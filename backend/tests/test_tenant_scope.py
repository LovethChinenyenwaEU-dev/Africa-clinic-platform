import uuid

import pytest

from app.core.tenant_scope import tenant_select
from app.modules.tenancy.models import Branch, Tenant


def test_scoped_query_filters_on_tenant_id():
    sql = str(tenant_select(Branch, uuid.uuid4()))
    assert "branch.tenant_id" in sql


def test_table_without_tenant_id_is_refused():
    with pytest.raises(TypeError):
        tenant_select(Tenant, uuid.uuid4())