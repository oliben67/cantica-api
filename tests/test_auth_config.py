"""Tests for AuthConfig YAML loader and FederationPolicy."""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Standard library imports:
from pathlib import Path

# Third party imports:
import pytest

# Local imports:
from cantica.core.auth_config import AuthConfig
from cantica.core.federation_crypto import generate_key_pair
from cantica.core.federation_policy import FederationPolicy, _key_fingerprint

# ── AuthConfig ────────────────────────────────────────────────────────────────


def test_auth_config_defaults():
    cfg = AuthConfig.from_yaml(None)
    assert cfg.provider == "local"
    assert cfg.anonymous.roles == ["readonly"]
    assert cfg.local.seed_users == []


def test_auth_config_missing_file(tmp_path: Path):
    cfg = AuthConfig.from_yaml(tmp_path / "nonexistent.yaml")
    assert cfg.provider == "local"


def test_auth_config_from_yaml(tmp_path: Path):
    yaml_content = """
provider: local
anonymous:
  roles: []
local:
  seed_users:
    - username: admin
      email: admin@example.com
      password: secret
      roles: [admin]
"""
    p = tmp_path / "auth.yaml"
    p.write_text(yaml_content)
    cfg = AuthConfig.from_yaml(p)
    assert cfg.provider == "local"
    assert cfg.anonymous.roles == []
    assert len(cfg.local.seed_users) == 1
    assert cfg.local.seed_users[0].username == "admin"
    assert cfg.local.seed_users[0].roles == ["admin"]


def test_auth_config_empty_yaml(tmp_path: Path):
    p = tmp_path / "auth.yaml"
    p.write_text("")
    cfg = AuthConfig.from_yaml(p)
    assert cfg.provider == "local"


# ── FederationPolicy ──────────────────────────────────────────────────────────


def test_federation_policy_defaults():
    policy = FederationPolicy.from_yaml(None)
    assert "read:public" in policy.federation.default


def test_federation_policy_missing_file(tmp_path: Path):
    policy = FederationPolicy.from_yaml(tmp_path / "nope.yaml")
    assert "read:public" in policy.federation.default


def test_federation_policy_default_permissions():
    policy = FederationPolicy()
    pub, _priv = generate_key_pair()
    perms = policy.allowed_for(pub)
    assert "read:public" in perms
    assert "write:prompts" not in perms


def test_federation_policy_can_helper():
    policy = FederationPolicy()
    pub, _priv = generate_key_pair()
    assert policy.can("read:public", pub) is True
    assert policy.can("admin", pub) is False


def test_federation_policy_federation_rule(tmp_path: Path):
    fed_id = "test-fed-id"
    pub, _priv = generate_key_pair()
    yaml_content = f"""
federation:
  default:
    - read:public
  federations:
    - id: "{fed_id}"
      allow:
        - read:unlisted
        - write:prompts
"""
    p = tmp_path / "policy.yaml"
    p.write_text(yaml_content)
    policy = FederationPolicy.from_yaml(p)
    perms = policy.allowed_for(pub, federation_id=fed_id)
    assert "read:public" in perms
    assert "read:unlisted" in perms
    assert "write:prompts" in perms


def test_federation_policy_member_rule(tmp_path: Path):
    pub, _priv = generate_key_pair()
    fingerprint = _key_fingerprint(pub)
    yaml_content = f"""
federation:
  default:
    - read:public
  members:
    - fingerprint: "{fingerprint}"
      allow:
        - read:all
"""
    p = tmp_path / "policy.yaml"
    p.write_text(yaml_content)
    policy = FederationPolicy.from_yaml(p)
    perms = policy.allowed_for(pub)
    assert "read:all" in perms


def test_key_fingerprint_deterministic():
    pub, _priv = generate_key_pair()
    assert _key_fingerprint(pub) == _key_fingerprint(pub)
    assert _key_fingerprint(pub).startswith("sha256:")


def test_federation_policy_unmatched_federation_id(tmp_path):
    """federation_id given but no rule matches → default perms only (branch 101->100)."""
    pub, _priv = generate_key_pair()
    yaml_content = """
federation:
  default:
    - read:public
  federations:
    - id: "fed-aaa"
      allow:
        - write:prompts
"""
    p = tmp_path / "policy.yaml"
    p.write_text(yaml_content)
    policy = FederationPolicy.from_yaml(p)
    # "fed-bbb" exists in the request but is not in the policy → no extra perms
    perms = policy.allowed_for(pub, federation_id="fed-bbb")
    assert "read:public" in perms
    assert "write:prompts" not in perms


def test_federation_policy_unmatched_member_fingerprint(tmp_path):
    """Member rule exists but fingerprint doesn't match → no extra perms (branch 105->104)."""
    pub1, _priv1 = generate_key_pair()
    pub2, _priv2 = generate_key_pair()
    fp1 = _key_fingerprint(pub1)
    yaml_content = f"""
federation:
  default:
    - read:public
  members:
    - fingerprint: "{fp1}"
      allow:
        - read:all
"""
    p = tmp_path / "policy.yaml"
    p.write_text(yaml_content)
    policy = FederationPolicy.from_yaml(p)
    # pub2's fingerprint doesn't match fp1 → member rule not applied
    perms = policy.allowed_for(pub2)
    assert "read:public" in perms
    assert "read:all" not in perms
