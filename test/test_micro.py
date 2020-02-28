import pytest

from aiomicro.micro import micro
from aiomicro.http import HTTPException


@pytest.mark.parametrize(
    'input,expected,is_exception', (
        (1, 1, False),
        (0, 0, False),
        (-1, -1, False),
        (None, None, True),
        ('string', None, True),
        (1.1, None, True),
    )
)
def test_int(input, expected, is_exception):
    try:
        assert micro._int(input) == expected
    except ValueError:
        assert is_exception


@pytest.mark.parametrize(
    'input,expected,is_exception', (
        (1, 1, False),
        (0, None, True),
        (-1, None, True),
        (None, None, True),
        ('string', None, True),
        (1.1, None, True),
    )
)
def test_count(input, expected, is_exception):
    try:
        assert micro._count(input) == expected
    except ValueError:
        assert is_exception


@pytest.mark.parametrize(
    'input,expected,is_exception', (
        (1, True, False),
        (0, False, False),
        ('True', True, False),
        ('False', False, False),
        ('TrUe', True, False),
        ('FaLse', False, False),
        ('t', True, False),
        ('f', False, False),
        ('tr', None, True),
        ('fa', None, True),
        (None, None, True),
    )
)
def test_boolean(input, expected, is_exception):
    try:
        assert micro._boolean(input) == expected
    except ValueError:
        assert is_exception


@pytest.mark.parametrize(
    'values,to_upper,to_lower,input,expected,is_exception', (
        (['A', 'B', 'C'], True, False, 'a', 'A', False),
        (['A', 'B', 'C'], True, False, 'A', 'A', False),
        (['A', 'B', 'C'], True, False, 'z', None, True),
        (['a', 'b', 'c'], False, True, 'a', 'a', False),
        (['a', 'b', 'c'], False, True, 'A', 'a', False),
        (['a', 'b', 'c'], False, True, 'z', None, True),
        (['a', 'b', 'c'], False, True, '', None, True),
    )
)
def test_group(values, to_upper, to_lower, input, expected, is_exception):
    try:
        group = micro.Group(*values, to_upper=to_upper,
                            to_lower=to_lower)
        assert group(input) == expected
    except ValueError:
        assert is_exception


def _yup(value):
    return 'yup'


@pytest.mark.parametrize(
    'type,group,groups,input,expected,is_valueerror,is_exception', (
        ('int', None, None, '1', 1, False, False),
        (None, 'TEST', {'TEST': micro.Group('a', 'b')},
         'a', 'a', False, False),
        (None, 'TEST', {'TEST': micro.Group('a', 'b')},
         'c', None, True, False),
        (None, 'WHAT', {'TEST': micro.Group('a', 'b')}, None, None, False,
         True),
        ('test.test_micro._yup', None, None, 'a', 'yup', False, True),
    )
)
def test_type(type, group, groups, input, expected, is_valueerror,
              is_exception):
    try:
        _type = micro._type(type, group, groups)
        assert _type(input) == expected
    except ValueError:
        assert is_valueerror
    except Exception:
        assert is_exception


@pytest.mark.parametrize(
    'args,kwargs,input,expected,is_valueerror,is_exception', (
        (['int'], {}, '1', 1, False, False),
        (['int'], {}, 'x', None, True, False),
        ([], {'group': 'TEST'}, 'a', 'a', False, False),
        ([], {'group': 'TEST'}, 'B', 'b', False, False),
        ([], {'group': 'TEST'}, 'X', None, True, False),
        ([], {'group': 'HUH'}, None, None, False, True),
    )
)
def test_arg(args, kwargs, input, expected, is_valueerror, is_exception):
    kwargs['groups'] = {
        'TEST': micro.Group('a', 'b', 'c', to_lower=True),
    }
    try:
        arg = micro.Arg(*args, **kwargs)
        assert arg(input) == expected
    except ValueError:
        assert is_valueerror
    except Exception:
        assert is_exception


@pytest.mark.parametrize(
    'args,kwargs,input,expected,is_valueerror,is_exception', (
        (['test'], {}, '1', '1', False, False),
        (['test', 'int'], {}, '1', 1, False, False),
        (['test', 'int'], {}, 'x', None, True, False),
        (['test'], {'group': 'TEST'}, 'a', 'a', False, False),
        (['test'], {'group': 'TEST'}, 'B', 'b', False, False),
        (['test'], {'group': 'TEST'}, 'X', None, True, False),
        (['test'], {'group': 'HUH'}, None, None, False, True),
    )
)
def test_content(args, kwargs, input, expected, is_valueerror, is_exception):
    kwargs['groups'] = {
        'TEST': micro.Group('a', 'b', 'c', to_lower=True),
    }
    try:
        arg = micro.Content(*args, **kwargs)
        assert arg(input) == expected
    except HTTPException:
        assert is_valueerror
    except Exception:
        assert is_exception


def test_act_group():
    ctx = micro.Context()
    assert not ctx.groups
    micro.act_group(ctx, 'test', 'a', 'b')
    assert len(ctx.groups) == 1
    assert ctx.groups['test']('a') == 'a'


def test_act_server():
    ctx = micro.Context()
    assert not ctx.server
    assert not ctx.servers
    micro.act_server(ctx, 'test', '123')
    assert ctx.server == ctx.servers[0]
    assert ctx.server.port == 123


def test_act_route():
    ctx = micro.Context()
    assert not ctx.route
    micro.act_server(ctx, 'test', '123')
    micro.act_route(ctx, 'pattern')
    assert ctx.route
    assert ctx.route == ctx.server.routes[-1]


def test_act_arg():
    ctx = micro.Context()
    ctx.route = micro.Route('pattern')
    assert not ctx.route.args
    micro.act_arg(ctx, 'int')
    assert ctx.route.args


def test_act_content():
    ctx = micro.Context()
    ctx.method = micro.Method('test.test_micro._yup')
    assert not ctx.method.contents
    micro.act_content(ctx, 'test', 'int')
    assert ctx.method.contents


def test_method():
    ctx = micro.Context()
    ctx.route = micro.Route('pattern')
    assert not ctx.route.methods
    micro._method(ctx, 'GET', 'test.test_micro._yup')
    assert ctx.route.methods
    assert ctx.route.methods.get('GET')


def _wrap(request, *args, **kwargs):
    assert request.test1
    assert not request.test2


def test_wrap():

    def wrapper(handler):
        def inner(request, *args, **kwargs):
            request.test1 = True
            handler(request, *args, **kwargs)
            request.test2 = True
        return inner

    class request:
        def __init__(self):
            self.test1 = False
            self.test2 = False

    ctx = micro.Context()
    ctx.wraps['test'] = wrapper
    ctx.route = micro.Route('pattern')
    micro._method(ctx, 'GET', 'test.test_micro._wrap', wrap='test')
    r = request()
    ctx.method.handler(r)
    assert r.test2
