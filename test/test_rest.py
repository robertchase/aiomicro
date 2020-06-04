import pytest

from aiomicro.http import HTTPException
from aiomicro.micro import micro
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
    try:
        assert rest.normalize_args(resource, args) == result
    except ValueError:
        assert is_value
    except Exception:
        assert is_exception


@pytest.mark.parametrize(
    'content,body,result,is_exception', (
        # empty case
        ({}, {}, {}, False),
        # body, no content expected
        ({}, {'a': '1'}, {}, False),
        # missing required content
        ({'a': micro.Content('a', 'int')}, {}, {}, True),
        # missing not-required content (this is OK)
        (
            {
                'a': micro.Content('a', 'int'),
                'b': micro.Content('b', 'bool'),
                'c': micro.Content('c', 'int', is_required=False),
            },
            {'a': '1', 'b': 'true'}, {'a': 1, 'b': True}, False
        ),
        # not-required content present
        (
            {
                'a': micro.Content('a', 'int'),
                'b': micro.Content('b', 'bool'),
                'c': micro.Content('c', 'int', is_required=False),
            },
            {'a': '1', 'b': 'true', 'c': '12'},
            {'a': 1, 'b': True, 'c': 12}, False
        ),
    )
)
def test_normalize_content(content, body, result, is_exception):
    try:
        assert rest.normalize_content(body, content) == result
    except HTTPException:
        assert is_exception


@pytest.mark.parametrize(
    'result,expect,is_exception', (
        (None, {'a': None, 'b': None, 'c': 1}, False),
        ({'c': 2}, {'a': None, 'b': None, 'c': 2}, False),
        ({'c': '2'}, {'a': None, 'b': None, 'c': 2}, False),
        ({'a': '1', 'c': '2'}, {'a': '1', 'b': None, 'c': 2}, False),
        ({'a': '1', 'b': 123, 'c': '2'}, {'a': '1', 'b': 123, 'c': 2}, False),
        ({'d': 2}, None, True),
        ('string', None, True),
    )
)
def test_response(result, expect, is_exception):
    res = micro.Response('json')
    res.keys['a'] = micro.Key('a')
    res.keys['b'] = micro.Key('b', type=int)
    res.keys['c'] = micro.Key('c', type=int, default=1)
    resp = rest._Response(res)

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
    res = micro.Response('str', default='foo')
    resp = rest._Response(res)

    assert resp(result) == expect
