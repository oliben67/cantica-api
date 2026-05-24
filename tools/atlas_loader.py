"""
Atlas DDL provider bridge: prints SQLAlchemy model DDL for Atlas migrations.

This script is invoked by ``task db:new`` (via Atlas's ``composite`` data
source) to generate the current target schema DDL from the SQLAlchemy ORM
models.  Atlas diffs the output against its stored schema state to produce
migration SQL.

Usage (called by Atlas, not directly)::

    python tools/atlas_loader.py

All ORM model classes must be imported before calling ``print_ddl`` so that
they register themselves with ``Base.metadata``.  The ``# noqa: F401`` markers
suppress unused-import warnings on those imports.

See ``Taskfile.yml`` (``db:new`` task) for the full invocation context, and
``tools/atlas_loader.py`` in the project root for the ``atlas.hcl`` config
that wires this script into the Atlas pipeline.
"""

# Future imports (must occur at the beginning of the file):
from __future__ import annotations

# Third party imports:
from atlas_provider_sqlalchemy.ddl import print_ddl

# Local imports:
from cantica.orm.tables import (  # noqa: F401
    ApiKeyOrm,
    BranchOrm,
    ForkOrm,
    NamespaceOrm,
    PromptOrm,
    TagOrm,
    VersionOrm,
)

# All models must be imported above so they register with Base.metadata before
# print_ddl walks the metadata graph.
print_ddl("sqlite", [NamespaceOrm, PromptOrm, VersionOrm, TagOrm, BranchOrm, ForkOrm, ApiKeyOrm])
