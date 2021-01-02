"""test micro parser"""
from io import StringIO
import pytest

from aiomicro.micro.parser import parse


def test_database():
    """test database directive"""
    database, _, _ = parse(StringIO(
        'DATABASE yeah foo=bar yes=no'
    ))
    assert database
    assert database.args[0] == 'yeah'


def test_database_multiple():
    """test multiple database directives"""
    with pytest.raises(Exception):
        parse(StringIO(
            'DATABASE yeah foo=bar yes=no\n'
            'DATABASE what foo=bar yes=no\n'
        ))


def test_group():
    """test group directive"""
    _, servers, _ = parse(StringIO(
        'GROUP test_group ONE TWO to_upper=true\n'
        'SERVER test 1000\n'
        'ROUTE /test/ping\n'
        'ARG group=test_group\n'
    ))
    server = servers[0]
    route = server.routes[0]
    arg = route.args[0]
    group_type = arg.type
    assert group_type('one') == 'ONE'
    with pytest.raises(ValueError):
        group_type('three')


def test_group_duplicate():
    """test group directive"""
    with pytest.raises(Exception):
        parse(StringIO(
            'GROUP test_group ONE TWO to_upper=true\n'
            'GROUP test_group three four to_lower=true\n'
        ))


def double(fun):
    """double the output of the fn"""
    def _double():
        return fun() * 2
    return _double


def function():
    """return a string"""
    return 'foo'


def test_wrap():
    """test wrap directive"""
    _, servers, _ = parse(StringIO(
        'WRAP test_wrap tests.test_parser.double\n'
        'SERVER test 1000\n'
        'ROUTE /test/ping\n'
        'GET tests.test_parser.function\n'
        'PUT tests.test_parser.function wrap=test_wrap\n'
    ))
    server = servers[0]
    route = server.routes[0]
    get = route.methods['GET']
    assert get.handler() == function()
    put = route.methods['PUT']
    assert put.handler() == double(function)()


def test_response_str():
    """test response directive"""
    _, servers, _ = parse(StringIO(
        'SERVER test 1000\n'
        'ROUTE /test/ping\n'
        'GET tests.test_parser.function\n'
        'RESPONSE str\n'
    ))
    server = servers[0]
    route = server.routes[0]
    get = route.methods['GET']
    response = get.response
    assert response.type == 'str'
    assert response.default is None


def test_response_str_default():
    """test response directive"""
    _, servers, _ = parse(StringIO(
        'SERVER test 1000\n'
        'ROUTE /test/ping\n'
        'GET tests.test_parser.function\n'
        'RESPONSE str default=whatever\n'
    ))
    server = servers[0]
    route = server.routes[0]
    get = route.methods['GET']
    response = get.response
    assert response.type == 'str'
    assert response.default == 'whatever'


def test_response_str_key():
    """test response directive"""
    with pytest.raises(Exception):
        parse(StringIO(
            'SERVER test 1000\n'
            'ROUTE /test/ping\n'
            'GET test.test_parser.function\n'
            'RESPONSE str\n'
            'KEY abc\n'
        ))


def test_response_json():
    """test response directive"""
    _, servers, _ = parse(StringIO(
        'SERVER test 1000\n'
        'ROUTE /test/ping\n'
        'GET tests.test_parser.function\n'
        'RESPONSE json\n'
        'KEY abc\n'
    ))
    assert servers  # more to do here


def test_response_json_default():
    """test response directive"""
    with pytest.raises(Exception):
        _, servers, _ = parse(StringIO(
            'SERVER test 1000\n'
            'ROUTE /test/ping\n'
            'GET test.test_parser.function\n'
            'RESPONSE json default=foo\n'
        ))
        assert servers  # more to do here
