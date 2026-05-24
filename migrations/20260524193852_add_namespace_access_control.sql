-- Disable the enforcement of foreign-keys constraints
PRAGMA foreign_keys = off;
-- Add column "is_proprietary" to table: "namespaces"
ALTER TABLE `namespaces` ADD COLUMN `is_proprietary` integer NOT NULL;
-- Add column "encoded" to table: "namespaces"
ALTER TABLE `namespaces` ADD COLUMN `encoded` integer NOT NULL;
-- Add column "encryption_key" to table: "namespaces"
ALTER TABLE `namespaces` ADD COLUMN `encryption_key` varchar NULL;
-- Add column "is_encoded" to table: "versions"
ALTER TABLE `versions` ADD COLUMN `is_encoded` integer NOT NULL;
-- Create "new_webhooks" table
CREATE TABLE `new_webhooks` (
  `id` varchar NOT NULL,
  `url` varchar NOT NULL,
  `events` varchar NOT NULL,
  `secret` varchar NOT NULL,
  `namespace` varchar NULL,
  `created_at` varchar NOT NULL,
  PRIMARY KEY (`id`)
);
-- Copy rows from old table "webhooks" to new temporary table "new_webhooks"
INSERT INTO `new_webhooks` (`id`, `url`, `events`, `secret`, `namespace`, `created_at`) SELECT `id`, `url`, `events`, `secret`, `namespace`, `created_at` FROM `webhooks`;
-- Drop "webhooks" table after copying rows
DROP TABLE `webhooks`;
-- Rename temporary table "new_webhooks" to "webhooks"
ALTER TABLE `new_webhooks` RENAME TO `webhooks`;
-- Create "instance_config" table
CREATE TABLE `instance_config` (
  `key` varchar NOT NULL,
  `value` varchar NOT NULL,
  PRIMARY KEY (`key`)
);
-- Create "namespace_certs" table
CREATE TABLE `namespace_certs` (
  `id` varchar NOT NULL,
  `namespace` varchar NOT NULL,
  `granted_to` varchar NOT NULL,
  `issued_at` varchar NOT NULL,
  `expires_at` varchar NULL,
  `revoked` integer NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `0` FOREIGN KEY (`namespace`) REFERENCES `namespaces` (`name`) ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Enable back the enforcement of foreign-keys constraints
PRAGMA foreign_keys = on;
