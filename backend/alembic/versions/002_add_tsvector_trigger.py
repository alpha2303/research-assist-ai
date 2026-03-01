"""Add tsvector trigger for BM25 search

Revision ID: 002
Revises: 55f174102612
Create Date: 2026-02-28 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '55f174102612'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add trigger to auto-populate search_vector from content on INSERT/UPDATE.

    This uses PostgreSQL's built-in tsvector_update_trigger which automatically
    sets the search_vector column to to_tsvector('english', content) whenever
    a row is inserted or updated.

    Also back-fills any existing rows that have a NULL search_vector.
    """
    # Create the trigger function and trigger
    op.execute("""
        CREATE OR REPLACE FUNCTION document_chunks_search_vector_update()
        RETURNS trigger AS $$
        BEGIN
            NEW.search_vector := to_tsvector('pg_catalog.english', COALESCE(NEW.content, ''));
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER tsvector_update_trigger
        BEFORE INSERT OR UPDATE OF content
        ON document_chunks
        FOR EACH ROW
        EXECUTE FUNCTION document_chunks_search_vector_update();
    """)

    # Back-fill existing rows
    op.execute("""
        UPDATE document_chunks
        SET search_vector = to_tsvector('pg_catalog.english', COALESCE(content, ''))
        WHERE search_vector IS NULL;
    """)


def downgrade() -> None:
    """Remove the tsvector trigger and function."""
    op.execute("DROP TRIGGER IF EXISTS tsvector_update_trigger ON document_chunks;")
    op.execute("DROP FUNCTION IF EXISTS document_chunks_search_vector_update();")
