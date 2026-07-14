-- Disable the enforcement of foreign-keys constraints
PRAGMA foreign_keys = off;
-- Create "new_users" table
CREATE TABLE `new_users` (
  `id` varchar NOT NULL,
  `username` varchar NOT NULL,
  `email` varchar NOT NULL,
  `password_hash` varchar NULL,
  `roles_json` varchar NOT NULL,
  `is_active` integer NOT NULL,
  `e_user_id` varchar NULL,
  `created_at` varchar NOT NULL,
  `updated_at` varchar NOT NULL,
  PRIMARY KEY (`id`)
);
-- Copy rows from old table "users" to new temporary table "new_users"
INSERT INTO `new_users` (`id`, `username`, `email`, `password_hash`, `roles_json`, `is_active`, `created_at`, `updated_at`) SELECT `id`, `username`, `email`, `password_hash`, `roles_json`, `is_active`, `created_at`, `updated_at` FROM `users`;
-- Drop "users" table after copying rows
DROP TABLE `users`;
-- Rename temporary table "new_users" to "users"
ALTER TABLE `new_users` RENAME TO `users`;
-- Create index "users_username" to table: "users"
CREATE UNIQUE INDEX `users_username` ON `users` (`username`);
-- Create index "ix_users_username" to table: "users"
CREATE INDEX `ix_users_username` ON `users` (`username`);
-- Create index "ix_users_e_user_id" to table: "users"
CREATE INDEX `ix_users_e_user_id` ON `users` (`e_user_id`);
-- Create "new_user_invites" table
CREATE TABLE `new_user_invites` (
  `id` varchar NOT NULL,
  `token` varchar NOT NULL,
  `email` varchar NOT NULL,
  `created_by` varchar NOT NULL,
  `expires_at` varchar NOT NULL,
  `used_at` varchar NULL,
  `used_by` varchar NULL,
  `created_at` varchar NOT NULL,
  PRIMARY KEY (`id`)
);
-- Copy rows from old table "user_invites" to new temporary table "new_user_invites"
INSERT INTO `new_user_invites` (`id`, `token`, `email`, `created_by`, `expires_at`, `used_at`, `used_by`, `created_at`) SELECT `id`, `token`, `email`, `created_by`, `expires_at`, `used_at`, `used_by`, `created_at` FROM `user_invites`;
-- Drop "user_invites" table after copying rows
DROP TABLE `user_invites`;
-- Rename temporary table "new_user_invites" to "user_invites"
ALTER TABLE `new_user_invites` RENAME TO `user_invites`;
-- Create index "ix_user_invites_token" to table: "user_invites"
CREATE UNIQUE INDEX `ix_user_invites_token` ON `user_invites` (`token`);
-- Create "used_jtis" table
CREATE TABLE `used_jtis` (
  `jti` varchar NOT NULL,
  `purpose` varchar NOT NULL,
  `expires_at` varchar NOT NULL,
  PRIMARY KEY (`jti`)
);
-- Create "user_flags" table
CREATE TABLE `user_flags` (
  `id` varchar NOT NULL,
  `user_id` varchar NOT NULL,
  `flag` varchar NOT NULL,
  `comment` varchar NOT NULL,
  `created_by` varchar NOT NULL,
  `created_at` varchar NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `0` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON UPDATE NO ACTION ON DELETE CASCADE
);
-- Create index "ix_user_flags_flag" to table: "user_flags"
CREATE INDEX `ix_user_flags_flag` ON `user_flags` (`flag`);
-- Create index "ix_user_flags_user_id" to table: "user_flags"
CREATE INDEX `ix_user_flags_user_id` ON `user_flags` (`user_id`);
-- Create "jwt_keys" table
CREATE TABLE `jwt_keys` (
  `id` varchar NOT NULL,
  `cantica_user_id` varchar NOT NULL,
  `user_id` varchar NOT NULL,
  `public_key` varchar NOT NULL,
  `created_at` varchar NOT NULL,
  `last_used_at` varchar NULL,
  `revoked_at` varchar NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `0` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON UPDATE NO ACTION ON DELETE CASCADE
);
-- Create index "ix_jwt_keys_user_id" to table: "jwt_keys"
CREATE INDEX `ix_jwt_keys_user_id` ON `jwt_keys` (`user_id`);
-- Create index "ix_jwt_keys_cantica_user_id" to table: "jwt_keys"
CREATE INDEX `ix_jwt_keys_cantica_user_id` ON `jwt_keys` (`cantica_user_id`);
-- Enable back the enforcement of foreign-keys constraints
PRAGMA foreign_keys = on;
