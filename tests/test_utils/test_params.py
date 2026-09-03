import pytest
from maxapi.utils.params import bool_to_query


@pytest.mark.parametrize(
    ("value", "expected"),
    [(True, "true"), (False, "false")],
)
def test_bool_to_query(value, expected):
    assert bool_to_query(value) == expected
