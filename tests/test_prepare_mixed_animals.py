from __future__ import annotations

from scripts.prepare_mixed_animals import (
    identity_from_member,
    scene_from_member,
    slugify,
    split_identity_groups,
)


def test_identity_supports_both_afd_folder_layouts() -> None:
    assert identity_from_member("species/ver/10/000001.jpg") == "10"
    assert identity_from_member("species/11/ver/000001.jpg") == "11"


def test_scene_groups_afd_pair_variants() -> None:
    assert scene_from_member("species/ver/10/000001-1.jpg") == "000001"
    assert scene_from_member("species/ver/10/000001-2.jpg") == "000001"


def test_split_identity_groups_has_no_identity_leakage() -> None:
    groups = {str(index): [f"{index}-{item}.jpg" for item in range(6)] for index in range(1, 16)}
    split = split_identity_groups(groups, gallery_count=25, query_count=5)
    identities = {
        name: {identity for identity, _ in members}
        for name, members in split.items()
    }
    assert len(split["gallery"]) == 25
    assert len(split["validation"]) == 5
    assert len(split["test"]) == 5
    assert identities["gallery"].isdisjoint(identities["validation"])
    assert identities["gallery"].isdisjoint(identities["test"])
    assert identities["validation"].isdisjoint(identities["test"])
    assert len(identities["validation"]) == 5
    assert len(identities["test"]) == 5


def test_split_identity_groups_skips_rejected_source_member() -> None:
    groups = {str(index): [f"{index}-{item}.jpg" for item in range(8)] for index in range(1, 16)}
    rejected = {"1-0.jpg", "6-0.jpg", "11-0.jpg"}
    split = split_identity_groups(groups, gallery_count=25, query_count=5, excluded_members=rejected)
    assert rejected.isdisjoint({member for members in split.values() for _, member in members})


def test_slugify_scientific_name() -> None:
    assert slugify("Panthera tigris") == "panthera-tigris"
