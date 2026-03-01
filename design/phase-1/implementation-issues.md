# Implementation Issues and Resolutions

> **Last Updated**: 2026-03-01\n>\n> This document tracks issues encountered during development", "oldString": "> **Last Updated**: 2026-02-21\n>\n> This document tracks issues encountered during development, their root causes, and resolutions for future reference.

---

## Table of Contents

- [Phase 1 Issues](#phase-1-issues)
- [Phase 2 Issues](#phase-2-issues)
- [Phase 3 Issues](#phase-3-issues)
- [Phase 4 Issues](#phase-4-issues)
- [Phase 6 Issues](#phase-6-issues)
- [Post-Deployment Issues](#post-deployment-issues)

---

## Phase 1 Issues

No significant issues encountered during Phase 1.

---

## Phase 2 Issues

### Issue: Database Migration Failed - Missing uuid-ossp Extension

**Cause:**
- PostgreSQL requires explicit installation of the `uuid-ossp` extension
- The extension was not enabled in the database before running migrations
- Alembic migration tried to use `uuid_generate_v4()` without the extension

**Resolution:**
- Added extension installation to Alembic migration:
  ```python
  op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
  ```
- Placed this before any table creation that uses UUID defaults
- Alternative: Use `gen_random_uuid()` which is built-in to PostgreSQL 13+

---

### Issue: pgvector Extension Not Available

**Cause:**
- pgvector extension not installed in the PostgreSQL container
- Standard PostgreSQL Docker image doesn't include pgvector

**Resolution:**
- Used `pgvector/pgvector:pg16` Docker image instead of standard `postgres:16`
- Added to docker-compose.yml:
  ```yaml
  postgres:
    image: pgvector/pgvector:pg16
  ```
- Enabled extension in migration:
  ```python
  op.execute('CREATE EXTENSION IF NOT EXISTS vector')
  ```

---

## Phase 3 Issues

### Issue: SQLAlchemy Tests Failed - "vector has no default operator class for access method hnsw"

**Cause:**
- HNSW index creation requires explicit operator class specification for pgvector
- SQLAlchemy Index definition was missing the `postgresql_ops` parameter
- pgvector doesn't have a default operator class for HNSW indexes

**Resolution:**
- Added explicit operator class to HNSW index definition:
  ```python
  Index(
      "idx_chunks_embedding_hnsw",
      "embedding",
      postgresql_using="hnsw",
      postgresql_ops={"embedding": "vector_cosine_ops"}
  )
  ```
- Available operator classes: `vector_cosine_ops`, `vector_l2_ops`, `vector_ip_ops`

**Reference:** pgvector documentation on index types and operator classes

---

### Issue: AsyncClient TypeError - "unexpected keyword argument 'app'"

**Cause:**
- httpx `AsyncClient` API changed in recent versions
- Direct `app=` parameter no longer supported
- Need to use `ASGITransport` wrapper for ASGI applications

**Resolution:**
- Updated test fixture to use `ASGITransport`:
  ```python
  from httpx import AsyncClient, ASGITransport
  
  async with AsyncClient(
      transport=ASGITransport(app=app),
      base_url="http://test"
  ) as client:
      yield client
  ```
- This is the correct pattern for testing FastAPI apps with httpx

**Reference:** httpx documentation on testing ASGI applications

---

### Issue: AttributeError - 'Project' object has no attribute 'documents'

**Cause:**
- SQLAlchemy relationship not defined on both sides of many-to-many relationship
- Used explicit association table (`project_documents`) but didn't configure relationships properly
- Without `viewonly=True`, SQLAlchemy tried to manage the relationship through the association table

**Resolution:**
- Added `viewonly=True` to both sides of the relationship:
  ```python
  # In Project model
  documents = relationship(
      "Document",
      secondary="project_documents",
      viewonly=True
  )
  
  # In Document model
  projects = relationship(
      "Project",
      secondary="project_documents",
      viewonly=True
  )
  ```
- This tells SQLAlchemy we're managing the association table directly
- Prevents cascade issues and gives explicit control over linking/unlinking

**Best Practice:** For many-to-many with additional metadata on the association (like timestamps), use explicit association table with viewonly relationships

---

### Issue: TypeScript Build Errors - "An import path can only end with a '.ts' extension"

**Cause:**
- `verbatimModuleSyntax: true` in tsconfig.json enforces strict import syntax
- Type imports must use `import type { ... }` syntax
- Regular imports used for types were causing compilation errors

**Resolution:**
- Changed all type-only imports to use explicit `type` keyword:
  ```typescript
  // Before
  import { Project } from './types';
  
  // After
  import type { Project } from './types';
  ```
- Updated all component files to use type-only imports consistently
- This improves build performance and makes the distinction between runtime and type imports clear

**Best Practice:** Always use `import type` for TypeScript types and interfaces when `verbatimModuleSyntax` is enabled

---

### Issue: React useEffect Missing Dependency Warning

**Cause:**
- `loadProjects` function used in useEffect was not memoized
- Function recreated on every render, causing infinite re-render loop
- React's exhaustive-deps rule requires all dependencies to be listed

**Resolution:**
- Wrapped `loadProjects` in `useCallback` with proper dependencies:
  ```typescript
  const loadProjects = useCallback(async () => {
    // Implementation
  }, [dispatch]);
  
  useEffect(() => {
    loadProjects();
  }, [loadProjects]);
  ```
- This ensures function identity is stable unless dependencies change
- Prevents unnecessary re-renders and infinite loops

**Best Practice:** Always wrap async functions used in useEffect with useCallback

---

### Issue: CreateProjectModal Not Visible After Button Click

**Cause:**
- Tailwind CSS v4 syntax mismatch in index.css
- Used old v3 directives (`@tailwind base/components/utilities`) instead of v4 syntax
- PostCSS plugin was `@tailwindcss/postcss` (v4) but CSS used v3 syntax
- This caused Tailwind utilities to not be generated, leading to incorrect CSS values

**Resolution:**
- Updated index.css to use Tailwind v4 syntax:
  ```css
  /* Before (v3 syntax) */
  @tailwind base;
  @tailwind components;
  @tailwind utilities;
  
  /* After (v4 syntax) */
  @import "tailwindcss";
  ```
- Modal became visible immediately after hot reload
- All Tailwind utilities now working correctly

**Debug Process:**
1. Added console.log to verify state changes (confirmed state was updating)
2. Checked React DevTools Elements tab (confirmed div was in DOM)
3. Inspected computed styles (found incorrect inset values)
4. Identified Tailwind configuration mismatch

**Best Practice:** When using Tailwind CSS v4 with `@tailwindcss/postcss` plugin, always use `@import "tailwindcss"` syntax

---

### Issue: Modal Rendering Inside Nested Layout (Initial Attempt)

**Cause:**
- Modal rendered inside component hierarchy was subject to parent's z-index stacking context
- Layout containers with overflow or transform properties create new stacking contexts
- Modal backdrop couldn't cover entire viewport when rendered inside nested divs

**Resolution:**
- Used React Portal to render modal at document.body level:
  ```typescript
  import { createPortal } from 'react-dom';
  
  return createPortal(
    <div className="fixed inset-0 z-50">{/* modal content */}</div>,
    document.body
  );
  ```
- This ensures modal is always at the top level of DOM hierarchy
- z-index now works correctly relative to entire page

**Best Practice:** Always use React Portals for modals, tooltips, and other overlay components that need to escape parent stacking context

---

## Phase 4 Issues

### Issue: SQLAlchemy Column Direct Assignment Not Allowed

**Cause:**
- Attempted to directly assign values to SQLAlchemy Column objects
- Column objects are descriptors, not actual attributes
- Type checker correctly identified this as incompatible with Column type

**Resolution:**
- Changed from direct attribute assignment to UPDATE statement:
  ```python
  # Before (incorrect)
  document.status = status
  document.error_message = error_message
  
  # After (correct)
  stmt = update(Document).where(Document.id == document_id).values(
      status=status,
      error_message=error_message
  )
  result = await session.execute(stmt)
  ```
- This is the proper way to update records in async SQLAlchemy
- Avoids issues with session state and type checking

**Best Practice:** Use UPDATE statements for updating records in async SQLAlchemy, not direct attribute assignment

---

### Issue: Import Error - 'get_session' Not Found in db.session

**Cause:**
- Function `get_session` was in `app.db.base` module
- Import statement incorrectly referenced `app.db.session` which doesn't exist
- This was a simple module location error

**Resolution:**
- Updated import statement:
  ```python
  # Before
  from app.db.session import get_session
  
  # After
  from app.db.base import get_session
  ```

---

### Issue: TypeScript verbatimModuleSyntax Error with DragEvent Import

**Cause:**
- `verbatimModuleSyntax: true` in tsconfig.json requires explicit type imports
- `DragEvent` is a type, not a runtime value
- Importing it as a regular import caused compilation error

**Resolution:**
- Changed to type-only import:
  ```typescript
  // Before
  import { useState, useRef, DragEvent } from 'react';
  
  // After
  import { useState, useRef } from 'react';
  import type { DragEvent } from 'react';
  ```

**Best Practice:** When using `verbatimModuleSyntax`, always use `import type` for TypeScript types

---

### Issue: apiClient Import Using Named Export Instead of Default

**Cause:**
- `client.ts` exports `apiClient` as default export
- Import statement used named import syntax `{ apiClient }`
- This mismatch caused module not found error

**Resolution:**
- Changed to default import:
  ```typescript
  // Before
  import { apiClient } from './client';
  
  // After
  import apiClient from './client';
  ```

---

### Issue: pymupdf4llm.to_markdown() Return Type Mismatch

**Cause:**
- pymupdf4llm library can return different types depending on version
- Could be `str`, `dict`, or `list[dict]`
- Type checker flagged `.get()` method call on what it inferred as a list

**Resolution:**
- Added explicit type checking for all possible return types:
  ```python
  result = pymupdf4llm.to_markdown(str(file_path))
  
  if isinstance(result, str):
      markdown_text = result
      metadata: dict[str, Any] = {}
  elif isinstance(result, dict):
      markdown_text = result.get("output", "")
      metadata = result.get("metadata", {})
  else:
      # Handle list or other types
      markdown_text = str(result)
      metadata = {}
  ```
- This handles all versions of the library gracefully

**Best Practice:** When using third-party libraries with inconsistent return types, add explicit type checking

---

### Issue: PdfPlumber Page Dimensions Type Incompatibility

**Cause:**
- PdfPlumber's `page.width` and `page.height` return numeric types (likely Decimal or custom numeric)
- PageContent metadata requires `dict[str, str | int | float]`
- Type parameter is invariant, so exact type match required

**Resolution:**
- Explicitly converted to float with type annotation:
  ```python
  page_metadata: dict[str, str | int | float] = {
      "width": float(page.width),
      "height": float(page.height),
  }
  ```
- Added explicit type annotation to satisfy type checker

**Best Practice:** When dealing with library-specific numeric types, explicitly convert to standard Python types

---

### Issue: SQLAlchemy Result.rowcount Attribute Not Recognized

**Cause:**
- Type checker doesn't recognize `rowcount` attribute on `Result[Any]`
- This is a known limitation with SQLAlchemy's type stubs
- `rowcount` is a standard attribute on cursor result objects

**Resolution:**
- Added type ignore comment:
  ```python
  return result.rowcount if result.rowcount is not None else 0  # type: ignore[attr-defined]
  ```
- This is safe because rowcount is guaranteed to exist on DELETE result objects

**Best Practice:** Use `type: ignore[attr-defined]` for known SQLAlchemy stub limitations

---

### Issue: Unused projectId Prop in DocumentListItem

**Cause:**
- Initially designed component to accept `projectId` prop
- During implementation, realized it wasn't needed
- Forgot to remove from component signature

**Resolution:**
- Removed unused prop from component:
  ```typescript
  // Removed projectId from Props interface and component signature
  interface Props {
    document: Document;
    onDelete: (documentId: string) => void;
    onStatusUpdate: (documentId: string) => void;
  }
  ```

**Best Practice:** Regularly review component props and remove unused ones to keep interfaces clean

---

### Issue: AppState and AppAction Missing Document Fields

**Cause:**
- Created document management components but forgot to update type definitions
- AppState didn't have `documents` array field
- AppAction union type didn't include document-related actions

**Resolution:**
- Updated type definitions in one place:
  ```typescript
  export interface AppState {
    projects: Project[];
    selectedProjectId: string | null;
    selectedChatId: string | null;
    documents: Document[];  // Added
    isLoading: boolean;
    error: string | null;
  }
  
  export type AppAction =
    | { type: 'SET_PROJECTS'; payload: Project[] }
    // ... other actions ...
    | { type: 'SET_DOCUMENTS'; payload: Document[] }  // Added
    | { type: 'ADD_DOCUMENT'; payload: Document }     // Added
    | { type: 'UPDATE_DOCUMENT'; payload: Document }  // Added
    | { type: 'REMOVE_DOCUMENT'; payload: string }    // Added
    | { type: 'SET_LOADING'; payload: boolean }
    | { type: 'SET_ERROR'; payload: string | null };
  ```

**Best Practice:** Update type definitions before implementing new features to catch interface mismatches early

---

## Phase 4 Unit Testing Status

> **Last Updated**: 2026-02-21
> **Test Framework**: pytest 9.0.2, pytest-asyncio 1.3.0, httpx 0.28.1
> **Execution**: `$env:DATABASE_URL="postgresql+asyncpg://..."; uv run pytest tests/`

### Test Coverage Summary

**Overall Status**: 76/158 tests passing (48% pass rate)
- ✅ **Passing Suites**: Chunking (16/16), Titan Embedding (14/14)
- ⚠️ **Partial Pass**: Document Repo, Chunk Repo, PDF Parsers, Document Tasks, Documents Router
- ❌ **Failing Suites**: Storage Service, PGVector Store, Document Service

### Test Files Created

| Test File | Test Count | Status | Key Issues |
|-----------|------------|--------|------------|
| `test_storage_service.py` | 16 tests | 8 failed | Settings/config mismatch, S3 bucket name hardcoded |
| `test_document_repo.py` | 17 tests | Mostly passing | Minor async session mock issues |
| `test_chunk_repo.py` | 13 tests | Mostly passing | - |
| `test_document_service.py` | 15 tests | 15 errors | Missing `settings` parameter in fixture |
| `test_chunking_service.py` | 16 tests | ✅ All passing | Fixed: RecursiveCharacterSplitter → TextChunker, chunk.text → chunk.content |
| `test_pdf_parsers.py` | 30 tests | Mostly passing | - |
| `test_titan_embedding.py` | 14 tests | ✅ All passing | Fixed: Made all tests async, added await, fixed mock signatures |
| `test_pgvector_store.py` | 17 tests | 17 failed | Method signature mismatches, missing methods |
| `test_documents_router.py` | 16 tests | Some passing | Dependency on failing services |
| `test_document_tasks.py` | 13 tests | Some passing | Celery task mocking issues |

### Known Issues and Fixes Needed

#### 1. Storage Service Tests (8 failures)

**Issue**: Test fixtures create `StorageService` with test config, but implementation reads from global `Settings`

**Failures**:
- `test_upload_file_success`: Returns tuple instead of string (hash computed but not in original design)
- `test_upload_file_with_metadata`: Unexpected `metadata` parameter
- `test_upload_file_s3_error`: Exception wrapped in RuntimeError instead of propagating ClientError
- `test_download_file_*`: Takes 2 args but 3 given (signature mismatch)
- `test_delete_file_success`: Bucket name mismatch (expects 'test-bucket', gets 'research-assist-documents-dev')
- `test_generate_presigned_url_success`: Same bucket name issue
- `test_file_exists_true`: Same bucket name issue

**Root Cause**:
```python
# Test fixture:
storage_service = StorageService(
    bucket_name="test-bucket",
    settings=mock_settings
)

# But StorageService.__init__ might be:
def __init__(self):
    self.settings = get_settings()  # Reads global config
```

**Fix Required**: 
- Update `StorageService` to accept settings via dependency injection
- Or update tests to mock `get_settings()` globally

#### 2. PGVector Store Tests (17 failures)

**Issue**: Method signatures and available methods don't match test expectations

**Failures**:
- `store_embeddings()`: Missing `chunks` parameter
- `similarity_search()`: No `k` parameter (expects different signature)
- `hybrid_search()`: No `k` parameter
- `count_by_document`: Method doesn't exist (expected `count_embeddings`)
- `update_embedding`: Method doesn't exist  
- `get_chunks_by_document`: Method doesn't exist
- `delete_by_document_id`: Returns AsyncMock instead of integer rowcount

**Root Cause**: Tests written against interface specification, but implementation has different method signatures

**Fix Required**:
- Review actual `PGVectorStore` implementation method signatures
- Update tests to match actual implementation
- Or update implementation to match interface specification

#### 3. Document Service Tests (17 errors)

**Issue**: Fixture initialization missing required parameter

**Error**: `TypeError: DocumentService.__init__() missing 1 required positional argument: 'settings'`

**Root Cause**:
```python
# Test fixture:
@pytest.fixture
def document_service(mock_storage_service, mock_document_repo):
    return DocumentService(
        storage_service=mock_storage_service,
        document_repository=mock_document_repo
        # Missing: settings parameter
    )
```

**Fix Required**: Add `settings` parameter to fixture:
```python
@pytest.fixture
def document_service(mock_storage_service, mock_document_repo, mock_settings):
    return DocumentService(
        storage_service=mock_storage_service,
        document_repository=mock_document_repo,
        settings=mock_settings
    )
```

### Successfully Fixed Issues

#### Issue: RecursiveCharacterSplitter Class Not Found

**Cause**: Tests referenced non-existent `RecursiveCharacterSplitter` class when actual implementation uses `TextChunker`

**Resolution**:
- Removed entire `TestRecursiveCharacterSplitter` test class (60+ lines)
- Rewrote tests to use `TextChunker` with `ChunkingConfig`
- Fixed fixture: `ChunkingConfig(chunk_size_tokens=800, overlap_tokens=150, split_separators=[...])`

#### Issue: TextChunk Attribute Name Mismatch

**Cause**: Tests accessed `chunk.text` but actual dataclass field is `chunk.content`

**Resolution**: Changed all references from `chunk.text` → `chunk.content` in 4 test methods

#### Issue: Async/Await Missing in Titan Embedding Tests

**Cause**: `embed_text()` and `embed_batch()` are async coroutines but tests weren't async

**Resolution**:
- Converted 12 test methods from `def test_` → `async def test_`
- Added `await` before all `titan_provider.embed_text()` and `titan_provider.embed_batch()` calls
- Fixed mock function signatures to accept `**kwargs` for `contentType` parameter
- Changed exception expectations from `ClientError` → `RuntimeError` (implementation wraps exceptions)
- Changed `patch('time.sleep')` → `patch('asyncio.sleep')` for retry tests

#### Issue: ChunkingConfig Field Names

**Cause**: Test fixture used wrong field names: `chunk_size`, `chunk_overlap`, `separators`

**Resolution**: Fixed to match actual config: `chunk_size_tokens`, `overlap_tokens`, `split_separators`

#### Issue: Chunking Service Method Name

**Cause**: Test called `chunk_pages()` but actual method is `chunk_document_pages()`

**Resolution**: Updated test to use correct method name with correct signature (list of tuples instead of PageContent objects)

### Testing Best Practices Learned

1. **Always verify implementation before writing tests** - Check actual method signatures, parameter names, and return types
2. **Async tests require pytest-asyncio** - Mark functions as `async def` and use `await` for coroutines
3. **Mock signatures must match actual calls** - Use `**kwargs` in mock functions to accept unexpected keyword arguments
4. **Exception wrapping changes test assertions** - If implementation wraps exceptions, test for the wrapper not the original
5. **Configuration injection** - Services should accept config via DI, not read global settings, for testability
6. **Dataclass field names** - Use actual field names from dataclass definitions, not assumed names

### Next Steps to Achieve 100% Pass Rate

1. **Fix Storage Service** (Priority: High)
   - Update `StorageService.__init__` to accept `settings` parameter
   - Update all S3 operations to use `self.settings.bucket_name`
   - Review return value expectations (hash vs S3 key)

2. **Fix Document Service** (Priority: High)
   - Add `settings` parameter to test fixture
   - Verify all mocked dependencies are correctly configured

3. **Fix PGVector Store** (Priority: Medium)
   - Compare test expectations with actual implementation
   - Update method signatures or tests to align
   - Add missing methods if required by interface

4. **Run full test suite** (Priority: Medium)
   - Execute: `uv run pytest tests/ -v --cov=app --cov-report=html`
   - Target: 80%+ code coverage for Phase 4 components

5. **Integration testing** (Priority: Low)
   - Create end-to-end test: Upload PDF → Process → Verify chunks in vector store
   - Test full Celery pipeline with actual services

---

## General Patterns and Lessons Learned

### Testing Patterns

- **Async Tests**: Always use `pytest-asyncio` for async functions, mark tests with `@pytest.mark.asyncio` (or use `pytest.ini` config)
- **Database Testing**: Create and drop tables per test for proper isolation, or use transaction rollback
- **API Testing**: Use `httpx.AsyncClient` with `ASGITransport` for FastAPI testing
- **Mocking**: Use dependency override in FastAPI for swapping out database sessions in tests

### SQLAlchemy Patterns

- **Relationships**: Use `viewonly=True` for many-to-many when using explicit association tables
- **Indexes**: Always specify operator class for pgvector indexes
- **Async**: Use `async with session.begin()` for transactions, always await queries

### React Patterns

- **State Management**: Context + useReducer works well for moderate complexity
- **Modals**: Always use Portals to avoid z-index issues
- **Effects**: Wrap async functions in useCallback before using in useEffect
- **Imports**: Use `import type` for types when `verbatimModuleSyntax` is enabled

### CSS Patterns

- **Tailwind v4**: Use `@import "tailwindcss"` not `@tailwind` directives
- **PostCSS**: Configure with `@tailwindcss/postcss` plugin for v4
- **Debugging**: Use browser DevTools to inspect computed styles and identify missing utilities

---

## Issue Template

```markdown
### Issue: [Short Title]

**Cause:**
- Point 1
- Point 2

**Resolution:**
- Step 1
- Step 2
- Code example if applicable

**Best Practice:** [Optional - general lesson learned]
```

---

## Phase 6 Issues

### Issue: Error Handling Gaps Across RAG Pipeline (6.2.2 / 6.2.3 / 6.2.4)

**Cause:**
- `ChatService.process_user_message_stream()` had a single bare `except Exception` that swallowed all errors into SSE events **without logging** — no server-side record of failures.
- `ChatService.process_user_message()` (non-streaming) had **zero error handling** — any downstream failure resulted in an unstructured 500.
- `RetrievalService` and `ConversationMemory` had no try/except blocks — embedding errors, DynamoDB timeouts, and vector search failures propagated uncaught.
- `ChatRepository.get_chat_session()`, `update_chat_session()`, and `delete_chat_session()` caught all `ClientError` generically and silently returned `None` / `False`, making it impossible to distinguish "item not found" from "DynamoDB is down".
- `StorageService` had correct `ClientError` translation to domain exceptions but no retry logic for transient S3 errors (5xx, `SlowDown`, `RequestTimeout`).
- Chats router had no `try/except` around DynamoDB calls — `ClientError` from `list_chat_sessions`, `create_chat_session`, `delete_*`, `get_messages` would trigger the global 500 handler instead of an informative 503.

**Resolution:**

**Bedrock failure handling (6.2.2):**
- `ChatService` streaming path now catches `ClientError`, `EndpointConnectionError`, and `RuntimeError` separately from the LLM streaming step, classifying errors by AWS error code (`ThrottlingException` → "high demand"; `AccessDeniedException` → "configuration issue"; `ServiceUnavailableException` → "temporarily unavailable").
- Non-streaming path raises a new `ServiceUnavailableError` for transient Bedrock failures.
- Retrieval failures degrade gracefully (empty context) instead of aborting the stream.
- Conversation memory failures degrade gracefully (empty history) with fallback to raw recent messages.

**S3 failure handling (6.2.3):**
- Added `_retry_s3()` helper to `StorageService` with exponential backoff (3 attempts, 1s base delay) for transient S3 error codes: `InternalError`, `ServiceUnavailable`, `SlowDown`, `RequestTimeout`, `RequestTimeTooSkewed`, and any HTTP 5xx.
- All S3 methods now log errors with `logger.error()`/`logger.warning()` before re-raising.

**DynamoDB failure handling (6.2.4):**
- `ChatRepository`: `get_chat_session()`, `update_chat_session()`, `delete_chat_session()` now distinguish `ResourceNotFoundException` (return `None`/`False`) from other `ClientError`s (log and re-raise). `delete_chat_messages()` logs per-item failures.
- Chats router: all DynamoDB-calling endpoints wrapped in `try/except (ClientError, EndpointConnectionError)` returning 503 with "Chat service is temporarily unavailable".
- `ConversationMemory.add_message()`: summarisation trigger wrapped in try/except — failure logs and defers to next qualifying message (non-blocking).
- `ConversationMemory.clear_conversation()`: both steps log on failure.

**Cross-cutting:**
- Added `logging.getLogger(__name__)` to all 6 modified files: `chat_service.py`, `retrieval_service.py`, `conversation_memory.py`, `storage_service.py`, `chat_repo.py`, `chats.py`.
- Added 9 new tests to `test_chat_service.py` covering: Bedrock throttling, access denied, RuntimeError classification, DynamoDB write failures (user msg, assistant msg), non-streaming equivalents, and conversation memory degradation.
- Updated 2 existing tests to match new behaviour (graceful degradation, user-friendly messages).
- Test count: 126/126 passing (previously 117 + 9 new).

**Best Practice:** Error handling should be granular per downstream call, not a single catch-all. Categorise errors into *transient* (retry/503) vs *permanent* (log and surface) early. Always log server-side before emitting a user-friendly message. Summarisation and retrieval should be best-effort — never block the core chat flow.

---

## Post-Deployment Issues

### Issue: Chat Messages Displayed Out of Chronological Order

**Symptoms:**
- Chat messages appeared in random order in the UI instead of chronological sequence
- Conversation history in RAG prompts was scrambled, degrading LLM response quality
- Conversation memory's `get_recent_messages()` returned arbitrary messages instead of the most recent ones

**Cause:**
- `ChatRepository.add_message()` used `str(uuid.uuid4())` as the DynamoDB sort key (`message_id`)
- UUIDv4 is randomly generated — its lexicographic sort order has no relationship to insertion time
- DynamoDB `Query` with `ScanIndexForward=True/False` sorts by sort key, so messages were returned in random UUID hex order (e.g., `2f→6e→7b→9a→a6→bd→d9→f7`) instead of chronological order
- This affected all message retrieval paths: `get_messages()` (chat history API), `get_recent_messages()` (conversation memory), and the sliding window summarisation trigger

**Resolution:**
- Changed `message_id` generation in `ChatRepository.add_message()` from `str(uuid.uuid4())` to a timestamp-prefixed format: `f"{now.strftime('%Y%m%dT%H%M%S%f')}#{uuid.uuid4()}"`
- The timestamp prefix (`YYYYMMDDTHHMMSSF6`) ensures lexicographic sort order matches chronological order
- The UUID suffix preserves uniqueness in the unlikely event of sub-microsecond duplicate timestamps
- Created a one-time migration script (`backend/scripts/migrate_message_ids.py`) to re-key existing messages using their `timestamp` attribute
- Migration atomically deletes old items and writes new ones with timestamp-prefixed `message_id` values
- Python's `uuid7` was considered but is not available in the standard library (Python 3.12); the timestamp-prefix approach achieves the same chronological ordering guarantee

**Files Changed:**
- `backend/app/repositories/chat_repo.py` — `add_message()` message_id generation
- `backend/scripts/migrate_message_ids.py` — one-time data migration for existing messages

**Best Practice:** When using DynamoDB sort keys for ordered data, never use random UUIDs. Use a time-sortable format (timestamp prefix, ULID, or UUIDv7) so that lexicographic ordering matches chronological ordering. This is critical for any query that relies on `ScanIndexForward`.

---

### Issue: RAG Context Window Too Small — LLM Could Not Answer Questions About Document Content

**Symptoms:**
- When asking the LLM about content from uploaded research papers (e.g., "who are the authors?"), the response was "the document does not provide information"
- The document was correctly parsed (15 pages, 24 chunks) and retrieval returned relevant chunks
- The LLM simply never saw enough of the document to answer

**Cause:**
- `PromptBuilder` hardcoded `context_window = 8000` tokens, while the model (Amazon Nova Micro) supports ~128,000 tokens
- With a 60/30/10 token budget split (context / messages / summary), only ~4,800 tokens were allocated for retrieved document chunks
- Research papers with many pages had their context severely truncated — author lists, abstracts, and key sections were often cut entirely
- The config system (`LLMConfig`) had no `context_window` field, so the value couldn't be configured

**Resolution:**
- Added `context_window: int = 128000` to `LLMConfig` in `backend/app/core/config.py`
- Added `context_window: 128000` to `backend/config.yaml` under the `llm:` section
- Changed `PromptBuilder.__init__()` from `context_window = 8000` to `context_window = self.settings.llm.context_window`
- With 128k budget, ~75,000 tokens are now available for document chunks (60% allocation), vs only ~4,800 before
- Updated `test_build_prompt_with_truncation` to explicitly pass `context_window=8000` since the default 128k no longer triggers truncation with test data

**Files Changed:**
- `backend/app/core/config.py` — added `context_window` field to `LLMConfig`
- `backend/app/services/prompt_builder.py` — read `context_window` from settings
- `backend/config.yaml` — added `context_window: 128000`
- `backend/tests/test_prompt_builder.py` — updated truncation test fixture

**Best Practice:** Never hardcode model-specific limits deep in service code. Always expose them as configuration values so they can be tuned per model (e.g., Nova Micro 128k vs Nova Lite 300k) without code changes. Token budgets should be validated against the actual model's context window during startup or testing.
