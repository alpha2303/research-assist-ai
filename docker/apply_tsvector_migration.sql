-- Apply migration 002: Add tsvector trigger for BM25 search
-- This migration was missed during initial setup

CREATE OR REPLACE FUNCTION document_chunks_search_vector_update()
RETURNS trigger AS $$
BEGIN
    NEW.search_vector := to_tsvector('pg_catalog.english', COALESCE(NEW.content, ''));
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tsvector_update_trigger
BEFORE INSERT OR UPDATE OF content
ON document_chunks
FOR EACH ROW
EXECUTE FUNCTION document_chunks_search_vector_update();

-- Back-fill existing rows
UPDATE document_chunks
SET search_vector = to_tsvector('pg_catalog.english', COALESCE(content, ''))
WHERE search_vector IS NULL;

-- Update alembic version to reflect this migration
UPDATE alembic_version SET version_num = '002';
