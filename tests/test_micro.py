"""test micro fsm"""
import pytest

from aiomicro.micro import micro
from aiomicro.http import HTTPException


@pytest.mark.parametrize(
    'value,expected,is_exception', (
        (1, 1, False),
        (0, 0, False),
        (-1, -1, False),
        (None, None, True),
        ('string', None, True),
        (1.1, None, True),
    )
)
def test_int(value, expected, is_exception):
    """test int operaton"""
    try:
        assert micro._int(value) == expected  # pylint: disable=W0212
    except ValueError:
        assert is_exception


@pytest.mark.parametrize(
    'value,expected,is_exception', (
        (1, 1, False),
        (0, None, True),
        (-1, None, True),
        (None, None, True),
        ('string', None, True),
        (1.1, None, True),
    )
)
def test_count(value, expected, is_exception):
    """test count operation"""
    try:
        assert micro._count(value) == expected  # pylint: disable=W0212
    except ValueError:
        assert is_exception


@pytest.mark.parametrize(
    'value,expected,is_exception', (
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
def test_boolean(value, expected, is_exception):
    """test boolean operation"""
    try:
        assert micro._boolean(value) == expected  # pylint: disable=W0212
    except ValueError:
        assert is_exception


@pytest.mark.parametrize(
    'values,to_upper,to_lower,value,expected,is_exception', (
        (['A', 'B', 'C'], True, False, 'a', 'A', False),
        (['A', 'B', 'C'], True, False, 'A', 'A', False),
        (['A', 'B', 'C'], True, False, 'z', None, True),
        (['a', 'b', 'c'], False, True, 'a', 'a', False),
        (['a', 'b', 'c'], False, True, 'A', 'a', False),
        (['a', 'b', 'c'], False, True, 'z', None, True),
        (['a', 'b', 'c'], False, True, '', None, True),
    )  # pylint: disable=too-many-arguments
)
def test_group(values, to_upper, to_lower, value, expected, is_exception):
    """test group operation"""
    try:
        group = micro.Group(*values, to_upper=to_upper,
                            to_lower=to_lower)
        assert group(value) == expected
    except ValueError:
        assert is_exception


def _yup():
    return 'yup'


@pytest.mark.parametrize(
    'type,group,groups,value,expected,is_valueerror,is_exception', (
        ('int', None, None, '1', 1, False, False),
        (None, 'TEST', {'TEST': micro.Group('a', 'b')},
         'a', 'a', False, False),
        (None, 'TEST', {'TEST': micro.Group('a', 'b')},
         'c', None, True, False),
        (None, 'WHAT', {'TEST': micro.Group('a', 'b')}, None, None, False,
         True),
        ('test.test_micro._yup', None, None, 'a', 'yup', False, True),
    )  # pylint: disable=too-many-arguments
)
def test_type(type,  # pylint: disable=redefined-builtin
              group, groups, value, expected, is_valueerror, is_exception):
    """test type coersion"""
    try:
        _type = micro._type(  # pylint: disable=protected-access
            type, group, groups)
        assert _type(value) == expected
    except ValueError:
        assert is_valueerror
    except Exception:  # pylint: disable=broad-except
        assert is_exception


@pytest.mark.parametrize(
    'args,kwargs,value,expected,is_valueerror,is_exception', (
        (['int'], {}, '1', 1, False, False),
        (['int'], {}, 'x', None, True, False),
        ([], {'group': 'TEST'}, 'a', 'a', False, False),
        ([], {'group': 'TEST'}, 'B', 'b', False, False),
        ([], {'group': 'TEST'}, 'X', None, True, False),
        ([], {'group': 'HUH'}, None, None, False, True),
    )  # pylint: disable=too-many-arguments
)
def test_arg(args, kwargs, value, expected, is_valueerror, is_exception):
    """test arg type coersion"""
    kwargs['groups'] = {
        'TEST': micro.Group('a', 'b', 'c', to_lower=True),
    }
    try:
        arg = micro.Arg(*args, **kwargs)
        assert arg(value) == expected
    except ValueError:
        assert is_valueerror
    except Exception:  # pylint: disable=broad-except
        assert is_exception


@pytest.mark.parametrize(
    'args,kwargs,content,expected,is_valueerror,is_exception', (
        (['test'], {}, '1', '1', False, False),
        (['test', 'int'], {}, '1', 1, False, False),
        (['test', 'int'], {}, 'x', None, True, False),
        (['test'], {'group': 'TEST'}, 'a', 'a', False, False),
        (['test'], {'group': 'TEST'}, 'B', 'b', False, False),
        (['test'], {'group': 'TEST'}, 'X', None, True, False),
        (['test'], {'group': 'HUH'}, None, None, False, True),
    )  # pylint: disable=too-many-arguments
)
def test_content(args, kwargs, content, expected, is_valueerror, is_exception):
    """test content type coersion"""
    kwargs['groups'] = {
        'TEST': micro.Group('a', 'b', 'c', to_lower=True),
    }
    try:
        arg = micro.Content(*args, **kwargs)
        assert arg(content) == expected
    except HTTPException:
        assert is_valueerror
    except Exception:  # pylint: disable=broad-except
        assert is_exception


def test_act_group():
    """test group action routine"""
    ctx = micro.Context()
    assert not ctx.groups
    micro.act_group(ctx, 'test', 'a', 'b')
    assert len(ctx.groups) == 1
    assert ctx.groups['test']('a') == 'a'


def test_act_server():
    """test server action routine"""
    ctx = micro.Context()
    assert not ctx.server
    assert not ctx.servers
    micro.act_server(ctx, 'test', '123')
    assert ctx.server == ctx.servers[0]
    assert ctx.server.port == 123


def test_act_route():
    """test route action routine"""
    ctx = micro.Context()
    assert not ctx.route
    micro.act_server(ctx, 'test', '123')
    micro.act_route(ctx, 'pattern')
    assert ctx.route
    assert ctx.route == ctx.server.routes[-1]


def test_act_arg():
    """test arg action routine"""
    ctx = micro.Context()
    ctx.route = micro.Route('pattern')
    assert not ctx.route.args
    micro.act_arg(ctx, 'int')
    assert ctx.route.args


def test_act_content():
    """test content action routine"""
    ctx = micro.Context()
    ctx.method = micro.Method('test.test_micro._yup')
    assert not ctx.method.contents
    micro.act_content(ctx, 'test', 'int')
    assert ctx.method.contents


def test_method():
    """test method setter"""
    ctx = micro.Context()
    ctx.route = micro.Route('pattern')
    assert not ctx.route.methods
    micro._method(ctx, 'GET',  # pylint: disable=protected-access
                  'test.test_micro._yup')
    assert ctx.route.methods
    assert ctx.route.methods.get('GET')


def _wrap(request):
    assert request.test1
    assert not request.test2


def test_wrap():
    """test micro wrap operation"""

    def wrapper(handler):
        def inner(request, *args, **kwargs):
            request.test1 = True
            handler(request, *args, **kwargs)
            request.test2 = True
        return inner

    class Request:  # pylint: disable=too-few-public-methods
        """mock request"""

        def __init__(self):
            self.test1 = False
            self.test2 = False

    ctx = micro.Context()
    ctx.wraps['test'] = wrapper
    ctx.route = micro.Route('pattern')
    micro._method(ctx, 'GET',  # pylint: disable=protected-access
                  'test.test_micro._wrap', wrap='test')
    res = Request()
    ctx.method.handler(res)
    assert res.test2
