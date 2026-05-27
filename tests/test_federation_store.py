"""Tests for VersionStore federation protocol methods."""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from pathlib import Path

# Third party imports:
import pytest

# Local imports:
from cantica.core.federation_crypto import generate_key_pair
from cantica.services.version_store import VersionStore


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def store(tmp_path: Path) -> VersionStore:
    vault = tmp_path / "vault"
    s = VersionStore(vault)
    yield s
    s.close()


# ── get_or_create_identity ────────────────────────────────────────────────────


def test_get_or_create_identity_generates_key_pair(store: VersionStore) -> None:
    identity = store.get_or_create_identity()
    assert identity.public_key_pem.startswith("-----BEGIN PUBLIC KEY-----")
    assert store._federation_key_path().exists()


def test_get_or_create_identity_persists_key(store: VersionStore, tmp_path: Path) -> None:
    id1 = store.get_or_create_identity()
    id2 = store.get_or_create_identity()
    assert id1.public_key_pem == id2.public_key_pem


def test_get_or_create_identity_key_file_mode(store: VersionStore) -> None:
    store.get_or_create_identity()
    import stat

    mode = store._federation_key_path().stat().st_mode
    assert oct(stat.S_IMODE(mode)) == "0o600"


def test_get_or_create_identity_existing_key_missing_db_row(
    store: VersionStore, tmp_path: Path
) -> None:
    """If the key file exists but the DB row was deleted, a new row is created."""
    pub, priv = generate_key_pair()
    key_path = store._federation_key_path()
    key_path.write_text(priv)
    key_path.chmod(0o600)
    # Force cache invalidation so the cached_property uses the new key
    try:
        del store.__dict__["_fed_enc_key"]
    except KeyError:
        pass
    identity = store.get_or_create_identity()
    assert identity.public_key_pem == pub


# ── sign_federation_message ───────────────────────────────────────────────────


def test_sign_federation_message(store: VersionStore) -> None:
    store.get_or_create_identity()
    sig = store.sign_federation_message(b"test payload")
    assert isinstance(sig, str)
    assert len(sig) > 0


# ── create / get / list federations ──────────────────────────────────────────


def test_create_federation_returns_federation_and_member(store: VersionStore) -> None:
    store.get_or_create_identity()
    fed, member = store.create_federation("test-fed")
    assert fed.name == "test-fed"
    assert fed.is_founder is True
    assert member.federation_id == fed.id
    assert member.is_accepted is True


def test_get_federation_found(store: VersionStore) -> None:
    store.get_or_create_identity()
    fed, _ = store.create_federation("alpha")
    result = store.get_federation(fed.id)
    assert result is not None
    assert result.name == "alpha"


def test_get_federation_not_found(store: VersionStore) -> None:
    store.get_or_create_identity()
    assert store.get_federation("no-such-id") is None


def test_get_federation_by_name_found(store: VersionStore) -> None:
    store.get_or_create_identity()
    store.create_federation("beta")
    result = store.get_federation_by_name("beta")
    assert result is not None
    assert result.name == "beta"


def test_get_federation_by_name_not_found(store: VersionStore) -> None:
    store.get_or_create_identity()
    assert store.get_federation_by_name("unknown") is None


def test_list_federations_empty(store: VersionStore) -> None:
    store.get_or_create_identity()
    assert store.list_federations() == []


def test_list_federations_multiple(store: VersionStore) -> None:
    store.get_or_create_identity()
    store.create_federation("fed-1")
    store.create_federation("fed-2")
    feds = store.list_federations()
    names = {f.name for f in feds}
    assert names == {"fed-1", "fed-2"}


# ── add_federation_member ─────────────────────────────────────────────────────


def test_add_federation_member_new(store: VersionStore) -> None:
    store.get_or_create_identity()
    fed, _ = store.create_federation("my-fed")
    pub2, _priv2 = generate_key_pair()
    member = store.add_federation_member(fed.id, pub2, "http://peer.example/v1/federate")
    assert member.public_key == pub2
    assert member.federate_url == "http://peer.example/v1/federate"
    assert member.is_accepted is True


def test_add_federation_member_update_existing(store: VersionStore) -> None:
    store.get_or_create_identity()
    fed, _ = store.create_federation("my-fed")
    pub2, _priv2 = generate_key_pair()
    m1 = store.add_federation_member(fed.id, pub2, "http://old.example/v1/federate")
    m2 = store.add_federation_member(
        fed.id, pub2, "http://new.example/v1/federate", is_accepted=False
    )
    assert m1.id == m2.id
    assert m2.federate_url == "http://new.example/v1/federate"
    assert m2.is_accepted is False


# ── get_member_by_key ─────────────────────────────────────────────────────────


def test_get_member_by_key_found(store: VersionStore) -> None:
    store.get_or_create_identity()
    fed, _ = store.create_federation("my-fed")
    pub2, _priv2 = generate_key_pair()
    store.add_federation_member(fed.id, pub2, "http://peer.example/v1/federate")
    result = store.get_member_by_key(fed.id, pub2)
    assert result is not None
    assert result.public_key == pub2


