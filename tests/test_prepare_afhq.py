from __future__ import annotations

import pytest

from scripts.prepare_afhq import validate_sample_sizes


def test_three_domain_gallery_accepts_200_per_domain() -> None:
    validate_sample_sizes(200, 40)


def test_three_domain_gallery_rejects_less_than_500_total() -> None:
    with pytest.raises(ValueError, match="tối thiểu 500"):
        validate_sample_sizes(166, 40)


@pytest.mark.parametrize("queries_per_domain", [0, 1, 3])
def test_query_count_must_be_even_and_positive(queries_per_domain: int) -> None:
    with pytest.raises(ValueError, match="số chẵn"):
        validate_sample_sizes(200, queries_per_domain)
