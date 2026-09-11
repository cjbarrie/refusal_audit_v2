import numpy as np

from refusal_audit.response_validity.home_augmentation import allocate_integer_neyman


def test_integer_neyman_allocation_preserves_budget_and_bounds():
    sizes = np.array([10, 20, 30])
    weights = np.array([1.0, 9.0, 4.0])
    got = allocate_integer_neyman(weights, sizes, total=24, minimum_each=2)
    assert got.sum() == 24
    assert np.all(got >= 2)
    assert np.all(got <= sizes)
    assert got[1] > got[0]


def test_integer_neyman_allocation_rejects_impossible_minimum():
    try:
        allocate_integer_neyman(np.ones(3), np.repeat(10, 3), total=5, minimum_each=2)
    except ValueError as error:
        assert "minimum" in str(error)
    else:
        raise AssertionError("expected ValueError")
