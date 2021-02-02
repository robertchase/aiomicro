"""test rest operations"""
import marshmallow as ma
import pytest

from aiohttp import HTTPException
from aiomicro.micro import action
from aiomicro import rest


@pytest.mark.parametrize(
    'resource,args,result,is_value,is_exception', (
        ((), [], [], False, False),
        (('1',), [int], [1], False, False),
        (('1', '2'), [int], [1, '2'], False, False),
        (('1',), [int, int], None, False, True),
        (('hi',), [int], None, True, False),
    )
)
def test_normalize_args(resource, args, result, is_value, is_exception):
    """test args operation"""
    try:
        assert rest.normalize_args(resource, args) == result
    except ValueError:
        assert is_value
    except Exception:  # pylint: disable=broad-except
        assert is_exception


@pytest.mark.parametrize(
    'content,body,result,is_exception', (
        # empty case
        ({}, {}, {}, False),
        # body, no content expected
        ({}, {'a': '1'}, {}, False),
        # missing required content
        ({'a': action.Content('a', 'int')}, {}, {}, True),
        # missing not-required content (this is OK)
        (
            {
                'a': action.Content('a', 'int'),
                'b': action.Content('b', 'bool'),
                'c': action.Content('c', 'int', is_required=False),
            },
            {'a': '1', 'b': 'true'}, {'a': 1, 'b': True}, False
        ),
        # not-required content present
        (
            {
                'a': action.Content('a', 'int'),
                'b': action.Content('b', 'bool'),
                'c': action.Content('c', 'int', is_required=False),
            },
            {'a': '1', 'b': 'true', 'c': '12'},
            {'a': 1, 'b': True, 'c': 12}, False
        ),
    )
)
def test_normalize_content(content, body, result, is_exception):
    """test content operation"""
    try:
        assert rest.normalize_content(body, content) == result
    except HTTPException:
        assert is_exception


class ResponseSchema(ma.Schema):
    class Meta:
        unknown = ma.EXCLUDE

    a = ma.fields.String(missing=None)
    b = ma.fields.Integer(missing=None)
    c = ma.fields.Integer(missing=1)


@pytest.mark.parametrize(
    'result,expect,is_exception', (
        (None, {'a': None, 'b': None, 'c': 1}, False),
        ({'c': 2}, {'a': None, 'b': None, 'c': 2}, False),
        ({'c': '2'}, {'a': None, 'b': None, 'c': 2}, False),
        ({'a': '1', 'c': '2'}, {'a': '1', 'b': None, 'c': 2}, False),
        ({'a': '1', 'b': 123, 'c': '2'}, {'a': '1', 'b': 123, 'c': 2}, False),
        ({'d': 2}, {'a': None, 'b': None, 'c': 1}, False),
        ('string', None, True),
    )
)
def test_response(result, expect, is_exception):
    """test json response"""
    res = action.Response("json", marshmallow="tests.test_rest.ResponseSchema")
    resp = rest._Response(res)  # pylint: disable=protected-access

    if is_exception:
        with pytest.raises(Exception):
            resp(result)
    else:
        assert resp(result) == expect


@pytest.mark.parametrize(
    'result,expect', (
        ('a', 'a'),
        (1, '1'),
        ({'a': 1}, "{'a': 1}"),
        (None, 'foo'),
    )
)
def test_response_str(result, expect):
    """test str response operation"""
    res = action.Response('str', default='foo')
    resp = rest._Response(res)  # pylint: disable=protected-access

    assert resp(result) == expect
