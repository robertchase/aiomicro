"""parser and producer for http documents"""
import asyncio
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


class HTTPEOF(Exception):
    """unexpected end of stream"""


class HTTPDocument:

    def __init__(self):
        self.http_message = ''
        self.http_headers = {}
        self.http_self = None
        self.http_method = None
        self.http_resource = None
        self.http_query_string = ''
        self.http_query = {}
        self.http_self_length = None
        self.http_self_type = None
        self.http_charset = None
        self.http_encoding = None
        self.http_content_type = None
        self.is_keep_alive = True

        self.content = {}


class HTTPReader:
    """stream reader that supports a max line length and timeout"""

    def __init__(self, reader, max_line_length=10_000, max_header_count=100,
                 max_content_length=None, timeout=5):
        self.reader = reader
        self.max_line_length = max_line_length
        self.max_header_count = max_header_count
        self.max_content_length = max_content_length
        self.timeout = timeout
        self.buffer = b""

    async def chunk(self):
        """read a chunk from the underlying stream"""

        async def _read():
            return await self.reader.read(5000)

        data = await asyncio.wait_for(_read(), self.timeout)

        if len(data) == 0:
            raise HTTPEOF()

        self.buffer += data

    async def read(self, length):
        """read length bytes"""
        while True:
            if len(self.buffer) >= length:
                data, self.buffer = self.buffer[:length], self.buffer[length:]
                return data
            await self.chunk()

    async def readline(self):
        """read a line (ends in \n or \r\n) as ascii"""
        while True:
            test = self.buffer.split(b"\n", 1)
            if len(test) == 2:
                line, self.buffer = test
                if line.endswith(b"\r"):
                    line = line[:-1]
                if len(line) > self.max_line_length:
                    raise HTTPException(431, "Request Header Fields Too Long")
                return line.decode("ascii")

            if len(self.buffer) > self.max_line_length:
                raise HTTPException(431, "Request Header Fields Too Long",
                                    "no end of line encountered")
            await self.chunk()


async def parse(reader):
    """parse an HTTP document from a stream"""
    document = HTTPDocument()

    # --- status: POST / HTTP/1.1
    status = await reader.readline()
    toks = status.split()

    if len(toks) != 3:
        raise HTTPException(400, "Bad Request", "malformed status line")
    if toks[2] not in ("HTTP/1.0", "HTTP/1.1"):
        raise HTTPException(400, "Bad Request", "unsupported HTTP protocol")

    document.http_method = toks[0].upper()
    res = urlparse.urlparse(toks[1])
    document.http_resource = res.path
    if res.query:
        document.http_query_string = res.query
        for key, val in urlparse.parse_qs(res.query).items():
            document.http_query[key] = val[0] if len(val) == 1 else val

    # --- headers
    while len(header := await reader.readline()) > 0:
        if len(document.http_headers) == reader.max_header_count:
            raise HTTPException(400, "Bad Request",
                                "max header count exceeded")
        test = header.split(":", 1)
        if len(test) != 2:
            raise HTTPException(400, "Bad Request", "header missing colon")
        name, value = test
        document.http_headers[name.strip().lower()] = value.strip()

    # --- keep alive
    keep_alive = document.http_headers.get("connection", "keep-alive")
    document.is_keep_alive = keep_alive == "keep-alive"

    # --- content length
    length = document.http_headers.get("content-length")
    if length is None:
        length = 0

    try:
        document.http_content_length = int(length)
    except ValueError:
        raise HTTPException(400, "Bad Request", "invalid content-length")

    if reader.max_content_length:
        if document.http_content_length > reader.max_content_length:
            raise HTTPException(413, "Request Entity Too Large")

    # --- content type
    if "content-type" in document.http_headers and \
        document.http_headers.get("content-type") == "":
            raise HTTPException(400, "Bad Request",
                                "invalid content-type header")

    content_type = document.http_headers.get("content-type")
    if content_type:

        # lenient content-type parser
        pattern = (
            r"\s*"                # optional leading spaces
            "(?P<type>.+?)"       # content type
            r"\s*/\s*"            # slash with optional spaces
            "(?P<subtype>[^;]+?)" # content subtype
            "("                   # start of optional parameter specification
            r"\s*;\s*"            # semicolon with optional spaces
            "(?P<attribute>.+?)"  # attribute name
            r"\s*=\s*"            # equal with optional spaces
            "(?P<value>.+?)"      # attribute value
            ")?"                  # end of optional parameter specification
            r"\s*$"               # optional spaces and end of line
        )
        match = re.match(pattern, content_type)
        if not match:
            raise HTTPException(400, "Bad Request",
                                "invalid content-type header")
        ctype = match.groupdict()
        document.http_content_type = f"{ctype['type']}/{ctype['subtype']}"
        if ctype.get("attribute") == "charset":
            document.http_charset = ctype["value"]

    # --- content encoding
    encoding = document.http_headers.get("content-encoding")
    if encoding:
        if encoding != "gzip":
            raise HTTPException(400, "Bad Request",
                                "unsupported content encoding")
    document.http_encoding = encoding

    # --- body
    if document.http_content_length:
        data = await reader.read(document.http_content_length)
        if document.http_encoding == "gzip":
            try:
                data = gzip.decompress(data)
            except Exception:
                raise HTTPException(400, "Bad Request", "malformed gzip data")
        document.http_content = data.decode(document.http_charset or "utf-8")

    # --- content
    if document.http_method == "GET":
        document.content = document.http_query
    elif document.http_method in ("PATCH", "POST", "PUT"):
        if document.http_content_type == "application/json":
            try:
                document.content = json.loads(document.http_content)
            except json.decoder.JSONDecodeError:
                raise HTTPException(400, "Bad Request", "invalid json content")
        elif document.http_content_type == "application/x-www-form-urlencoded":
            query = urlparse.parse_qs(document.http_content)
            document.content = {
                n: v[0] if len(v) == 1 else v for n, v in query.items()
            }

    return document


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
