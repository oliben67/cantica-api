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
