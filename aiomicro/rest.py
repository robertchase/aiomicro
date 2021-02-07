"""rest/http"""
from itertools import zip_longest
import re

from aiohttp import HTTPException


class _Response:

    def __init__(self, response):
        self.response = response

    def __call__(self, result):
        if self.response is None:
            response = result
        elif result is None:
            response = self.response.default
        else:
            response = self.response(result)
        return response


class _Match:  # pylint: disable=too-few-public-methods

    def __init__(self, method, args, kwargs):
        self.args = args
        self.kwargs = kwargs
        self.handler = method.handler
        self.silent = method.silent
        self.cursor = method.cursor
        self.response = _Response(method.response)

    async def __call__(self, request):
        result = await self.handler(request, *self.args, **self.kwargs)
        return self.response(result)


def match(server, request):
    """match http resource and method against server routes"""

    for route in server.routes:
        check = re.match(route.pattern, request.http_resource)
        if check:
            method = route.methods.get(request.http_method)
            if not method:
                break

            # normalize args (from url) and content
            if route.args:
                args = route.args(check.groups())
            else:
                args = []
            if method.content:
                kwargs = method.content(request.content)
            else:
                kwargs = {}

            return _Match(method, args, kwargs)

    raise HTTPException(404, 'Not Found')
