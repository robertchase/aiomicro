"""rest/http"""
from itertools import zip_longest
import re

from aiomicro.http import HTTPException


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
            return result

        if result is None:
            return self.default()

        if self.response.type == 'str':
            return str(result)

        if not isinstance(result, dict):
            raise Exception('expecting dict result from handler')

        response = self.default()
        for key, val in result.items():
            if key not in response:
                raise Exception(f"unexpected key '{key}' in handler result")
            if val is None:
                continue
            cast = self.response.keys[key].type
            response[key] = cast(val)
        return response

    def default(self):
        """return default value for response"""
        if self.response.type == 'str':
            return self.response.default
        return {key: val.default for key, val in self.response.keys.items()}


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
