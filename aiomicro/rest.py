from itertools import zip_longest
import re

import fsm.parser as fsm

from aiomicro.http import HTTPException


class Parser:

    _fsm = fsm.Parser.parse('aiomicro.http.fsm')

    def __init__(self):
        self.fsm = Parser._fsm.compile()

    @property
    def is_loading(self):
        return self.fsm.context.is_parsing

    @property
    def request(self):
        return Request(self.fsm.context)

    def handle(self, data):
        self.fsm.handle('data', data)


class Request:

    def __init__(self, http):
        self._http = http

    def __getattr__(self, name):
        if name in ('http_headers', 'http_content', 'http_method',
                    'http_resource', 'http_query_string', 'http_query',
                    'content'):
            return getattr(self._http, name)
        raise AttributeError(f"'Request' object has no attribute '{name}'")


def normalize_args(resource, args):

    if len(args) > len(resource):
        raise Exception('too few regex matches in http resource')

    return [
        fn(value) for
        value, fn in
        zip_longest(
            resource, args,
            fillvalue=lambda x: x
        )
    ]


def normalize_content(body, kwargs):

    result = {}
    for name, defn in kwargs.items():
        if name in body:
            result[name] = defn(body[name])
        elif defn.is_required:
            raise HTTPException(400, 'Bad Request', f"'{name}' is required")
    return result


class _Match:

    def __init__(self, method, args, kwargs):
        self.args = args
        self.kwargs = kwargs
        self.handler = method.handler
        self.silent = method.silent
        self.cursor = method.cursor

    async def __call__(self, request):
        return await self.handler(request, *self.args, **self.kwargs)


def match(server, request):

    for route in server.routes:
        match = re.match(route.pattern, request.http_resource)
        if not match:
            continue
        method = route.methods.get(request.http_method)
        if not method:
            break
        args = normalize_args(match.groups(), route.args)
        kwargs = normalize_content(request.content, method.contents)
        return _Match(method, args, kwargs)

    raise HTTPException(404, 'Not Found')
