-- PostgreSQL initialization script for Research Assist AI
-- This script runs automatically when the PostgreSQL container is first created

-- Enable the pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify the extension was created
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Create the database (if it doesn't exist - Docker already creates it)
-- But we can add any additional initialization here

COMMENT ON EXTENSION vector IS 'Vector similarity search extension for PostgreSQL';
