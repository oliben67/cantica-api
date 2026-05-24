-- Create "collections" table
CREATE TABLE `collections` (
  `id` varchar NOT NULL,
  `namespace` varchar NOT NULL,
  `name` varchar NOT NULL,
  `description` varchar NOT NULL,
  `created_at` varchar NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `0` FOREIGN KEY (`namespace`) REFERENCES `namespaces` (`name`) ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create index "collections_namespace_name" to table: "collections"
CREATE UNIQUE INDEX `collections_namespace_name` ON `collections` (`namespace`, `name`);
-- Create "stars" table
CREATE TABLE `stars` (
  `id` varchar NOT NULL,
  `namespace` varchar NOT NULL,
  `prompt_id` varchar NOT NULL,
  `created_at` varchar NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `0` FOREIGN KEY (`prompt_id`) REFERENCES `prompts` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT `1` FOREIGN KEY (`namespace`) REFERENCES `namespaces` (`name`) ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create index "stars_namespace_prompt_id" to table: "stars"
CREATE UNIQUE INDEX `stars_namespace_prompt_id` ON `stars` (`namespace`, `prompt_id`);
-- Create "comments" table
CREATE TABLE `comments` (
  `id` varchar NOT NULL,
  `prompt_id` varchar NOT NULL,
  `version_sha` varchar NULL,
  `author` varchar NOT NULL,
  `body` varchar NOT NULL,
  `created_at` varchar NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `0` FOREIGN KEY (`prompt_id`) REFERENCES `prompts` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
);
-- Create "collection_items" table
CREATE TABLE `collection_items` (
  `collection_id` varchar NOT NULL,
  `prompt_id` varchar NOT NULL,
  `added_at` varchar NOT NULL,
  PRIMARY KEY (`collection_id`, `prompt_id`),
  CONSTRAINT `0` FOREIGN KEY (`prompt_id`) REFERENCES `prompts` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION,
  CONSTRAINT `1` FOREIGN KEY (`collection_id`) REFERENCES `collections` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
);