def test_get_member_by_key_not_found(store: VersionStore) -> None:
    store.get_or_create_identity()
    fed, _ = store.create_federation("my-fed")
    pub2, _priv2 = generate_key_pair()
    assert store.get_member_by_key(fed.id, pub2) is None


# ── update_member_status ──────────────────────────────────────────────────────


def test_update_member_status_found(store: VersionStore) -> None:
    store.get_or_create_identity()
    fed, founding_member = store.create_federation("my-fed")
    updated = store.update_member_status(founding_member.id, is_accepted=False)
    assert updated is not None
    assert updated.is_accepted is False


def test_update_member_status_not_found(store: VersionStore) -> None:
    store.get_or_create_identity()
    result = store.update_member_status("no-such-id", is_accepted=True)
    assert result is None


# ── list_federation_members ───────────────────────────────────────────────────


def test_list_federation_members_accepted_only(store: VersionStore) -> None:
    store.get_or_create_identity()
    fed, _ = store.create_federation("my-fed")
    pub2, _priv2 = generate_key_pair()
    store.add_federation_member(fed.id, pub2, "http://peer.example/v1/federate", is_accepted=False)
    # Only the founding member (accepted) should be in accepted_only results
    members = store.list_federation_members(fed.id, accepted_only=True)
    assert all(m.is_accepted for m in members)
    assert len(members) == 1


def test_list_federation_members_all(store: VersionStore) -> None:
    store.get_or_create_identity()
    fed, _ = store.create_federation("my-fed")
    pub2, _priv2 = generate_key_pair()
    store.add_federation_member(fed.id, pub2, "http://peer.example/v1/federate", is_accepted=False)
    members = store.list_federation_members(fed.id, accepted_only=False)
    assert len(members) == 2


# ── remove_federation_member ──────────────────────────────────────────────────


def test_remove_federation_member_success(store: VersionStore) -> None:
    store.get_or_create_identity()
    fed, founding_member = store.create_federation("my-fed")
    result = store.remove_federation_member(founding_member.id)
    assert result is True
    assert store.list_federation_members(fed.id, accepted_only=True) == []


def test_remove_federation_member_not_found(store: VersionStore) -> None:
    store.get_or_create_identity()
    assert store.remove_federation_member("no-such-id") is False


# ── reconcile_members_table ───────────────────────────────────────────────────


def test_reconcile_members_table_adds_unknown_member(store: VersionStore) -> None:
    store.get_or_create_identity()
    fed, _ = store.create_federation("my-fed")
    pub2, _priv2 = generate_key_pair()
    submitted = [{"public_key": pub2, "federate_url": "http://new.example/v1/federate", "is_accepted": True}]
    canonical = store.reconcile_members_table(fed.id, submitted)
    keys = {m.public_key for m in canonical}
    assert pub2 in keys


def test_reconcile_members_table_prunes_leaving_member(store: VersionStore) -> None:
    store.get_or_create_identity()
    fed, _ = store.create_federation("my-fed")
    pub2, _priv2 = generate_key_pair()
    # Add a member then mark it as not accepted (wants to leave)
    m = store.add_federation_member(fed.id, pub2, "http://peer.example/v1/federate", is_accepted=False)
    canonical = store.reconcile_members_table(fed.id, [])
    member_ids = {m.id for m in canonical}
    assert m.id not in member_ids


def test_reconcile_members_table_skips_existing_keys(store: VersionStore) -> None:
    store.get_or_create_identity()
    fed, founding_member = store.create_federation("my-fed")
    # Submit the founding member's key again — should not create a duplicate
    submitted = [{"public_key": founding_member.public_key, "federate_url": "", "is_accepted": True}]
    canonical = store.reconcile_members_table(fed.id, submitted)
    assert len(canonical) == 1


def test_get_member_by_key_skips_corrupted_rows(store: VersionStore) -> None:
    """get_member_by_key silently skips rows whose public_key_enc is corrupted."""
    store.get_or_create_identity()
    fed, _ = store.create_federation("my-fed")
    # Manually insert a row with garbage encrypted data
    from cantica.orm.tables import FederationMemberOrm  # noqa: PLC0415
    from cantica.services.version_store import _iso, _utcnow  # noqa: PLC0415

    now = _iso(_utcnow())
    import uuid  # noqa: PLC0415

    store.session.execute(
        store._insert(FederationMemberOrm).values(
            id=str(uuid.uuid4()),
            federation_id=fed.id,
            public_key_enc="not-valid-base64-or-aes!!!",
            federate_url_enc="not-valid",
            is_accepted=1,
            joined_at=now,
            updated_at=now,
        )
    )
    store.session.commit()
    # Should return None (corrupted row skipped) rather than raising
    result = store.get_member_by_key(fed.id, "some-key-that-doesnt-exist")
    assert result is None
