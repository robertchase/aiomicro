"""test micro actions"""
import marshmallow as ma

from aiomicro.micro import action, parser


# @pytest.mark.parametrize(
#     'value,expected,is_exception', (
#         (1, True, False),
#         (0, False, False),
#         ('True', True, False),
#         ('False', False, False),
#         ('TrUe', True, False),
#         ('FaLse', False, False),
#         ('t', True, False),
#         ('f', False, False),
#         ('tr', None, True),
#         ('fa', None, True),
#         (None, None, True),
#     )
# )
# def test_boolean(value, expected, is_exception):
#     """test boolean operation"""
#     try:
#         assert action._boolean(value) == expected  # pylint: disable=W0212
#     except ValueError:
#         assert is_exception


def _yup():
    return 'yup'


def test_act_server():
    """test server action routine"""
    ctx = parser.Parser()
    assert not ctx.server
    assert not ctx.servers
    action.act_server(ctx, 'test', '123')
    assert ctx.server == ctx.servers[0]
    assert ctx.server.port == 123


def test_act_route():
    """test route action routine"""
    ctx = parser.Parser()
    assert not ctx.route
    action.act_server(ctx, 'test', '123')
    action.act_route(ctx, 'pattern')
    assert ctx.route
    assert ctx.route == ctx.server.routes[-1]


class Schema(ma.Schema):
    pass


def test_act_arg():
    """test arg action routine"""
    ctx = parser.Parser()
    ctx.route = action.Route('pattern')
    assert not ctx.route.args
    action.act_arg(ctx, "marshmallow", path="tests.test_micro.Schema")
    assert ctx.route.args


def test_act_content():
    """test content action routine"""
    ctx = parser.Parser()
    ctx.method = action.Method('tests.test_micro._yup')
    assert not ctx.method.content
    action.act_content(ctx, "marshmallow", path="tests.test_micro.Schema")
    assert ctx.method.content


def test_method():
    """test method setter"""
    ctx = parser.Parser()
    ctx.route = action.Route('pattern')
    assert not ctx.route.methods
    action._method(ctx, 'GET',  # pylint: disable=protected-access
                   'tests.test_micro._yup')
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

    ctx = parser.Parser()
    ctx.wraps['test'] = wrapper
    ctx.route = action.Route('pattern')
    action._method(ctx, 'GET',  # pylint: disable=protected-access
                   'tests.test_micro._wrap', wrap='test')
    res = Request()
    ctx.method.handler(res)
    assert res.test2
