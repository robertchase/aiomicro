"""action routines for micro file parsing"""
import re

import marshmallow as ma

from aiohttp import HTTPException
from aiomicro.util import import_by_path


class Database:  # pylint: disable=too-few-public-methods
    """Container for database configuration"""

    def __init__(self, *args, pool=False, pool_size=10, **kwargs):
        self.pool = _boolean(pool)
        self.pool_size = int(pool_size)
        self.args = args
        self.kwargs = kwargs


class Group:  # pylint: disable=too-few-public-methods
    """Definition for a group"""

    def __init__(self, *values, to_upper=False, to_lower=False):
        self.values = values
        self.to_upper = to_upper
        self.to_lower = to_lower

    def __call__(self, value):
        if self.to_upper:
            value = value.upper()
        elif self.to_lower:
            value = value.lower()
        if value in self.values:
            return value
        raise ValueError('must be one of: %s' % str(self.values))


class Server:  # pylint: disable=too-few-public-methods
    """Container for a server configuration"""

    def __init__(self, name, port):
        self.name = name
        self.port = int(port)
        self.routes = []


class Route:  # pylint: disable=too-few-public-methods
    """Container for a route configuration"""

    def __init__(self, pattern):
        self.pattern = re.compile(pattern)
        self.args = []
        self.methods = {}


class Method:  # pylint: disable=too-few-public-methods
    """Container for a method configuration"""

    def __init__(self, path, silent=False, cursor=False, wrap=None):
        self.handler = import_by_path(path)
        if wrap:
            self.handler = wrap(self.handler)
        self.silent = _boolean(silent)
        self.cursor = _boolean(cursor)
        self.content = None
        self.response = None


class ResponseMarshmallow:
    """marshmallow managed response"""

    def __init__(self, path=None, only=None):
        schema = import_by_path(path)
        if only:
            self.schema = schema(only=only.split(","))
        else:
            self.schema = schema()

    def __call__(self, result):
        return self.schema.load(result, unknown=ma.EXCLUDE)

    @property
    def default(self):
        return self.schema.load({})


class ResponseStr:  # pylint: disable=too-few-public-methods
    """Container for a string response configuration"""

    def __init__(self, default=""):
        self._default = default

    def __call__(self, value):
        return str(value)

    @property
    def default(self):
        return self._default


class Key:  # pylint: disable=too-few-public-methods
    """Container for a response key"""

    def __init__(self, name,  # pylint: disable=too-many-arguments
                 type=None,  # pylint: disable=redefined-builtin
                 group=None, groups=None, default=None):
        self.name = name
        self.type = _type(type, group, groups=groups)
        self.default = default


def _int(value):
    """validator for int type"""
    try:
        if int(value) == float(value):
            return int(value)
    except ValueError:
        pass
    except TypeError:  # from None
        pass
    raise ValueError('must be an int')


def _count(value):
    """validator for count type"""
    try:
        value = _int(value)
        if value > 0:
            return value
    except ValueError:
        pass
    raise ValueError('must be a positive int')


def _boolean(value):
    """validator for boolean type"""
    if value is True or value is False:
        return value
    if str(value).upper() in ('1', 'TRUE', 'T'):
        return True
    if str(value).upper() in ('0', 'FALSE', 'F'):
        return False
    raise ValueError('must be a boolean')


def _type(name, group=None, groups=None):
    """overall type validator"""

    if group:
        try:
            return groups[group]
        except KeyError:
            raise Exception(f"group '{group}' not defined")

    if name is None:
        return str

    try:
        return {
            'int': _int,
            'count': _count,
            'bool': _boolean,
        }[name]
    except KeyError:
        pass

    try:
        return import_by_path(name)
    except Exception:
        raise Exception(f"unable to import validation function '{name}'")


class MarshmallowContent:  # pylint: disable=too-few-public-methods
    """Container for marshmallow content definition"""

    def __init__(self,  # pylint: disable=too-many-arguments
                 path=None, only=None):
        schema = import_by_path(path)
        if only:
            self.fields = only.split(",")
            self.schema = schema(only=only.split(","))
        else:
            self.fields = schema._declared_fields.keys()
            self.schema = schema()

    def __call__(self, value):
        if value is None:
            raise HTTPException(400, "Bad Request",
                                f"expecting fields: {', '.join(self.fields)}")
        try:
            return self.schema.load(value)
        except ma.exceptions.ValidationError as exc:
            msg = "; ".join([
                f"{msg[:-1]}: {fld}"
                for fld, msgs in exc.messages.items()
                for msg in msgs])
            raise HTTPException(400, "Bad Request", msg)


