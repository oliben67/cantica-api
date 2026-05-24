-- Create "collections" table
CREATE TABLE "collections" (
  "id" TEXT NOT NULL,
  "namespace" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "description" TEXT NOT NULL,
  "created_at" TEXT NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "fk_collections_namespace" FOREIGN KEY ("namespace") REFERENCES "namespaces" ("name")
);
-- Create index "collections_namespace_name" to table: "collections"
CREATE UNIQUE INDEX "collections_namespace_name" ON "collections" ("namespace", "name");
-- Create "stars" table
CREATE TABLE "stars" (
  "id" TEXT NOT NULL,
  "namespace" TEXT NOT NULL,
  "prompt_id" TEXT NOT NULL,
  "created_at" TEXT NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "fk_stars_prompt" FOREIGN KEY ("prompt_id") REFERENCES "prompts" ("id"),
  CONSTRAINT "fk_stars_namespace" FOREIGN KEY ("namespace") REFERENCES "namespaces" ("name")
);
-- Create index "stars_namespace_prompt_id" to table: "stars"
CREATE UNIQUE INDEX "stars_namespace_prompt_id" ON "stars" ("namespace", "prompt_id");
-- Create "comments" table
CREATE TABLE "comments" (
  "id" TEXT NOT NULL,
  "prompt_id" TEXT NOT NULL,
  "version_sha" TEXT NULL,
  "author" TEXT NOT NULL,
  "body" TEXT NOT NULL,
  "created_at" TEXT NOT NULL,
  PRIMARY KEY ("id"),
  CONSTRAINT "fk_comments_prompt" FOREIGN KEY ("prompt_id") REFERENCES "prompts" ("id")
);
-- Create "collection_items" table
CREATE TABLE "collection_items" (
  "collection_id" TEXT NOT NULL,
  "prompt_id" TEXT NOT NULL,
  "added_at" TEXT NOT NULL,
  PRIMARY KEY ("collection_id", "prompt_id"),
  CONSTRAINT "fk_collection_items_prompt" FOREIGN KEY ("prompt_id") REFERENCES "prompts" ("id"),
  CONSTRAINT "fk_collection_items_collection" FOREIGN KEY ("collection_id") REFERENCES "collections" ("id")
);
