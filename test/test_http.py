import gzip
import pytest

from aiomicro import http


class MockContext:
    def __init__(self, data):
        try:
            self.data = data.encode()
        except AttributeError:
            self.data = data
        http.act_clear(self)


@pytest.mark.parametrize(
    'input,expected,remainder', (
        ('abc', None, 'abc'),
        ('abc\n', 'abc', ''),
        ('abc\r\n', 'abc', ''),
        ('abc\r\ndef', 'abc', 'def'),
        ('abc\r\ndef\r\n', 'abc', 'def\r\n'),
    )
)
def test_line(input, expected, remainder):

    ctx = MockContext(input)
    result = http._line(ctx)
    assert result == expected

    try:
        remainder = remainder.encode()
    except AttributeError:
        pass
    assert ctx.data == remainder


@pytest.mark.parametrize(
    'input,max,message', (
        ('abcdefghij', 5, 'no end of line encountered'),
        ('abcdefghij\n', 5, ''),
    )
)
def test_line_length(input, max, message):
    ctx = MockContext(input)
    ctx.http_max_line_length = max
    try:
        http._line(ctx)
        assert False
    except http.HTTPException as e:
        assert e.code == 431
        assert e.explanation == message


@pytest.mark.parametrize(
    'input,method,resource,query', (
        ('GET /', None, None, {}),
        ('GET / HTTP/1.1\n', 'GET', '/', {}),
        ('GET /?a=1 HTTP/1.1\n', 'GET', '/', {'a': '1'}),
        ('POST http://test.com/ HTTP/1.1\n', 'POST', '/', {}),
        ('PUT http://test.com/abc/def HTTP/1.1\n', 'PUT', '/abc/def', {}),
        (
            'PUT http://test.com/abc/def?a=b HTTP/1.1\n',
            'PUT', '/abc/def', {'a': 'b'}
        ),
    )
)
def test_status(input, method, resource, query):
    ctx = MockContext(input)
    http.act_status(ctx)
    assert ctx.http_method == method
    assert ctx.http_resource == resource
    assert ctx.http_query == query


@pytest.mark.parametrize(
    'input,message', (
        ('GET / HTTP/1.1 FOO\n', 'malformed status line'),
        ('GET /\n', 'malformed status line'),
        ('GET / FOO\n', 'unsupported HTTP protocol'),
    )
)
def test_invalid_status(input, message):
    ctx = MockContext(input)
    try:
        http.act_status(ctx)
        assert False
    except http.HTTPException as e:
        assert e.code == 400
        assert e.explanation == message


@pytest.mark.parametrize(
    'input,result,expected', (
        ('A: B\n', 'header', {'a': 'B'}),
        ('', None, {}),
        ('\r\n', 'done', {}),
    )
)
def test_header(input, result, expected):
    ctx = MockContext(input)
    r = http.act_header(ctx)
    assert r == result
    assert ctx.http_headers == expected


def test_invalid_header():
    ctx = MockContext('ABC\n')
    try:
        http.act_header(ctx)
        assert False
    except http.HTTPException as e:
        assert e.code == 400
        assert e.explanation == 'header missing colon'


def test_too_many_headers():
    ctx = MockContext('X:Y\n')
    ctx.http_headers = {'a': 'b'}
    ctx.http_max_header_count = 1
    try:
        http.act_header(ctx)
        assert False
    except http.HTTPException as e:
        assert e.code == 400
        assert e.explanation == 'max header count exceeded'


@pytest.mark.parametrize(
    'input,result,expected', (
        ({'content-length': '10'}, 'content', 10),
    )
)
def test_process_headers(input, result, expected):
    ctx = MockContext(b'')
    ctx.http_headers = input
    r = http.act_process_headers(ctx)
    assert r == result
    assert ctx.http_content_length == expected


