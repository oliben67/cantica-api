-- Create "server_identity" table
CREATE TABLE `server_identity` (
  `id` varchar NOT NULL,
  `public_key_pem` varchar NOT NULL,
  `created_at` varchar NOT NULL,
  PRIMARY KEY (`id`)
);
-- Create "federations" table
CREATE TABLE `federations` (
  `id` varchar NOT NULL,
  `name` varchar NOT NULL,
  `founding_key_enc` varchar NOT NULL,
  `created_at` varchar NOT NULL,
  PRIMARY KEY (`id`)
);
-- Create index "federations_name" to table: "federations"
CREATE UNIQUE INDEX `federations_name` ON `federations` (`name`);
-- Create "federation_members" table
CREATE TABLE `federation_members` (
  `id` varchar NOT NULL,
  `federation_id` varchar NOT NULL,
  `public_key_enc` varchar NOT NULL,
  `federate_url_enc` varchar NOT NULL,
  `is_accepted` integer NOT NULL,
  `joined_at` varchar NOT NULL,
  `updated_at` varchar NOT NULL,
  PRIMARY KEY (`id`),
  CONSTRAINT `0` FOREIGN KEY (`federation_id`) REFERENCES `federations` (`id`) ON UPDATE NO ACTION ON DELETE NO ACTION
);
