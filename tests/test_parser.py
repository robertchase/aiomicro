"""test micro parser"""
from io import StringIO
import pytest

from aiomicro.micro.parser import parse


def test_database():
    """test database directive"""
    database, _, _ = parse(StringIO(
        'DATABASE name yeah foo=bar yes=no'
    ))
    assert database["name"]
    assert database["name"].args[0] == 'yeah'


def test_database_multiple():
    """test database directive"""
    database, _, _ = parse(StringIO(
        'DATABASE one yeah foo=bar yes=no\n'
        'DATABASE two yeah-yeah foo=bar yes=no'
    ))
    assert database["one"].args[0] == 'yeah'
    assert database["two"].args[0] == 'yeah-yeah'


def test_database_duplicate():
    """test multiple database directives"""
    with pytest.raises(Exception):
        parse(StringIO(
            'DATABASE duplicate yeah foo=bar yes=no\n'
            'DATABASE duplicate what foo=bar yes=no\n'
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
    assert response.default == ""


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
        "RESPONSE marshmallow path=tests.test_parser.function\n"
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
