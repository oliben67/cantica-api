-- Create "namespaces" table
CREATE TABLE `namespaces` (
  `name` varchar NOT NULL,
  `description` varchar NOT NULL,
  `created_at` varchar NOT NULL,
  PRIMARY KEY (`name`)
);
-- Create "forks" table
CREATE TABLE `forks` (
  `id` varchar NOT NULL,
  `source_slug` varchar NOT NULL,
  `source_sha` varchar NOT NULL,
  `fork_slug` varchar NOT NULL,
  `created_at` varchar NOT NULL,
  PRIMARY KEY (`id`)
);
-- Create "api_keys" table
CREATE TABLE `api_keys` (
  `id` varchar NOT NULL,
  `name` varchar NOT NULL,
  `key_hash` varchar NOT NULL,
  `created_at` varchar NOT NULL,
  `last_used_at` varchar NULL,
  PRIMARY KEY (`id`)
);
-- Create index "api_keys_key_hash" to table: "api_keys"
CREATE UNIQUE INDEX `api_keys_key_hash` ON `api_keys` (`key_hash`);
-- Create "prompts" table
CREATE TABLE `prompts` (
  `id` varchar NOT NULL,
  `namespace` varchar NOT NULL,
  `name` varchar NOT NULL,
  `description` varchar NOT NULL,
  `tags` varchar NOT NULL,
  `model_hints` varchar NOT NULL,
  `license` varchar NOT NULL,
  `visibility` varchar NOT NULL,
  `variables` varchar NOT NULL,
  `star_count` integer NOT NULL,
  `fork_count` integer NOT NULL,
  `default_branch` varchar NOT NULL,
  `created_at` varchar NOT NULL,
  `updated_at` varchar NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `0` FOREIGN KEY (`namespace`) REFERENCES `namespaces` (`name`) ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create index "prompts_namespace_name" to table: "prompts"
CREATE UNIQUE INDEX `prompts_namespace_name` ON `prompts` (`namespace`, `name`);
-- Create "versions" table
CREATE TABLE `versions` (
  `sha` varchar NOT NULL,
  `prompt_id` varchar NOT NULL,
  `branch` varchar NOT NULL,
  `parent_sha` varchar NULL,
  `message` varchar NOT NULL,
  `author` varchar NOT NULL,
  `content_sha` varchar NOT NULL,
  `variables` varchar NOT NULL,
  `created_at` varchar NOT NULL,
  PRIMARY KEY (`sha`),
  CONSTRAINT `0` FOREIGN KEY (`parent_sha`) REFERENCES `versions` (`sha`) ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT `1` FOREIGN KEY (`prompt_id`) REFERENCES `prompts` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create index "idx_versions_prompt_created" to table: "versions"
CREATE INDEX `idx_versions_prompt_created` ON `versions` (`prompt_id`, `created_at`);
-- Create index "idx_versions_prompt_branch" to table: "versions"
CREATE INDEX `idx_versions_prompt_branch` ON `versions` (`prompt_id`, `branch`);
-- Create "tags" table
CREATE TABLE `tags` (
  `prompt_id` varchar NOT NULL,
  `name` varchar NOT NULL,
  `sha` varchar NOT NULL,
  `created_at` varchar NOT NULL,
  PRIMARY KEY (`prompt_id`, `name`),
  CONSTRAINT `0` FOREIGN KEY (`sha`) REFERENCES `versions` (`sha`) ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT `1` FOREIGN KEY (`prompt_id`) REFERENCES `prompts` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "branches" table
CREATE TABLE `branches` (
  `prompt_id` varchar NOT NULL,
  `name` varchar NOT NULL,
  `head_sha` varchar NOT NULL,
  `created_at` varchar NOT NULL,
  `updated_at` varchar NOT NULL,
  PRIMARY KEY (`prompt_id`, `name`),
  CONSTRAINT `0` FOREIGN KEY (`head_sha`) REFERENCES `versions` (`sha`) ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT `1` FOREIGN KEY (`prompt_id`) REFERENCES `prompts` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
);
