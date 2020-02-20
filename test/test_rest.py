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