@pytest.mark.parametrize(
    'headers,length,code,reason,explanation', (
        ({}, 0, None, None, None),
        (
            {'content-length': 'abc'},
            None, 400, 'Bad Request', 'invalid content-length'
        ),
        (
            {'content-length': 1_000_000},
            None, 413, 'Request Entity Too Large', ''
        ),
        ({'content-length': 1_000}, 1_000, None, None, None),
        ({'content-length': '1000'}, 1_000, None, None, None),
    )
)
def test_content_length(headers, length, code, reason, explanation):
    ctx = MockContext(b'')
    ctx.http_headers = headers
    ctx.http_max_content_length = 10_000
    try:
        http._content_length(ctx)
        assert ctx.http_content_length == length
    except http.HTTPException as e:
        assert e.code == code
        assert e.reason == reason
        assert e.explanation == explanation


@pytest.mark.parametrize(
    'headers,content_type,charset,is_exception', (
        ({}, None, None, False),
        (
            {'content-type': 'text/csv'},
            'text/csv', None, False
        ),
        (
            {'content-type': 'application/json; charset=utf-8'},
            'application/json', 'utf-8', False
        ),
        (
            {'content-type': ' application / json ; charset = utf-8 '},
            'application/json', 'utf-8', False
        ),
        ({'content-type': 'garbage'}, None, None, True),
    )
)
def test_content_type(headers, content_type, charset, is_exception):
    ctx = MockContext(b'')
    ctx.http_headers = headers
    try:
        http._content_type(ctx)
        assert ctx.http_content_type == content_type
        assert ctx.http_charset == charset
    except http.HTTPException:
        assert is_exception is True


@pytest.mark.parametrize(
    'headers,encoding,code,explanation', (
        ({}, None, None, None),
        ({'transfer-encoding': 'gzip'}, 'gzip', None, None),
        ({'transfer-encoding': 'chunked'}, None, 400,
         'unsupported transfer encoding'),
    )
)
def test_transfer_encoding(headers, encoding, code, explanation):
    ctx = MockContext(b'')
    ctx.http_headers = headers
    try:
        http._transfer_encoding(ctx)
        assert ctx.http_encoding == encoding
    except http.HTTPException as e:
        assert e.code == code
        assert e.explanation == explanation


@pytest.mark.parametrize(
    'input,is_gzip,result,length,code,reason,explanation', (
        ('test', False, 'test', None, None, None, None),
        ('test', True, 'test', None, None, None, None),
        ('test', True, 'test', 1, 400, 'Bad Request', 'malformed gzip data'),
        ('test', False, None, 10, None, None, None),
    )
)
def test_body(input, is_gzip, result, length, code, reason, explanation):
    if is_gzip:
        input = gzip.compress(input.encode())
    ctx = MockContext(input)
    if is_gzip:
        ctx.http_encoding = 'gzip'
    ctx.http_content_length = length if length else len(input)
    try:
        http.act_body(ctx)
        assert ctx.http_content == result
    except http.HTTPException as e:
        assert e.code == code
        assert e.reason == reason
        assert e.explanation == explanation


@pytest.mark.parametrize(
    'method,query,type,body,result', (
        ('GET', {'a': 1}, None, None, {'a': 1}),
        ('PATCH', {'a': 1}, None, None, None),
        ('POST', {'a': 1}, None, None, None),
        ('PUT', {'a': 1}, None, None, None),
        ('PATCH', None, 'application/json', '{"b": 2}', {'b': 2}),
        ('POST', {'a': 1}, 'application/json', '{"b": 2}', {'b': 2}),
        ('PUT', None, 'application/json',
         '{"b": 2, "c": 3}', {'b': 2, 'c': 3}),
        ('PATCH', None, 'application/x-www-form-urlencoded',
         'b=2', {'b': '2'}),
        ('PUT', None, 'application/x-www-form-urlencoded',
         'b=2&b=3', {'b': ['2', '3']}),
        ('POST', None, 'application/x-www-form-urlencoded',
         'b=2&b=3&c=4', {'b': ['2', '3'], 'c': '4'}),
    )
)
def test_content(method, query, type, body, result):
    ctx = MockContext(b'')
    ctx.http_method = method
    ctx.http_query = query
    ctx.http_content_type = type
    ctx.http_content = body
    http._content(ctx)
    assert ctx.content == (result if result is not None else {})
