"""rest/http"""
from itertools import zip_longest
import re

from aiohttp import HTTPException


def normalize_args(resource, args):
    """extract and format/normalize args from http resource"""

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
    """extract content from http request"""

    result = {}
    for name, defn in kwargs.items():
        if name in body:
            result[name] = defn(body[name])
        elif defn.is_required:
            raise HTTPException(400, 'Bad Request', f"'{name}' is required")
    return result


class _Response:

    def __init__(self, response):
        self.response = response
        self.result = {}

    def __call__(self, result):

        if self.response is None:
            response = result
        elif result is None:
            response = self.default()
        elif self.response.type == 'str':
            response = str(result)
        elif self.response.marshmallow is not None:
            response = self.response.marshmallow.load(result)
        elif not isinstance(result, dict):
            raise Exception('expecting dict result from handler')
        else:
            response = result
        return response

    def default(self):
        """return default value for response"""
        if self.response.type == 'str':
            result = self.response.default
        elif self.response.marshmallow is not None:
            result = self.response.marshmallow.load({})
        else:
            raise Exception()
        return result


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
        if not check:
            continue
        method = route.methods.get(request.http_method)
        if not method:
            break
        args = normalize_args(check.groups(), route.args)
        kwargs = normalize_content(request.content, method.contents)
        return _Match(method, args, kwargs)

    raise HTTPException(404, 'Not Found')
