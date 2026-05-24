-- Create "webhooks" table
CREATE TABLE `webhooks` (
  `id` varchar NOT NULL,
  `url` varchar NOT NULL,
  `events` varchar NOT NULL DEFAULT '["version.created"]',
  `secret` varchar NOT NULL,
  `namespace` varchar NULL,
  `created_at` varchar NOT NULL,
  PRIMARY KEY (`id`)
);
