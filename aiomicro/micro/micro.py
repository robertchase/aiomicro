import re

from ergaleia import import_by_path

from aiomicro.http import HTTPException


class Context:

    def __init__(self):
        self.database = None
        self.groups = {}
        self.servers = []
        self.server = None
        self.route = None
        self.method = None


class Database:

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs


class Group:

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


class Server:

    def __init__(self, name, port):
        self.name = name
        self.port = int(port)
        self.routes = []


class Route:

    def __init__(self, pattern):
        self.pattern = re.compile(pattern)
        self.args = []
        self.methods = {}


class Method:

    def __init__(self, path, silent=False, cursor=False):
        self.handler = import_by_path(path)
        self.silent = _boolean(silent)
        self.cursor = _boolean(cursor)
        self.contents = {}


def _int(value):
    try:
        if int(value) == float(value):
            return int(value)
    except Exception:
        raise ValueError('must be an int')


def _count(value):
    try:
        value = _int(value)
        if value > 0:
            return value
    except Exception:
        pass
    raise ValueError('must be a positive int')


def _boolean(value):
    if value is True or value is False:
        return value
    if str(value).upper() in ('1', 'TRUE', 'T'):
        return True
    if str(value).upper() in ('0', 'FALSE', 'F'):
        return False
    raise ValueError('must be a boolean')


def _type(type, group=None, groups=None):

    if group:
        try:
            return groups[group]
        except KeyError:
            raise Exception(f"group '{group}' not defined")

    if type is None:
        return str

    try:
        return {
            'int': _int,
            'count': _count,
            'bool': _boolean,
        }[type]
    except KeyError:
        pass

    try:
        return import_by_path(type)
    except Exception:
        raise Exception(f"unable to import validation function '{type}'")


class Arg:

    def __init__(self, type=None, group=None, groups=None):
        self.type = _type(type, group, groups=groups)

    def __call__(self, value):
        return self.type(value)


class Content:

    def __init__(self, name, type=None, group=None, groups=None,
                 is_required=True):
        self.name = name
        self.type = _type(type, group=group, groups=groups)
        self.is_required = _boolean(is_required)

    def __call__(self, value):
        try:
            return self.type(value)
        except ValueError as e:
            raise HTTPException(400, 'Bad Request', f"'{self.name}': {e}")


def act_database(context, *args, **kwargs):
    context.database = Database(*args, **kwargs)


def act_group(context, name, *values, to_upper=False, to_lower=False):
    group = Group(*values, to_upper=to_upper, to_lower=to_lower)
    context.groups[name] = group


def act_server(context, name, port):
    # TODO: check for duplicate server name
    server = Server(name, port)
    context.server = server
    context.servers.append(server)


def act_route(context, pattern):
    route = Route(pattern)
    context.route = route
    context.server.routes.append(route)


def act_arg(context, *args, **kwargs):
    arg = Arg(*args, groups=context.groups, **kwargs)
    context.route.args.append(arg)


def act_content(context, *args, **kwargs):
    # TODO: check for duplicate content name
    content = Content(*args, groups=context.groups, **kwargs)
    context.method.contents[content.name] = content


def _method(context, command, path, **kwargs):
    # TODO: check for duplicate command
    method = Method(path, **kwargs)
    context.method = method
    context.route.methods[command] = method


def act_get(context, path, **kwargs):
    _method(context, 'GET', path, **kwargs)


def act_patch(context, path, **kwargs):
    _method(context, 'PATCH', path, **kwargs)


def act_put(context, path, **kwargs):
    _method(context, 'PUT', path, **kwargs)


def act_post(context, path, **kwargs):
    _method(context, 'POST', path, **kwargs)


def act_delete(context, path, **kwargs):
    _method(context, 'DELETE', path, **kwargs)
