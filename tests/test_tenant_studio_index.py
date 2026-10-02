import pytest

from multimodal_agents.tenant_studio_index import (
    RESERVED_TENANT_IDS,
    ensure_tenant_alias,
    tenant_alias,
    validate_tenant_id,
)


def test_reserved_tenant_id_is_rejected():
    with pytest.raises(ValueError):
        validate_tenant_id("book-reference")


def test_empty_tenant_id_is_rejected():
    with pytest.raises(ValueError):
        validate_tenant_id("")


def test_non_alphanumeric_tenant_id_is_rejected():
    with pytest.raises(ValueError):
        validate_tenant_id("lab one; drop table")


def test_tenant_alias_name_is_scoped_and_distinct():
    assert tenant_alias("lab-one") != tenant_alias("lab-two")
    assert "lab-one" in tenant_alias("lab-one")


def test_shared_index_name_never_equals_any_tenant_alias():
    """The isolation boundary is the alias, not the index: any code path
    that queries TENANT_INDEX directly sees every tenant's documents. This
    module must never expose that raw index to a tenant-facing caller.
    """
    from multimodal_agents.tenant_studio_index import TENANT_INDEX

    for tenant_id in ("lab-one", "lab-two", "anything"):
        assert tenant_alias(tenant_id) != TENANT_INDEX
