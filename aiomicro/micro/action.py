"""action routines for micro file parsing"""
import re

import marshmallow as ma

from aiohttp import HTTPException
from aiomicro.util import import_by_path
from aiomicro.util.types import boolean


class Database:  # pylint: disable=too-few-public-methods
    """Container for database configuration"""

    def __init__(self, connection_name, *args, pool=False, pool_size=10,
                 **kwargs):
        self.connection_name = connection_name
        self.pool = boolean(pool)
        self.pool_size = int(pool_size)
        self.args = args
        self.kwargs = kwargs


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

    def __init__(self, path, silent=False, cursor=None, wrap=None):
        self.handler = import_by_path(path)
        if wrap:
            self.handler = wrap(self.handler)
        self.silent = boolean(silent)
        self.cursor = cursor
        self.content = None
        self.response = None


class MarshmallowResponse:
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


class StrResponse:  # pylint: disable=too-few-public-methods
    """Container for a string response configuration"""

    def __init__(self, default=""):
        self._default = default

    def __call__(self, value):
        return str(value)

    @property
    def default(self):
        return self._default


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
            result = self.schema.load(value)
            return {key: result[key] for key in self.fields}  # enforce order
        except ma.exceptions.ValidationError as exc:
            msg = "; ".join([
                f"{msg[:-1]}: {fld}"
                for fld, msgs in exc.messages.items()
                for msg in msgs])
            raise HTTPException(400, "Bad Request", msg)


class MarshmallowArg(MarshmallowContent):
    """Container for arg definition"""

    def __call__(self, value):
        if len(value) != len(self.fields):
            raise HTTPException(500, "Internal Server Error",
                                "mismatch between ARG and regex group count")
        value = dict(zip(self.fields, value))
        result = super().__call__(value)
        return [result[fld] for fld in self.fields]


def act_database(context, *args, **kwargs):
    """action routine for database"""
    db = Database(*args, **kwargs)
    if db.connection_name in context.database:
        raise Exception('duplicate database name')
    context.database[db.connection_name] = db


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
    cursor = kwargs.get("cursor")
    if cursor:
        if cursor not in context.database:
            raise Exception('undefined database name')
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
        response = StrResponse(**kwargs)
    elif payload_type == "marshmallow":
        response = MarshmallowResponse(**kwargs)
    else:
        raise Exception("invalid response type")

    context.method.response = response


STATES = dict(
        INIT=dict(
            database=(act_database, None),
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
            response=(act_response, None),
            route=(act_route, "ROUTE"),
            server=(act_server, "SERVER"),

        )
    )
