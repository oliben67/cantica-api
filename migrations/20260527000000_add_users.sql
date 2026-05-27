-- Add users table for local auth provider.
-- Users can authenticate with username+password; password_hash is NULL
-- for accounts managed by external providers (OIDC, LDAP, etc.).

CREATE TABLE IF NOT EXISTS users (
    id          TEXT PRIMARY KEY,
    username    TEXT NOT NULL UNIQUE,
    email       TEXT NOT NULL DEFAULT '',
    password_hash TEXT,
    roles_json  TEXT NOT NULL DEFAULT '["user"]',
    is_active   INTEGER NOT NULL DEFAULT 1,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
