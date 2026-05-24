# atlas.hcl — Atlas migration configuration for Cantica
# https://atlasgo.io/guides/orms/sqlalchemy/script
#
# Usage:
#   atlas migrate diff --env sqlalchemy          # plan a new migration
#   atlas migrate apply --env sqlalchemy         # apply to local dev DB
#   atlas migrate apply --env sqlalchemy \
#     --url "sqlite:///path/to/prod.db"          # apply to a specific DB
#   atlas migrate status --env sqlalchemy        # show pending migrations
#   atlas migrate lint --env sqlalchemy          # lint for destructive changes

data "external_schema" "sqlalchemy" {
  # Python script mode: runs inside the project virtualenv so that all
  # cantica.* imports resolve correctly.
  program = [
    "uv", "run", "python", "tools/atlas_loader.py",
  ]
}

env "sqlalchemy" {
  # Desired schema is read from the SQLAlchemy models via the loader script.
  src = data.external_schema.sqlalchemy.url

  # Dev database: a temporary SQLite file Atlas uses to plan migrations
  # (never contains real data — gitignored via .copilot exclusion).
  dev = "sqlite://atlas-dev.db"

  migration {
    dir = "file://migrations"
  }

  format {
    migrate {
      diff = "{{ sql . \"  \" }}"
    }
  }
}

env "postgres" {
  # Desired schema is read from the same SQLAlchemy models.
  src = data.external_schema.sqlalchemy.url

  # Dev database: a local PostgreSQL instance (requires Docker or local Postgres).
  # Override via ATLAS_POSTGRES_URL env var:
  #   export ATLAS_POSTGRES_URL="postgres://cantica:secret@localhost:5432/cantica_dev?sslmode=disable"
  dev = var.postgres_url

  migration {
    dir = "file://migrations/postgres"
  }

  format {
    migrate {
      diff = "{{ sql . \"  \" }}"
    }
  }
}

variable "postgres_url" {
  type    = string
  default = "postgres://cantica:secret@localhost:5432/cantica_dev?sslmode=disable"
}
