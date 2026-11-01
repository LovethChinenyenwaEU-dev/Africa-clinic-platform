"""Week 12: the checks the restore drill runs against a restored database. Here they run
against the test database itself, which stands in for a perfect restore."""
import json

import pytest

from app import backup_check
from app.backup_check import Head, check_restore, read_heads, restored_revision
from tests.scheduling_helpers import build_clinic


@pytest.fixture
def clinic(session, run_id):
    """A clinic with a few audit lines (registering its patient writes one)."""
    return build_clinic(session, run_id, "bk")


def ours(session, clinic):
    tenant_id = str(clinic["tenant"].id)
    return {tenant_id: read_heads(session)[tenant_id]}


def test_the_heads_name_each_clinics_latest_line(session, clinic):
    head = ours(session, clinic)[str(clinic["tenant"].id)]

    assert head.seq >= 1
    assert len(head.hash) == 64


def test_this_codes_migration_version_is_the_databases(session):
    assert backup_check.expected_revision() == restored_revision(session)


def test_an_untouched_copy_passes(session, clinic):
    heads = ours(session, clinic)

    assert check_restore(session, heads, revision=restored_revision(session)) == []


def test_a_copy_whose_audit_line_differs_fails(session, clinic):
    heads = {t: Head(h.seq, "f" * 64) for t, h in ours(session, clinic).items()}

    problems = check_restore(session, heads, revision=restored_revision(session))

    assert len(problems) == 1
    assert "not the line recorded at backup time" in problems[0]


def test_a_copy_missing_recent_audit_lines_fails(session, clinic):
    heads = {t: Head(h.seq + 5, h.hash) for t, h in ours(session, clinic).items()}

    problems = check_restore(session, heads, revision=restored_revision(session))

    assert "existed at backup time" in problems[0]


def test_a_copy_from_another_code_version_fails(session, clinic):
    problems = check_restore(session, ours(session, clinic), revision="9999")

    assert "Migration version" in problems[0]


def test_the_heads_command_prints_json_with_ids_and_hashes_only(session, clinic, capsys):
    assert backup_check.main(["heads"]) == 0

    printed = json.loads(capsys.readouterr().out)
    mine = printed[str(clinic["tenant"].id)]
    assert set(mine) == {"seq", "hash"}


def test_an_unknown_command_is_refused():
    assert backup_check.main(["nonsense"]) == 2
