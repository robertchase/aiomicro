"""parser and producer for http documents"""
import gzip
import json
import re
import time
import urllib.parse as urlparse


class HTTPException(Exception):
    """add http attributes to base exception"""

    def __init__(self, code, reason, explanation=''):
        super(HTTPException).__init__()
        self.code = code
        self.reason = reason
        self.explanation = explanation


class Context:  # pylint: disable=too-few-public-methods
    """http fsm context"""

    def __init__(self):
        self.data = b''
        act_clear(self)


def act_clear(context):
    """action routine to set or reset the fsm context"""
    context.is_parsing = True
    context.http_max_content_length = None
    context.http_max_line_length = 10000
    context.http_max_header_count = 100

    context.http_message = ''
    context.http_headers = {}
    context.http_content = None
    context.http_method = None
    context.http_resource = None
    context.http_query_string = ''
    context.http_query = {}
    context.http_content_length = None
    context.http_content_type = None
    context.http_charset = None
    context.http_encoding = None

    context.content = {}


def act_data(context, data=None):
    """action routine to handle new incoming chunk of data"""
    if data:
        context.data += data


def _line(context):
    test = context.data.split(b'\n', 1)
    if len(test) == 1:
        if len(context.data) > context.http_max_line_length:
            raise HTTPException(431, 'Request Header Fields Too Long',
                                'no end of line encountered')
        return None
    line, context.data = test
    if line:
        if line.endswith(b'\r'):
            line = line[:-1]
        if len(line) > context.http_max_line_length:
            raise HTTPException(431, 'Request Header Fields Too Long')
    return line.decode('ascii')


def act_status(context):
    """action routine to handle status line"""
    line = _line(context)
    if not line:
        return None
    toks = line.split()
    if len(toks) != 3:
        raise HTTPException(400, 'Bad Request', 'malformed status line')
    if toks[2] not in ('HTTP/1.0', 'HTTP/1.1'):
        raise HTTPException(400, 'Bad Request', 'unsupported HTTP protocol')

    context.http_method = toks[0].upper()
    res = urlparse.urlparse(toks[1])
    context.http_resource = res.path
    if res.query:
        context.http_query_string = res.query
        for key, val in urlparse.parse_qs(res.query).items():
            context.http_query[key] = val[0] if len(val) == 1 else val

    return 'done'


def act_header(context):
    """action routine to handle a single header"""
    line = _line(context)
    if line is None:
        return None
    if len(line) == 0:
        return 'done'

    if len(context.http_headers) == context.http_max_header_count:
        raise HTTPException(400, 'Bad Request', 'max header count exceeded')
    test = line.split(':', 1)
    if len(test) != 2:
        raise HTTPException(400, 'Bad Request', 'header missing colon')
    name, value = test
    context.http_headers[name.strip().lower()] = value.strip()

    return 'header'


def _content_length(context):
    length = context.http_headers.get('content-length')
    if length is None:
        length = 0

    try:
        context.http_content_length = int(length)
    except ValueError:
        raise HTTPException(400, 'Bad Request', 'invalid content-length')

    if context.http_max_content_length:
        if context.http_content_length > context.http_max_content_length:
            raise HTTPException(413, 'Request Entity Too Large')


def _content_type(context):
    content_type = context.http_headers.get('content-type')
    if not content_type:
        return

    # lenient content-type parser
    pattern = (
        r'\s*'                # optional leading spaces
        '(?P<type>.+?)'       # content type
        r'\s*/\s*'            # slash with optional spaces
        '(?P<subtype>.+?)'    # content subtype
        '('                   # start of optional parameter specification
        r'\s*;\s*'            # semicolon with optional spaces
        '(?P<attribute>.+?)'  # attribute name
        r'\s*=\s*'            # equal with optional spaces
        '(?P<value>.+?)'      # attribute value
        ')?'                  # end of optional parameter specification
        r'\s*$'               # optional spaces and end of line
    )
    match = re.match(pattern, content_type)
    if not match:
        raise HTTPException(400, 'Bad Request', 'invalid content-type header')
    ctype = match.groupdict()
    context.http_content_type = f"{ctype['type']}/{ctype['subtype']}"
    if ctype.get('attribute') == 'charset':
        context.http_charset = ctype['value']


def _transfer_encoding(context):
    encoding = context.http_headers.get('transfer-encoding')
    if not encoding:
        return
    if encoding != 'gzip':
        raise HTTPException(400, 'Bad Request',
                            'unsupported transfer encoding')
    context.http_encoding = encoding


def act_process_headers(context):
    """action routine to handle headers"""
    _content_length(context)
    _content_type(context)
    _transfer_encoding(context)

    return 'content'


def _content(context):

    if context.http_method == 'GET':
        context.content = context.http_query
    elif context.http_method in ('PATCH', 'POST', 'PUT'):
        if context.http_content_type == 'application/json':
            context.content = json.loads(context.http_content)
        elif context.http_content_type == 'application/x-www-form-urlencoded':
            query = urlparse.parse_qs(context.http_content)
            context.content = {
                n: v[0] if len(v) == 1 else v for n, v in query.items()
            }


def act_body(context):
    """action routine to handle content"""
    if len(context.data) < context.http_content_length:
        return
    data = context.data[:context.http_content_length]
    context.data = context.data[context.http_content_length:]
    if context.http_encoding == 'gzip':
        try:
            data = gzip.decompress(data)
        except Exception:
            raise HTTPException(400, 'Bad Request', 'malformed gzip data')
    context.http_content = data.decode(context.http_charset or 'utf-8')
    _content(context)
    context.is_parsing = False


# ---


def format_server(content='', code=200, message='', headers=None):
    """format an http response"""

    if code == 200 and message == '':
        message = 'OK'
    status = 'HTTP/1.1 %d %s' % (code, message)

    if isinstance(content, (list, dict)):
        content_type = 'application/json'
    else:
        content_type = 'text/plain'

    return _format(status, headers, content, content_type)


def _format(status,  # pylint: disable=too-many-arguments
            headers, content, content_type='text/plain', charset='utf-8',
            close=False, compress=False):

    if not headers:
        headers = {}

    header_keys = [k.lower() for k in headers.keys()]

    if content:
        if 'content-type' not in header_keys:
            if content_type in ('json', 'application/json'):
                content = json.dumps(content)
                content_type = 'application/json'
            elif content_type in ('form', 'application/x-www-form-urlencoded'):
                content_type = 'application/x-www-form-urlencoded'
                content = urlparse.urlencode(content)
            headers['Content-Type'] = content_type

        if charset:
            content = content.encode(charset)
            headers['Content-Type'] += f'; charset={charset}'

    if compress:
        content = gzip.compress(content)
        headers['Content-Encoding'] = 'gzip'

    if 'date' not in header_keys:
        headers['Date'] = time.strftime(
            "%a, %d %b %Y %H:%M:%S %Z", time.localtime())

    if 'content-length' not in header_keys:
        headers['Content-Length'] = len(content)

    if close:
        headers['Connection'] = 'close'

    headers = '%s\r\n%s\r\n\r\n' % (
        status,
        '\r\n'.join(['%s: %s' % (k, v) for k, v in headers.items()]),
    )
    headers = headers.encode('ascii')

    return headers + content if content else headers
