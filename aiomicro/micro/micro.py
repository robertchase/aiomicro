"""action routines for micro file parsing"""
import re

from ergaleia import import_by_path

from aiomicro.http import HTTPException


class Context:  # pylint: disable=too-few-public-methods
    """Context for micro fsm"""

    def __init__(self):
        self.database = None
        self.groups = {}
        self.wraps = {}
        self.servers = []
        self.server = None
        self.route = None
        self.method = None


class Database:  # pylint: disable=too-few-public-methods
    """Container for database configuration"""

    def __init__(self, *args, **kwargs):
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
        self.contents = {}
        self.response = None


class Response:  # pylint: disable=too-few-public-methods
    """Container for a response configuration"""

    def __init__(self, type,  # pylint: disable=redefined-builtin
                 default=None):

        if type not in ('json', 'str'):
            raise Exception(f"invalid response type '{type}'")
        if default is not None and type != 'str':
            raise Exception(f"default not valid with type '{type}'")
        self.type = type
        self.default = default
        self.keys = {}


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


class Arg:  # pylint: disable=too-few-public-methods
    """Container for arg definition"""

    def __init__(self, type=None,  # pylint: disable=redefined-builtin
                 group=None, groups=None):
        self.type = _type(type, group, groups=groups)

    def __call__(self, value):
        return self.type(value)


class Content:  # pylint: disable=too-few-public-methods
    """Container for content definition"""

    def __init__(self, name,  # pylint: disable=too-many-arguments
                 type=None,  # pylint: disable=redefined-builtin
                 group=None, groups=None, is_required=True):
        self.name = name
        self.type = _type(type, group=group, groups=groups)
        self.is_required = _boolean(is_required)

    def __call__(self, value):
        try:
            return self.type(value)
        except ValueError as ex:
            raise HTTPException(400, 'Bad Request', f"'{self.name}': {ex}")


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


def act_route(context, pattern):
    """action routine for route"""
    route = Route(pattern)
    context.route = route
    context.server.routes.append(route)


def act_arg(context, *args, **kwargs):
    """action routine for arg"""
    arg = Arg(*args, groups=context.groups, **kwargs)
    context.route.args.append(arg)


def act_content(context, *args, **kwargs):
    """action routine for content"""
    content = Content(*args, groups=context.groups, **kwargs)
    if content.name in context.method.contents:
        raise Exception('duplicate content name')
    context.method.contents[content.name] = content


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


def act_response(context, type,  # pylint: disable=redefined-builtin
                 default=None):
    """action routine for response"""
    if context.method.response is not None:
        raise Exception('response already defined')
    context.method.response = Response(type, default=default)


def act_key(context, name, **kwargs):
    """action routine for response key"""
    response = context.method.response
    if response.type != 'json':
        raise Exception('key only valid for json response types')
    if name in response.keys.keys():
        raise Exception('duplicate key name')
    response.keys[name] = Key(name, groups=context.groups, **kwargs)
