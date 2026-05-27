-- One-time invite tokens for admin-initiated user registration.

CREATE TABLE IF NOT EXISTS user_invites (
    id          TEXT PRIMARY KEY,
    token       TEXT NOT NULL UNIQUE,
    email       TEXT NOT NULL DEFAULT '',
    created_by  TEXT NOT NULL,
    expires_at  TEXT NOT NULL,
    used_at     TEXT,
    used_by     TEXT,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_user_invites_token ON user_invites(token);
