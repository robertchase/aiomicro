"""tests for http parser"""
import gzip
import pytest

from aiomicro import http


class MockContext:  # pylint: disable=too-few-public-methods,R0902
    """mock for parser fsm context"""
    def __init__(self, data):
        try:
            self.data = data.encode()
        except AttributeError:
            self.data = data
        http.act_clear(self)


@pytest.mark.parametrize(
    'line,expected,remainder', (
        ('abc', None, 'abc'),
        ('abc\n', 'abc', ''),
        ('abc\r\n', 'abc', ''),
        ('abc\r\ndef', 'abc', 'def'),
        ('abc\r\ndef\r\n', 'abc', 'def\r\n'),
    )
)
def test_line(line, expected, remainder):
    """test end of line detection"""

    ctx = MockContext(line)
    result = http._line(ctx)  # pylint: disable=protected-access
    assert result == expected

    try:
        remainder = remainder.encode()
    except AttributeError:
        pass
    assert ctx.data == remainder


@pytest.mark.parametrize(
    'line,max_len,message', (
        ('abcdefghij', 5, 'no end of line encountered'),
        ('abcdefghij\n', 5, ''),
    )
)
def test_line_length(line, max_len, message):
    """test line length limits"""
    ctx = MockContext(line)
    ctx.http_max_line_length = max_len  # pylint: disable=W0201
    try:
        http._line(ctx)  # pylint: disable=protected-access
        assert False
    except http.HTTPException as ex:
        assert ex.code == 431
        assert ex.explanation == message


@pytest.mark.parametrize(
    'status,method,resource,query', (
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
def test_status(status, method, resource, query):
    """test status action routine"""
    ctx = MockContext(status)
    http.act_status(ctx)
    assert ctx.http_method == method  # pylint: disable=no-member
    assert ctx.http_resource == resource  # pylint: disable=no-member
    assert ctx.http_query == query


@pytest.mark.parametrize(
    'status,message', (
        ('GET / HTTP/1.1 FOO\n', 'malformed status line'),
        ('GET /\n', 'malformed status line'),
        ('GET / FOO\n', 'unsupported HTTP protocol'),
    )
)
def test_invalid_status(status, message):
    """test status action routine"""
    ctx = MockContext(status)
    try:
        http.act_status(ctx)
        assert False
    except http.HTTPException as ex:
        assert ex.code == 400
        assert ex.explanation == message


@pytest.mark.parametrize(
    'header,result,expected', (
        ('A: B\n', 'header', {'a': 'B'}),
        ('', None, {}),
        ('\r\n', 'done', {}),
    )
)
def test_header(header, result, expected):
    """test header action routine"""
    ctx = MockContext(header)
    res = http.act_header(ctx)
    assert res == result
    assert ctx.http_headers == expected


def test_invalid_header():
    """test missing colon in header"""
    ctx = MockContext('ABC\n')
    try:
        http.act_header(ctx)
        assert False
    except http.HTTPException as ex:
        assert ex.code == 400
        assert ex.explanation == 'header missing colon'


def test_too_many_headers():
    """test header count limit"""
    ctx = MockContext('X:Y\n')
    ctx.http_headers = {'a': 'b'}  # pylint: disable=W0201
    ctx.http_max_header_count = 1  # pylint: disable=W0201
    try:
        http.act_header(ctx)
        assert False
    except http.HTTPException as ex:
        assert ex.code == 400
        assert ex.explanation == 'max header count exceeded'


@pytest.mark.parametrize(
    'header,result,expected', (
        ({'content-length': '10'}, 'content', 10),
    )
)
def test_process_headers(header, result, expected):
    """test process_headers action routine"""
    ctx = MockContext(b'')
    ctx.http_headers = header  # pylint: disable=W0201
    res = http.act_process_headers(ctx)
    assert res == result
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
    """test content length"""
    ctx = MockContext(b'')
    ctx.http_headers = headers  # pylint: disable=W0201
    ctx.http_max_content_length = 10_000  # pylint: disable=W0201
    try:
        http._content_length(ctx)  # pylint: disable=protected-access
        assert ctx.http_content_length == length
    except http.HTTPException as ex:
        assert ex.code == code
        assert ex.reason == reason
        assert ex.explanation == explanation


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
    """test content-type"""
    ctx = MockContext(b'')
    ctx.http_headers = headers  # pylint: disable=W0201
    try:
        http._content_type(ctx)  # pylint: disable=protected-access
        assert ctx.http_content_type == content_type
        assert ctx.http_charset == charset  # pylint: disable=no-member
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
    """test transfer encoding"""
    ctx = MockContext(b'')
    ctx.http_headers = headers  # pylint: disable=W0201
    try:
        http._transfer_encoding(ctx)  # pylint: disable=protected-access
        assert ctx.http_encoding == encoding
    except http.HTTPException as ex:
        assert ex.code == code
        assert ex.explanation == explanation


@pytest.mark.parametrize(
    'body,is_gzip,result,length,code,reason,explanation', (
        ('test', False, 'test', None, None, None, None),
        ('test', True, 'test', None, None, None, None),
        ('test', True, 'test', 1, 400, 'Bad Request', 'malformed gzip data'),
        ('test', False, None, 10, None, None, None),
    )  # pylint: disable=too-many-arguments
)
def test_body(body, is_gzip, result, length, code, reason, explanation):
    """test act_body action routine"""
    if is_gzip:
        body = gzip.compress(body.encode())
    ctx = MockContext(body)
    if is_gzip:
        ctx.http_encoding = 'gzip'  # pylint: disable=W0201
    ctx.http_content_length = length if length \
        else len(body)  # pylint: disable=attribute-defined-outside-init
    try:
        http.act_body(ctx)
        assert ctx.http_content == result
    except http.HTTPException as ex:
        assert ex.code == code
        assert ex.reason == reason
        assert ex.explanation == explanation


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
def test_content(method, query, type,  # pylint: disable=redefined-builtin
                 body, result):
    """test content extraction"""
    ctx = MockContext(b'')
    ctx.http_method = method  # pylint: disable=attribute-defined-outside-init
    ctx.http_query = query  # pylint: disable=attribute-defined-outside-init
    ctx.http_content_type = type  # pylint: disable=W0201
    ctx.http_content = body  # pylint: disable=attribute-defined-outside-init
    http._content(ctx)  # pylint: disable=protected-access
    assert ctx.content == (  # pylint: disable=no-member
        result if result is not None else {})