class MarshmallowArg(MarshmallowContent):
    """Container for arg definition"""

    def __call__(self, value):
        result = super().__call__(dict(zip(self.fields, value)))
        return [result[fld] for fld in self.fields]


def act_database(context, *args, **kwargs):
    """action routine for database"""
    if context.database:
        raise Exception('database already specified')
    context.database = Database(*args, **kwargs)


def act_group(context, name, *values, to_upper=False, to_lower=False):
    """action routine for group"""
    if name in context.groups.keys():
        raise Exception('group already specified')
    group = Group(*values, to_upper=to_upper, to_lower=to_lower)
    context.groups[name] = group


def act_server(context, name, port):
    """action routine for server"""
    for server in context.servers:
        if name == server.name:
            raise Exception('duplicate server name')
    server = Server(name, port)
    context.server = server
    context.servers.append(server)


def act_wrap(context, name, path):
    """action routine for wrap"""
    if name in context.wraps.keys():
        raise Exception('duplicate wrap name')
    context.wraps[name] = import_by_path(path)


def act_task(context, name, path):
    """action routine for task"""
    if name in context.tasks.keys():
        raise Exception('duplicate task name')
    context.tasks[name] = import_by_path(path)


def act_route(context, pattern):
    """action routine for route"""
    route = Route(pattern)
    context.route = route
    context.server.routes.append(route)


def act_arg(context, payload_type, **kwargs):
    """action routine for arg"""
    if context.route.args:
        raise Exception('args already defined')
    if payload_type == "marshmallow":
        args = MarshmallowArg(**kwargs)
    else:
        raise Exception("invalid arg type")

    context.route.args = args


def act_content(context, payload_type, **kwargs):
    """action routine for content"""
    if context.method.content is not None:
        raise Exception('content already defined')
    if payload_type == "marshmallow":
        content = MarshmallowContent(**kwargs)
    else:
        raise Exception("invalid response type")

    context.method.content = content


def _method(context, command, path, **kwargs):
    """helper for method action routines"""
    if command in context.route.methods:
        raise Exception('duplicate method command name')
    wrap = kwargs.get('wrap')
    if wrap:
        kwargs['wrap'] = context.wraps[wrap]
    method = Method(path, **kwargs)
    context.method = method
    context.route.methods[command] = method


def act_get(context, path, **kwargs):
    """action routine for get method"""
    _method(context, 'GET', path, **kwargs)


def act_patch(context, path, **kwargs):
    """action routine for patch method"""
    _method(context, 'PATCH', path, **kwargs)


def act_put(context, path, **kwargs):
    """action routine for put method"""
    _method(context, 'PUT', path, **kwargs)


def act_post(context, path, **kwargs):
    """action routine for post method"""
    _method(context, 'POST', path, **kwargs)


def act_delete(context, path, **kwargs):
    """action routine for delete method"""
    _method(context, 'DELETE', path, **kwargs)


def act_response(context, payload_type, **kwargs):
    """action routine for response"""
    if context.method.response is not None:
        raise Exception('response already defined')
    if payload_type == "str":
        response = ResponseStr(**kwargs)
    elif payload_type == "marshmallow":
        response = ResponseMarshmallow(**kwargs)
    else:
        raise Exception("invalid response type")

    context.method.response = response


STATES = dict(
        INIT=dict(
            database=(act_database, None),
            group=(act_group, None),
            wrap=(act_wrap, None),
            task=(act_task, None),
            server=(act_server, "SERVER"),

        ), SERVER=dict(
            server=(act_server, None),
            route=(act_route, "ROUTE"),

        ), ROUTE=dict(
            arg=(act_arg, None),
            get=(act_get, "METHOD"),
            patch=(act_patch, "METHOD"),
            put=(act_put, "METHOD"),
            post=(act_post, "METHOD"),
            delete=(act_delete, "METHOD"),

        ), METHOD=dict(
            content=(act_content, None),
            get=(act_get, None),
            patch=(act_patch, None),
            put=(act_put, None),
            post=(act_post, None),
            delete=(act_delete, None),
            response=(act_response, "RESPONSE"),
            route=(act_route, "ROUTE"),
            server=(act_server, "SERVER"),

        ), RESPONSE=dict(
            get=(act_get, "METHOD"),
            patch=(act_patch, "METHOD"),
            put=(act_put, "METHOD"),
            post=(act_post, "METHOD"),
            delete=(act_delete, "METHOD"),
            route=(act_route, "ROUTE"),
            server=(act_server, "SERVER"),

        )
    )
