-- Create "webhooks" table
CREATE TABLE "webhooks" (
  "id" TEXT NOT NULL,
  "url" TEXT NOT NULL,
  "events" TEXT NOT NULL DEFAULT '["version.created"]',
  "secret" TEXT NOT NULL,
  "namespace" TEXT NULL,
  "created_at" TEXT NOT NULL,
  PRIMARY KEY ("id")
);
