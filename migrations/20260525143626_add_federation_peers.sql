-- Create "federation_peers" table
CREATE TABLE `federation_peers` (
  `id` varchar NOT NULL,
  `name` varchar NOT NULL,
  `url` varchar NOT NULL,
  `api_key` varchar NULL,
  `added_at` varchar NOT NULL,
  PRIMARY KEY (`id`)
);
-- Create index "federation_peers_name" to table: "federation_peers"
CREATE UNIQUE INDEX `federation_peers_name` ON `federation_peers` (`name`);
