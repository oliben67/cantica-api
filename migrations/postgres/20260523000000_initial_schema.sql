-- Create "namespaces" table
CREATE TABLE "namespaces" (
  "name" TEXT NOT NULL,
  "description" TEXT NOT NULL,
  "created_at" TEXT NOT NULL,
  PRIMARY KEY ("name")
);
-- Create "forks" table
CREATE TABLE "forks" (
  "id" TEXT NOT NULL,
  "source_slug" TEXT NOT NULL,
  "source_sha" TEXT NOT NULL,
  "fork_slug" TEXT NOT NULL,
  "created_at" TEXT NOT NULL,
  PRIMARY KEY ("id")
);
-- Create "api_keys" table
CREATE TABLE "api_keys" (
  "id" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "key_hash" TEXT NOT NULL,
  "created_at" TEXT NOT NULL,
  "last_used_at" TEXT NULL,
  PRIMARY KEY ("id")
);
-- Create index "api_keys_key_hash" to table: "api_keys"
CREATE UNIQUE INDEX "api_keys_key_hash" ON "api_keys" ("key_hash");
-- Create "prompts" table
CREATE TABLE "prompts" (
  "id" TEXT NOT NULL,
  "namespace" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "description" TEXT NOT NULL,
  "tags" TEXT NOT NULL,
  "model_hints" TEXT NOT NULL,
  "license" TEXT NOT NULL,
  "visibility" TEXT NOT NULL,
  "variables" TEXT NOT NULL,
  "star_count" INTEGER NOT NULL,
  "fork_count" INTEGER NOT NULL,
  "default_branch" TEXT NOT NULL,
  "created_at" TEXT NOT NULL,
  "updated_at" TEXT NOT NULL,
  "search_vector" tsvector,
  PRIMARY KEY ("id"),
  CONSTRAINT "fk_prompts_namespace" FOREIGN KEY ("namespace") REFERENCES "namespaces" ("name")
);
-- Create index "prompts_namespace_name" to table: "prompts"
CREATE UNIQUE INDEX "prompts_namespace_name" ON "prompts" ("namespace", "name");
-- Create GIN index on search_vector
CREATE INDEX "idx_prompts_search_vector" ON "prompts" USING GIN ("search_vector");
-- Create FTS update function
CREATE OR REPLACE FUNCTION _cantica_prompts_tsv() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  NEW.search_vector := to_tsvector('english',
    coalesce(NEW.name, '') || ' ' ||
    coalesce(NEW.description, '') || ' ' ||
    regexp_replace(NEW.tags, '[\[\]"]', ' ', 'g') || ' ' ||
    regexp_replace(NEW.model_hints, '[\[\]"]', ' ', 'g')
  );
  RETURN NEW;
END;
$$;
-- Create FTS trigger
CREATE TRIGGER trg_prompts_tsv
  BEFORE INSERT OR UPDATE ON "prompts"
  FOR EACH ROW EXECUTE FUNCTION _cantica_prompts_tsv();
-- Create "versions" table
CREATE TABLE "versions" (
  "sha" TEXT NOT NULL,
  "prompt_id" TEXT NOT NULL,
  "branch" TEXT NOT NULL,
  "parent_sha" TEXT NULL,
  "message" TEXT NOT NULL,
  "author" TEXT NOT NULL,
  "content_sha" TEXT NOT NULL,
  "variables" TEXT NOT NULL,
  "created_at" TEXT NOT NULL,
  PRIMARY KEY ("sha"),
  CONSTRAINT "fk_versions_parent" FOREIGN KEY ("parent_sha") REFERENCES "versions" ("sha"),
  CONSTRAINT "fk_versions_prompt" FOREIGN KEY ("prompt_id") REFERENCES "prompts" ("id")
);
-- Create index "idx_versions_prompt_created" to table: "versions"
CREATE INDEX "idx_versions_prompt_created" ON "versions" ("prompt_id", "created_at");
-- Create index "idx_versions_prompt_branch" to table: "versions"
CREATE INDEX "idx_versions_prompt_branch" ON "versions" ("prompt_id", "branch");
-- Create "tags" table
CREATE TABLE "tags" (
  "prompt_id" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "sha" TEXT NOT NULL,
  "created_at" TEXT NOT NULL,
  PRIMARY KEY ("prompt_id", "name"),
  CONSTRAINT "fk_tags_sha" FOREIGN KEY ("sha") REFERENCES "versions" ("sha"),
  CONSTRAINT "fk_tags_prompt" FOREIGN KEY ("prompt_id") REFERENCES "prompts" ("id")
);
-- Create "branches" table
CREATE TABLE "branches" (
  "prompt_id" TEXT NOT NULL,
  "name" TEXT NOT NULL,
  "head_sha" TEXT NOT NULL,
  "created_at" TEXT NOT NULL,
  "updated_at" TEXT NOT NULL,
  PRIMARY KEY ("prompt_id", "name"),
  CONSTRAINT "fk_branches_head" FOREIGN KEY ("head_sha") REFERENCES "versions" ("sha"),
  CONSTRAINT "fk_branches_prompt" FOREIGN KEY ("prompt_id") REFERENCES "prompts" ("id")
);
