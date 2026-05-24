# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
import pytest

# Local imports:
from cantica.core.resolver import PromptAddress, parse_address


def test_simple_slug() -> None:
    addr = parse_address("osteck/my-prompt")
    assert addr.namespace == "osteck"
    assert addr.name == "my-prompt"
    assert addr.ref == "latest"
    assert addr.host is None


def test_slug_with_ref() -> None:
    addr = parse_address("osteck/my-prompt@v2.1")
    assert addr.ref == "v2.1"


def test_slug_with_sha_prefix() -> None:
    addr = parse_address("osteck/my-prompt@abc123f")
    assert addr.ref == "abc123f"


def test_cantica_uri_no_ref() -> None:
    addr = parse_address("cantica://osteck/my-prompt")
    assert addr.namespace == "osteck"
    assert addr.name == "my-prompt"
    assert addr.ref == "latest"
    assert addr.host is None


def test_cantica_uri_with_ref() -> None:
    addr = parse_address("cantica://osteck/my-prompt@v1.4")
    assert addr.ref == "v1.4"
    assert addr.host is None


def test_cantica_uri_with_host() -> None:
    addr = parse_address("cantica://cantica.dev/community/architect@v1.4")
    assert addr.host == "cantica.dev"
    assert addr.namespace == "community"
    assert addr.name == "architect"
    assert addr.ref == "v1.4"


def test_str_representation() -> None:
    addr = PromptAddress(namespace="osteck", name="my-prompt", ref="v1.0")
    assert str(addr) == "cantica://osteck/my-prompt@v1.0"


def test_str_with_host() -> None:
    addr = PromptAddress(namespace="community", name="arch", ref="stable", host="cantica.dev")
    assert str(addr) == "cantica://cantica.dev/community/arch@stable"


def test_slug_property() -> None:
    addr = PromptAddress(namespace="osteck", name="my-prompt")
    assert addr.slug == "osteck/my-prompt"


def test_invalid_no_slash() -> None:
    with pytest.raises(ValueError):
        parse_address("no-slash-here")


def test_invalid_too_many_parts_non_uri() -> None:
    with pytest.raises(ValueError):
        parse_address("a/b/c")


def test_invalid_cantica_uri_extra_parts() -> None:
    with pytest.raises(ValueError):
        parse_address("cantica://a/b/c/d")
