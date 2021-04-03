"""test rest operations"""
import marshmallow as ma
import pytest

from aiohttp import HTTPException
from aiomicro.micro import action
from aiomicro import rest


class MyContent(ma.Schema):
    class Meta:
        ordered = True  # keeps exceptions in order for tests
    a = ma.fields.Integer(required=True)
    b = ma.fields.Boolean(required=True)
    c = ma.fields.String(required=True)


@pytest.mark.parametrize(
    'only,body,result,exception', (
        # happy
        ("a", (1,), [1], None),
        ("b,a", (False, 1), [False, 1], None),
        # bad
        ("a", ("bad",), None, "Not a valid integer: a"),
        # too many
        ("a", (1, "yeah"), None, "mismatch between ARG and regex group count"),
    )
)
def test_marshmallow_arg(only, body, result, exception):
    """test args operation"""
    try:
        path = "tests.test_rest.MyContent"
        content = action.MarshmallowArg(path, only)
        assert content(body) == result
    except HTTPException as exc:
        assert exc.explanation == exception


@pytest.mark.parametrize(
    'only,body,result,exception', (
        # happy
        ("a", {"a": 100}, {"a": 100}, None),
        ("a", {"a": "100"}, {"a": 100}, None),
        ("a,c", {"a": 100, "c": "yo"}, {"a": 100, "c": "yo"}, None),
        # order
        ("c,a", {"a": 100, "c": "yo"}, {"c": "yo", "a": 100}, None),
        ("c,a,b", dict(a=100, b=False, c="yo"), dict(c="yo", a=100, b=False),
            None),
        # empty case
        ("a", None, None, "expecting fields: a"),
        ("a,c", None, None, "expecting fields: a, c"),
        # missing
        ("a,c", {"a": 100}, None, "Missing data for required field: c"),
        ("a,b,c", {"a": 100}, None,
            ("Missing data for required field: b;"
             " Missing data for required field: c")),
        # bad value
        ("a", {"a": "bad"}, None, "Not a valid integer: a"),
        ("a,b", {"a": "bad", "b": "sad"}, None,
            "Not a valid integer: a; Not a valid boolean: b"),
        # extra
        ("a", {"a": 100, "d": "ohno"}, None, "Unknown field: d"),
        # all
        (None, {"a": 1, "b": True, "c": "hi"}, {"a": 1, "b": True, "c": "hi"},
            None),
        (None, {"a": 1, "b": True}, None,
            "Missing data for required field: c"),
    )
)
def test_marshmallow_content(only, body, result, exception):
    """test content operation"""
    try:
        path = "tests.test_rest.MyContent"
        content = action.MarshmallowContent(path, only)
        assert content(body) == result
    except HTTPException as exc:
        assert exc.explanation == exception


class ResponseSchema(ma.Schema):
    class Meta:
        unknown = ma.EXCLUDE

    a = ma.fields.String(missing=None)
    b = ma.fields.Integer(missing=None)
    c = ma.fields.Integer(missing=1)


@pytest.mark.parametrize(
    "only,result,expect,exception", (
        # happy
        (None, dict(a="foo", b=1, c=2), dict(a="foo", b=1, c=2), None),
        ("a", dict(a="foo", b=1, c=2), dict(a="foo"), None),
        ("b", dict(a="foo", b=1, c=2), dict(b=1), None),
        ("c,b", dict(a="foo", b=1, c=2), dict(b=1, c=2), None),
        ("a", dict(a="foo", d=2), dict(a="foo"), None),
        # default
        (None, {}, dict(a=None, b=None, c=1), None),
        ("a", {}, dict(a=None), None),
        ("a,c", dict(a="foo"), dict(a="foo", c=1), None),
        # bad data
        ("c", dict(c="akk"), None, {'c': ['Not a valid integer.']}),
    )
)
def test_marshmallow_response(only, result, expect, exception):
    """test json response"""
    path = "tests.test_rest.ResponseSchema"
    res = action.MarshmallowResponse(path=path, only=only)
    try:
        assert res(result) == expect
    except ma.exceptions.ValidationError as exc:
        assert exc.messages == exception


@pytest.mark.parametrize(
    'result,expect', (
        ('a', {"content": "a"}),
        (1, {"content": "1"}),
        ({'a': 1}, {"content": "{'a': 1}"}),
        (None, 'foo'),
    )
)
def test_str_response(result, expect):
    """test str response operation"""
    res = action.StrResponse(default='foo')
    resp = rest._Response(res)  # pylint: disable=protected-access

    assert resp(result) == expect
