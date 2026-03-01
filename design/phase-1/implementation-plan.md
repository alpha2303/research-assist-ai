# Research Assist AI — Implementation Plan

> **Status**: Phase 7 (Terraform & Deployment) Complete — Full AWS infrastructure + production Dockerfiles + deployment script
>
> **Last Updated**: 2026-03-01
>
> **Reference**: See `design-doc.md` for full design specifications and `requirement-specification.md` for requirements.

## Progress Summary

**Completed Phases:**
- ✅ **Phase 1**: Project scaffolding, Docker setup, backend/frontend initialization
- ✅ **Phase 2**: Configuration system, database models with migrations, interfaces, DynamoDB setup, Pydantic schemas
- ✅ **Phase 3**: Project Management Service with full CRUD backend (13/13 tests passing) and frontend UI with modal dialogs
- ✅ **Phase 4 (Implementation)**: Document Ingestion Pipeline fully implemented
  - Backend: Storage, parsers, chunking, embedding, vector store, Celery tasks
  - Frontend: Document upload area with drag-and-drop, document list with status badges
  - Testing: 76/158 tests passing (48% pass rate - needs fixes)
- ✅ **Phase 5**: Chat Service & RAG — all 8 sub-phases implemented
  - 5.1-5.2: Chat session management (DynamoDB) + Frontend Chat UI
  - 5.3: Hybrid retrieval (vector + BM25) with project-scoped search
  - 5.4: LLM Integration (Bedrock Nova via Converse API)
  - 5.5: Context assembly with token budgeting and priority-based truncation
  - 5.6: SSE streaming endpoint (token/sources/done/error events)
  - 5.7: Conversation memory (sliding window + LLM summarisation)
  - 5.8: Frontend chat interface with real-time streaming
  - Test Coverage: 89/89 Phase 5 tests passing (100% pass rate)
- ✅ **Phase 6**: Integration, Polish & Testing
  - 6.2: Error handling — global exception handler, Bedrock/S3/DynamoDB failure handling, error boundaries, toasts, Axios retry, SSE reconnection with exponential backoff
  - 6.3: UI polish — responsive mobile layout (hamburger drawer), empty/loading states, consistent visual styling, keyboard shortcuts (Ctrl+N, Escape), Markdown rendering (react-markdown + remark-gfm)
  - 6.4: Re-embedding pipeline — admin API, Celery batch task (resumable), mixed-model query filtering
  - Note: 6.1 (E2E integration tests) are manual end-to-end scenarios to be run against a live environment
- ✅ **Phase 7**: Terraform & Deployment
  - 7.1: Terraform foundation — modular layout, provider config, S3 backend (commented out), dev/prod tfvars
  - 7.2: AWS resource definitions — VPC, RDS (pgvector), DynamoDB, S3, ECR, ECS Fargate, ALB, ElastiCache Redis, IAM roles, CloudWatch alarms
  - 7.3: Deployment pipeline — production Dockerfiles (backend + frontend), deployment script (ECR push + ECS update + Alembic migrations), infrastructure README

**Current Status:**
- All implementation phases (1–7) **complete**
- Backend: 234 tests passing
- Frontend: requires `npm install` to pick up react-markdown and remark-gfm dependencies
- Infrastructure: Terraform modules ready for `terraform plan/apply`
- Post-deployment fixes applied: message ordering (timestamp-prefixed sort keys), RAG context window (8k → 128k configurable)
- Post-development enhancement: Dark mode with system preference detection and localStorage persistence

**Remaining (Optional):**
1. ~~Fix Phase 4 remaining unit test failures~~ ✅ Fixed
2. Run Phase 6.1 E2E integration tests against a live environment
3. Add CI/CD pipeline (GitHub Actions)

---

## Table of Contents

1. [Implementation Overview](#1-implementation-overview)
2. [Phase 1 — Project Scaffolding & Local Development Environment](#2-phase-1--project-scaffolding--local-development-environment)
3. [Phase 2 — Core Abstractions, Models & Configuration](#3-phase-2--core-abstractions-models--configuration)
4. [Phase 3 — Project Management Service](#4-phase-3--project-management-service)
5. [Phase 4 — Document Ingestion Pipeline](#5-phase-4--document-ingestion-pipeline)
6. [Phase 5 — Chat Service & RAG](#6-phase-5--chat-service--rag)
7. [Phase 6 — Integration, Polish & Testing](#7-phase-6--integration-polish--testing)
8. [Phase 7 — Terraform & Deployment](#8-phase-7--terraform--deployment)
9. [Project Structure](#9-project-structure)
10. [Dependency Map](#10-dependency-map)
11. [Risk Register](#11-risk-register)
12. [Post-Development Enhancements](#12-post-development-enhancements)

---

## 1. Implementation Overview

### Guiding Principles

- **Incremental delivery**: Each phase produces a working (if incomplete) system. No "big bang" integration at the end.
- **Backend-first, then frontend**: API endpoints are built and tested before the UI consumes them. This avoids blocked frontend work.
- **Abstractions before implementations**: Interfaces are defined in Phase 2, then implemented incrementally as each phase demands them.
- **Local-first development**: Everything runs locally via Docker Compose before any AWS resources are provisioned.

### Tools

| Layer | Tool | Notes |
|---|---|---|
| **Python Project Manager** | `uv` (by Astral) | Replaces pip, pip-tools, virtualenv, pyenv. Rust-powered, 10–100x faster installs. Lockfile (`uv.lock`) for reproducible builds. PEP 621 `pyproject.toml` native. |

### Coding Standards

All Python code must follow:

- **PEP 8**: Python's official style guide (line length, naming conventions, imports)
- **Google Python Style Guide**: Docstrings, type hints, code organization
- **Type annotations**: All function parameters, return types, and variables must have explicit type hints
- **Docstrings**: All modules, classes, and functions must have Google-style docstrings with Args/Returns/Raises sections
- **Import organization**: Standard library → third-party → local imports, alphabetically sorted within each group

Tools for enforcement:
- `mypy` for static type checking
- `ruff` for fast linting and formatting (replaces black, isort, flake8)
- `pytest` with type stubs for testing

### Phase Summary

| Phase | Name | Key Deliverable | Est. Effort |
|---|---|---|---|
| 1 | Project Scaffolding & Local Dev Environment | Running backend + frontend + Docker services | 2–3 days |
| 2 | Core Abstractions, Models & Configuration | All interfaces, DB models, config system | 2–3 days |
| 3 | Project Management Service | CRUD APIs + frontend project list panel | 2–3 days |
| 4 | Document Ingestion Pipeline | Upload → parse → chunk → embed → store (async) | 5–6 days |
| 5 | Chat Service & RAG | Chat UI + hybrid retrieval + LLM streaming | 6–7 days |
| 6 | Integration, Polish & Testing | End-to-end flow, error handling, responsive UI | 3–4 days |
| 7 | Terraform & Deployment | AWS infrastructure, deployment pipeline | 3–4 days |
| | | **Total estimated effort** | **~24–30 days** |

> **Note**: Effort estimates assume a single developer working part-time on a pet project. Adjust based on your actual availability.

---

## 2. Phase 1 — Project Scaffolding & Local Development Environment

**Goal**: A running backend (FastAPI), frontend (React), and local services (PostgreSQL + pgvector, Redis) — all containerized. No business logic yet.

### Tasks

#### 1.1 — Backend Project Initialization

| # | Task | Details |
|---|---|---|
| 1.1.1 | Initialize Python project with `uv` | `uv init backend` — creates `backend/` directory with `pyproject.toml` (PEP 621). Pin Python version: `uv python pin 3.12` (creates `.python-version` file). |
| 1.1.2 | Install core dependencies via `uv` | `uv add fastapi uvicorn pydantic pydantic-settings sqlalchemy asyncpg alembic boto3 celery redis`. This auto-updates `pyproject.toml` and generates `uv.lock` for reproducible installs. |
| 1.1.3 | Create FastAPI application entry point | `backend/app/main.py` with health check endpoint (`GET /api/health`) |
| 1.1.4 | Set up project directory structure | See [Section 9 — Project Structure](#9-project-structure) |
| 1.1.5 | Set up Alembic for database migrations | `uv run alembic init alembic`, configure `alembic.ini` to read DB URL from environment |
| 1.1.6 | Create `.env.local` template | Database URLs, Redis URL, AWS profile name, placeholder Bedrock model IDs |
| 1.1.7 | Verify backend starts | `uv run uvicorn app.main:app --reload` → health check returns 200 |

#### 1.2 — Frontend Project Initialization

| # | Task | Details |
|---|---|---|
| 1.2.1 | Initialize React + TypeScript project | `npx create-react-app frontend --template typescript` or Vite (`npm create vite@latest frontend -- --template react-ts`). **Recommend Vite** for faster dev server. |
| 1.2.2 | Install core dependencies | `tailwindcss`, `postcss`, `autoprefixer`, `axios` (or `fetch` wrapper), `react-router-dom` |
| 1.2.3 | Configure Tailwind CSS | `tailwind.config.js`, add Tailwind directives to `index.css` |
| 1.2.4 | Create basic app shell | Two-panel layout placeholder: left (1/3 width), right (2/3 width) |
| 1.2.5 | Set up API client module | Centralized API client with base URL from environment variable |
| 1.2.6 | Verify frontend starts | `npm run dev` → renders placeholder layout |

#### 1.3 — Docker Compose & Local Services

| # | Task | Details |
|---|---|---|
| 1.3.1 | Create `docker-compose.yml` | Services: PostgreSQL (pgvector), Redis, backend (FastAPI), frontend (Vite dev server) |
| 1.3.2 | PostgreSQL + pgvector service | Image: `pgvector/pgvector:pg16`, expose port 5432, volume for data persistence |
| 1.3.3 | Redis service | Image: `redis:7-alpine`, expose port 6379 |
| 1.3.4 | Backend service | Dockerfile using `uv` for dependency installation (`uv sync --frozen`), mount source for hot reload, depends on PostgreSQL + Redis |
| 1.3.5 | Frontend service | Dockerfile for Vite dev server (or run outside Docker for faster HMR) |
| 1.3.6 | Create initialization SQL script | Enable `pgvector` extension: `CREATE EXTENSION IF NOT EXISTS vector;` |
| 1.3.7 | Verify full stack starts | `docker-compose up` → all services healthy, frontend can reach backend health check |

### Phase 1 Acceptance Criteria

- [x] `uv sync` installs all dependencies and generates `uv.lock`.
- [x] `docker-compose up` starts PostgreSQL (with pgvector), Redis, backend, and frontend.
- [x] `GET /api/health` returns `200 OK` from the backend.
- [x] Frontend renders a two-panel placeholder layout.
- [x] Alembic is configured and can connect to PostgreSQL (`uv run alembic heads` succeeds).
- [x] `.env.local` template is documented with all required variables.
- [x] `uv.lock` is committed to the repo.

### Phase 1 Implementation Notes

**Backend Setup:**
- Python 3.12.3 with uv package manager for fast dependency management
- FastAPI 0.129.0 with uvicorn ASGI server
- SQLAlchemy 2.0.46 async ORM with asyncpg driver
- Alembic for database migrations
- Project structure following clean architecture (repositories, services, routers)

**Frontend Setup:**
- React 19.2.0 with TypeScript
- Vite 7.3.1 for fast development and builds
- Tailwind CSS v4 for styling with PostCSS integration
- Axios for API client with centralized configuration

**Infrastructure:**
- Docker Compose orchestrates PostgreSQL 16, Redis 7, backend, and frontend services
- PostgreSQL with pgvector extension v0.8.1 for vector embeddings
- Environment-based configuration with `.env` files

---

## 3. Phase 2 — Core Abstractions, Models & Configuration

**Goal**: All abstract interfaces, database models (SQLAlchemy + DynamoDB), Pydantic schemas, and the configuration system are in place. No API endpoints yet — this is the internal skeleton.

### Tasks

#### 2.1 — Configuration System

| # | Task | Details |
|---|---|---|
| 2.1.1 | Create `config.yaml` with defaults | All configurable parameters: chunking, retrieval, memory, embedding, LLM, document processing (see design doc Section 7.7) |
| 2.1.2 | Create Pydantic settings class | `backend/app/core/config.py` — loads from `.env` + `config.yaml`, supports env var overrides (e.g., `CHUNKING__CHUNK_SIZE_TOKENS`) |
| 2.1.3 | Create settings dependency for FastAPI | `get_settings()` dependency that provides the config object to endpoints |
| 2.1.4 | Add dev dependencies | `uv add --dev pytest pytest-asyncio httpx pyyaml` — test and dev tooling in a separate dependency group |
| 2.1.5 | Write unit tests for config loading | Verify YAML loading, env var overrides, default values (`uv run pytest`) |

#### 2.2 — Abstract Interfaces (Python Protocols / ABCs)

| # | Task | Details |
|---|---|---|
| 2.2.1 | `VectorStore` interface | `backend/app/core/interfaces/vector_store.py` — `store_embeddings()`, `similarity_search()`, `hybrid_search()`, `delete_by_document_id()` |
| 2.2.2 | `EmbeddingProvider` interface | `backend/app/core/interfaces/embedding_provider.py` — `embed_text()`, `embed_batch()`, `get_model_id()`, `get_dimensions()` |
| 2.2.3 | `LLMProvider` interface | `backend/app/core/interfaces/llm_provider.py` — `generate()`, `generate_stream()`, `get_model_id()` |
| 2.2.4 | `DocumentParser` interface | `backend/app/core/interfaces/document_parser.py` — `parse(file_path) → ParseResult`, `get_supported_formats()` |
| 2.2.5 | `TaskQueue` interface | `backend/app/core/interfaces/task_queue.py` — `submit_task()`, `get_task_status()`, `cancel_task()` |
| 2.2.6 | `ConversationMemory` interface | `backend/app/core/interfaces/conversation_memory.py` — `get_context()`, `add_message()`, `trigger_summarization()` |
| 2.2.7 | Create `__init__.py` barrel export | Re-export all interfaces from `backend/app/core/interfaces/__init__.py` |

#### 2.3 — Database Models (SQLAlchemy / PostgreSQL)

| # | Task | Details |
|---|---|---|
| 2.3.1 | Create SQLAlchemy base and engine setup | `backend/app/db/base.py` — async engine, session factory, base declarative model |
| 2.3.2 | `Project` model | `id` (UUID), `title`, `description`, `created_at`, `updated_at` |
| 2.3.3 | `Document` model | `id` (UUID), `title`, `s3_key`, `file_hash`, `file_size_bytes`, `mime_type`, `status` (enum), `page_count`, `created_at` |
| 2.3.4 | `ProjectDocument` model | `project_id` (FK), `document_id` (FK), `linked_at` — composite PK |
| 2.3.5 | `DocumentChunk` model | `id` (UUID), `document_id` (FK), `chunk_index`, `content`, `page_number`, `section_heading`, `token_count`, `embedding_model_id`, `embedding` (VECTOR(1024)), `search_vector` (TSVECTOR), `created_at` |
| 2.3.6 | Create Alembic migration | Auto-generate migration from models (`uv run alembic revision --autogenerate`), verify it creates all tables + indexes (HNSW on embedding, GIN on search_vector) |
| 2.3.7 | Run migration and verify schema | `uv run alembic upgrade head` → tables exist with correct columns and indexes |

#### 2.4 — DynamoDB Models / Schemas

| # | Task | Details |
|---|---|---|
| 2.4.1 | Create DynamoDB client wrapper | `backend/app/db/dynamodb.py` — boto3 DynamoDB resource, table references, connection config |
| 2.4.2 | Define `chat_sessions` table schema | Partition key: `project_id`, sort key: `chat_id`, attributes: `title`, `running_summary`, `summary_through_index`, `created_at`, `updated_at` |
| 2.4.3 | Define `chat_messages` table schema | Partition key: `chat_id`, sort key: `message_id` (timestamp-prefixed: `YYYYMMDDTHHMMSSF6#uuid4`), attributes: `sender`, `content`, `sources`, `token_count`, `timestamp` |
| 2.4.4 | Create table initialization script | Script to create DynamoDB tables (for LocalStack or real AWS). Idempotent — skips if tables exist. |

#### 2.5 — Pydantic Schemas (API Request/Response Models)

| # | Task | Details |
|---|---|---|
| 2.5.1 | Project schemas | `ProjectCreate`, `ProjectUpdate`, `ProjectResponse`, `ProjectListResponse` |
| 2.5.2 | Document schemas | `DocumentUploadResponse`, `DocumentStatusResponse`, `DocumentListResponse`, `DocumentLinkRequest` |
| 2.5.3 | Chat schemas | `ChatCreate`, `ChatResponse`, `ChatListResponse`, `MessageCreate`, `MessageResponse`, `MessageListResponse` |
| 2.5.4 | SSE event schemas | `TokenEvent`, `SourcesEvent`, `DoneEvent`, `ErrorEvent` |
| 2.5.5 | Common schemas | `PaginationParams`, `ErrorResponse`, standard envelope types |

### Phase 2 Acceptance Criteria

- [x] All 6 abstract interfaces are defined with type hints and docstrings.
- [x] `config.yaml` loads correctly, env var overrides work, unit tests pass.
- [x] Alembic migration creates all PostgreSQL tables with correct columns, types, and indexes.
- [x] DynamoDB tables can be created via the initialization script (against LocalStack or AWS).
- [x] All Pydantic schemas are defined and serializable.

### Phase 2 Implementation Notes

**Configuration System:**
- Used Pydantic Settings with YAML config file as base, environment variables as overrides
- Nested configuration models for different services (database, AWS, embedding, chunking)
- Test coverage: 9/9 tests passing including default values, YAML loading, env overrides

**Database Models:**
- SQLAlchemy 2.0 async with asyncpg driver
- UUIDs for primary keys using `uuid_generate_v4()` default
- Proper foreign key constraints with `ondelete="CASCADE"` for cleanup
- Timestamps using `func.now()` for server-side generation
- pgvector extension with Vector(1024) for embeddings
- HNSW index for fast vector similarity search with explicit operator class
- TSVECTOR for BM25 full-text search
- Many-to-many relationships with explicit association tables and viewonly relationships

**DynamoDB Tables:**
- `chat_sessions` table with project_id as partition key, chat_id as sort key
- `chat_messages` table with chat_id as partition key, message_id as sort key (timestamp-prefixed: `YYYYMMDDTHHMMSSF6#uuid4` for chronological ordering)
- Initialization script with boto3, idempotent table creation

**Pydantic Schemas:**
- All request/response models defined with proper validation
- Type-safe discriminated unions for actions
- Proper use of `Optional` vs required fields
- Custom validators where needed

---

## 4. Phase 3 — Project Management Service

**Goal**: Full CRUD for projects with a working frontend project list panel. First end-to-end feature.

### Tasks

#### 3.1 — Backend: Project CRUD APIs

| # | Task | Details |
|---|---|---|
| 3.1.1 | Create project repository layer | `backend/app/repositories/project_repo.py` — async SQLAlchemy queries for CRUD operations |
| 3.1.2 | Create project service layer | `backend/app/services/project_service.py` — business logic (validation, orchestration) |
| 3.1.3 | `POST /api/projects` | Create a new project. Request: `ProjectCreate`. Response: `ProjectResponse`. |
| 3.1.4 | `GET /api/projects` | List all projects (sorted by `updated_at` descending). Response: `ProjectListResponse`. |
| 3.1.5 | `GET /api/projects/{project_id}` | Get project details by ID. 404 if not found. |
| 3.1.6 | `PUT /api/projects/{project_id}` | Update project title/description. |
| 3.1.7 | `DELETE /api/projects/{project_id}` | Delete project and all associated links (cascade unlink documents, delete chats). |
| 3.1.8 | Add CORS middleware | Configure FastAPI CORS to allow frontend origin (configurable). |
| 3.1.9 | Write API integration tests | Test all CRUD operations against a test database. |

#### 3.2 — Frontend: Project List Panel

| # | Task | Details |
|---|---|---|
| 3.2.1 | Create `ProjectList` component | Left panel (1/3 width), scrollable list. |
| 3.2.2 | Create `ProjectCard` component | Card with project title (left), expand/collapse button (right). Rounded borders, shadow. |
| 3.2.3 | Create `CreateProjectButton` component | First item in the list. Opens a modal/inline form for project title + description. |
| 3.2.4 | Create `CreateProjectModal` component | Form with title (required) and description (optional). Calls `POST /api/projects`. |
| 3.2.5 | Wire up API calls | Fetch project list on mount, create project, delete project (via context menu or button). |
| 3.2.6 | Add loading and error states | Skeleton loader for project list, error toast on API failure. |
| 3.2.7 | Add project selection state | Clicking a project card highlights it and stores `selectedProjectId` in app state. |

#### 3.3 — State Management Setup

| # | Task | Details |
|---|---|---|
| 3.3.1 | Choose state management approach | React Context + `useReducer` for global state (project list, selected project, selected chat). Lightweight — no Redux needed for this scale. |
| 3.3.2 | Create `AppContext` provider | Holds: `projects`, `selectedProjectId`, `selectedChatId`, dispatch actions. |
| 3.3.3 | Create custom hooks | `useProjects()`, `useSelectedProject()` — abstract context access. |

### Phase 3 Acceptance Criteria

- [x] All 5 project CRUD endpoints work and return correct responses.
- [x] Frontend project list renders projects fetched from the API.
- [x] New projects can be created via the UI.
- [x] Projects can be deleted via the UI.
- [x] Selecting a project highlights it in the list.
- [x] CORS is configured and frontend-backend communication works.

### Phase 3 Implementation Notes

**Backend Implementation Patterns:**
- **Repository Layer**: Async SQLAlchemy with proper type hints, pagination support using limit/offset
- **Service Layer**: Business logic orchestration, Pydantic schema conversion using `model_validate()`
- **Router Layer**: FastAPI dependency injection for database sessions, proper HTTP status codes (201 for created, 204 for delete, 404 for not found)
- **Testing**: pytest-asyncio with `httpx.AsyncClient` using `ASGITransport`, fixtures with proper database isolation (create/drop tables per test)
- **SQLAlchemy Relationships**: Used `viewonly=True` for many-to-many relationships with explicit association tables
- **Database Indexes**: HNSW index with explicit operator class: `postgresql_ops={'embedding': 'vector_cosine_ops'}`

**Frontend Implementation Patterns:**
- **State Management**: React Context + `useReducer` with discriminated union types for type-safe actions
- **Component Architecture**: Smart/container components (ProjectList) vs presentational components (ProjectCard)
- **Modal Implementation**: React Portals (`createPortal(content, document.body)`) for proper z-index stacking outside component hierarchy
- **API Integration**: Centralized API service layer with axios, error handling with try/catch
- **Form Handling**: Controlled components with local state for form fields, validation before submission
- **UI/UX Patterns**: Loading skeletons, empty states with illustrations, error retry buttons, confirmation dialogs for destructive actions
- **Event Handling**: ESC key handling with `useEffect` cleanup, backdrop click detection for modals
- **CSS Configuration**: Tailwind CSS v4 with `@import "tailwindcss"` syntax (not v3 `@tailwind` directives), PostCSS with `@tailwindcss/postcss` plugin
- **TypeScript**: Strict mode with `verbatimModuleSyntax` enabled, type-only imports using `import type { ... }` syntax

**Development Tools:**
- **Backend**: mypy for type checking, ruff for linting, pytest with 13/13 tests passing
- **Frontend**: TypeScript strict mode, ESLint, Vite HMR for fast development
- **Docker**: Multi-stage builds for backend image, service orchestration with docker-compose

---

## 5. Phase 4 — Document Ingestion Pipeline

**Goal**: Users can upload PDFs to a project. The system asynchronously parses, chunks, embeds, and stores the document. Processing status is visible in the UI.

### Dependencies
- Phase 2 (interfaces, models, config)
- Phase 3 (project CRUD — documents are linked to projects)
- AWS credentials configured for S3 and Bedrock access

### Tasks

#### 4.1 — File Upload & S3 Storage

| # | Task | Details |
|---|---|---|
| 4.1.1 | Create S3 client wrapper | `backend/app/services/storage_service.py` — upload file, generate presigned URL, delete file. Configurable bucket name via env. |
| 4.1.2 | `POST /api/documents/upload` | Accepts multipart file upload. Computes SHA-256 hash. Checks for duplicate. If new: uploads to S3, creates `Document` record (status=`queued`), submits async task. If duplicate: returns existing document. |
| 4.1.3 | `POST /api/projects/{project_id}/documents` | Links an existing document to a project. Creates `ProjectDocument` record. |
| 4.1.4 | `GET /api/projects/{project_id}/documents` | Lists all documents linked to a project with their processing status. |
| 4.1.5 | `GET /api/documents/{document_id}/status` | Returns current processing status of a document. |
| 4.1.6 | `DELETE /api/projects/{project_id}/documents/{document_id}` | Unlinks a document from a project. Does NOT delete the global document or its chunks. |
| 4.1.7 | Handle upload validation | Max file size check (configurable, default 50MB), MIME type check (`application/pdf` only for now). |

#### 4.2 — PDF Parsing Implementation

| # | Task | Details |
|---|---|---|
| 4.2.1 | Install parsing dependencies | `uv add pymupdf pymupdf4llm pdfplumber` |
| 4.2.2 | Implement `PyMuPDF4LLMParser` | Concrete implementation of `DocumentParser`. Calls `pymupdf4llm.to_markdown()`. Returns structured `ParseResult` with markdown content + page metadata. |
| 4.2.3 | Implement `PdfPlumberParser` | Fallback implementation. Extracts text page-by-page, uses `.extract_tables()` for tables, converts to Markdown format. |
| 4.2.4 | Implement parser fallback logic | In the ingestion pipeline: try primary parser → on failure → try fallback → on failure → mark document as `failed`. |
| 4.2.5 | Write parser unit tests | Test both parsers against sample PDFs (with and without tables). |

#### 4.3 — Chunking Pipeline

| # | Task | Details |
|---|---|---|
| 4.3.1 | Install tokenization dependency | `uv add tiktoken` (for accurate token counting) or a simpler heuristic (chars ÷ 4). |
| 4.3.2 | Implement recursive character splitter | Configurable chunk size (default 800 tokens), overlap (default 150 tokens), separator hierarchy (`\n## `, `\n### `, `\n\n`, `\n`, `. `). Reads params from `config.yaml`. |
| 4.3.3 | Extract chunk metadata | For each chunk: `chunk_index`, `page_number` (from parser output), `section_heading` (detect nearest heading above chunk), `token_count`. |
| 4.3.4 | Write chunking unit tests | Test with various document structures: short docs, long docs, tables, multi-section papers. Verify overlap correctness. |

#### 4.4 — Embedding Generation

| # | Task | Details |
|---|---|---|
| 4.4.1 | Implement `TitanEmbeddingProvider` | Concrete implementation of `EmbeddingProvider`. Uses `boto3` Bedrock runtime client. Calls `invoke_model()` with Titan Embeddings V2 model ID. Returns vector (list of floats). |
| 4.4.2 | Implement `embed_batch()` | Batch embedding for efficiency. Titan V2 supports single-text input, so batch = sequential calls. Add rate limiting / retry logic with exponential backoff. |
| 4.4.3 | Write embedding integration tests | Verify embedding generation returns correct dimensions (1024). Test with mock Bedrock client for unit tests. |

#### 4.5 — Vector Storage (PGVector + BM25)

| # | Task | Details |
|---|---|---|
| 4.5.1 | Implement `PGVectorStore` | Concrete implementation of `VectorStore`. Uses SQLAlchemy + pgvector extension. |
| 4.5.2 | Implement `store_embeddings()` | Bulk insert chunks with embeddings into `document_chunks`. Auto-populate `search_vector` using PostgreSQL `to_tsvector()` trigger or application-side. |
| 4.5.3 | Implement `similarity_search()` | Cosine similarity search on `embedding` column, filtered by document IDs (project scope). Returns top-k results. |
| 4.5.4 | Implement `hybrid_search()` | Combines vector similarity + BM25 (`ts_rank` on `search_vector`). Weighted Reciprocal Rank Fusion. Configurable weights from `config.yaml`. |
| 4.5.5 | Implement `delete_by_document_id()` | Deletes all chunks for a given document (used for re-processing or document deletion). |
| 4.5.6 | Create PostgreSQL trigger for tsvector | Auto-update `search_vector` column when `content` is inserted/updated: `CREATE TRIGGER ... tsvector_update_trigger ...` (add to Alembic migration). *(Fixed in migration `002_add_tsvector_trigger.py` — was missing, causing BM25 search to return no results.)* |
| 4.5.7 | Write vector store integration tests | Test similarity search returns relevant results, hybrid search combines scores correctly, project scoping works. |

#### 4.6 — Task Queue (Celery + Redis)

| # | Task | Details |
|---|---|---|
| 4.6.1 | Configure Celery application | `backend/app/worker/celery_app.py` — Celery instance with Redis broker/backend URLs from config. |
| 4.6.2 | Implement `CeleryTaskQueue` | Concrete implementation of `TaskQueue`. Wraps Celery's `send_task()`, `AsyncResult`. |
| 4.6.3 | Create `process_document` task | Celery task that runs the full pipeline: parse → chunk → embed → store. Updates `documents.status` at each stage. |
| 4.6.4 | Add error handling and retries | Max 3 retries with exponential backoff. On final failure, set `documents.status = 'failed'` with error details. |
| 4.6.5 | Add Celery worker to Docker Compose | Separate container running `uv run celery -A app.worker.celery_app worker`. Same image as backend (shares `uv.lock`). |
| 4.6.6 | Write task queue integration tests | Submit a task, verify status transitions (queued → processing → ready), verify chunks are stored. |

#### 4.7 — Frontend: Document Upload UI

| # | Task | Details |
|---|---|---|
| 4.7.1 | Create `DocumentUploadArea` component | Drag-and-drop zone + file picker button. Validates file type (PDF) and size before upload. Placed in the expanded project view. |
| 4.7.2 | Create `DocumentList` component | Shows documents linked to the selected project. Each item shows title, status badge (queued/processing/ready/failed). |
| 4.7.3 | Implement upload flow | On file select: call `POST /api/documents/upload` → then `POST /api/projects/{id}/documents` to link. Show progress indicator. |
| 4.7.4 | Implement status polling | Poll `GET /api/documents/{id}/status` every 3 seconds while status is `queued` or `processing`. Stop on `ready` or `failed`. |
| 4.7.5 | Add document removal from project | Button to unlink a document from the project (calls `DELETE /api/projects/{id}/documents/{doc_id}`). |

### Phase 4 Acceptance Criteria

- [ ] PDF files can be uploaded via the UI and are stored in S3 (or local filesystem for dev).
- [ ] Duplicate files are detected and linked without re-processing.
- [ ] Document status transitions correctly: `queued` → `processing` → `ready`.
- [ ] Parsed chunks are visible in the `document_chunks` table with correct metadata.
- [ ] Embeddings are stored as 1024-dimension vectors in PGVector.
- [ ] BM25 `search_vector` is populated for every chunk.
- [ ] Celery worker processes tasks asynchronously.
- [ ] Frontend shows upload progress and document processing status.

---

## 6. Phase 5 — Chat Service & RAG

**Goal**: Users can create chat sessions within a project, ask questions, and receive AI-generated answers streamed in real-time — grounded in the project's uploaded documents.

### Dependencies
- Phase 4 (documents must be uploaded and indexed for retrieval to work)
- AWS credentials configured for Bedrock (LLM) and DynamoDB

### Tasks

#### 5.1 — Chat Session Management (DynamoDB)

| # | Task | Details | Status |
|---|---|---|---|
| 5.1.1 | Create chat repository layer | `backend/app/repositories/chat_repo.py` — DynamoDB operations for `chat_sessions` and `chat_messages` tables. **Post-deploy fix:** `message_id` changed from `uuid4()` to timestamp-prefixed format (`YYYYMMDDTHHMMSSF6#uuid4`) to ensure chronological sort key ordering. Migration script at `backend/scripts/migrate_message_ids.py`. | ✅ DONE |
| 5.1.2 | `POST /api/projects/{project_id}/chats` | Create a new chat session. Stores in DynamoDB with project_id, chat_id (UUID), title (auto-generated or user-provided). | ✅ DONE |
| 5.1.3 | `GET /api/projects/{project_id}/chats` | List all chat sessions for a project, sorted by `updated_at` descending. | ✅ DONE |
| 5.1.4 | `GET /api/chats/{chat_id}/messages` | Get full message history for a chat. Paginated. Sorted by timestamp ascending. | ✅ DONE |
| 5.1.5 | `DELETE /api/chats/{chat_id}` | Delete a chat session and all its messages from DynamoDB. | ✅ DONE |
| 5.1.6 | Write chat CRUD tests | Test all DynamoDB operations. | ✅ DONE (25/25 tests passing) |

#### 5.2 — Frontend: Chat List in Project Panel

| # | Task | Details | Status |
|---|---|---|---|
| 5.2.1 | Create `ChatList` component | Rendered inside expanded `ProjectCard`. Shows chat sessions for the project. | ✅ DONE |
| 5.2.2 | Create `CreateChatButton` component | First item in chat list. Creates a new chat session on click. | ✅ DONE (Modal) |
| 5.2.3 | Create `ChatListItem` component | Clickable item showing chat title. Clicking sets `selectedChatId` and opens chat in right panel. | ✅ DONE |
| 5.2.4 | Wire up chat selection | Selecting a chat loads its message history into the right panel. | ✅ DONE |

#### 5.3 — Hybrid Retrieval Integration

| # | Task | Details | Status |
|---|---|---|---|
| 5.3.1 | Create retrieval service | `backend/app/services/retrieval_service.py` — orchestrates the retrieval pipeline. | ✅ DONE |
| 5.3.2 | Implement project-scoped retrieval | Given a `project_id` and query: (1) get linked document IDs, (2) generate query embedding, (3) call `hybrid_search()` filtered by those document IDs. | ✅ DONE |
| 5.3.3 | Format retrieved chunks for context | Structure chunks as labeled context blocks: `[Source: Paper Title, Page X] content...` | ✅ DONE |
| 5.3.4 | Extract source metadata | Collect `(document_id, title, page_number)` from top-k results for source attribution in the response. | ✅ DONE |
| 5.3.5 | Write retrieval integration tests | Upload test documents, query, verify correct chunks are returned with project isolation. | ✅ DONE |

#### 5.4 — LLM Integration (Bedrock)

| # | Task | Details | Status |
|---|---|---|---|
| 5.4.1 | Implement `BedrockNovaProvider` | Concrete implementation of `LLMProvider`. Uses `boto3` Bedrock runtime client. | ✅ DONE |
| 5.4.2 | Implement `generate()` | Synchronous generation via Bedrock Converse API (`converse()`). For fallback/testing. *(Originally planned as `invoke_model()`; upgraded to Converse API for unified model interface.)* | ✅ DONE |
| 5.4.3 | Implement `generate_stream()` | Streaming generation via Bedrock Converse API (`converse_stream()`). Yields tokens as they arrive. *(Originally planned as `invoke_model_with_response_stream()`; upgraded to Converse API.)* | ✅ DONE |
| 5.4.4 | Create system prompt template | Template that instructs the LLM to: answer only from provided context, cite sources, say "I don't know" when context is insufficient. | ✅ DONE |
| 5.4.5 | Write LLM integration tests | Test with mock Bedrock client. Verify streaming yields tokens correctly. | ✅ DONE |

#### 5.5 — Context Assembly & Prompt Engineering

| # | Task | Details | Status |
|---|---|---|---|
| 5.5.1 | Create prompt builder | `backend/app/services/prompt_builder.py` — assembles the full prompt from system instructions + retrieved chunks + conversation history + user question. | ✅ DONE |
| 5.5.2 | Implement context window budgeting | Calculate token usage across all prompt sections. Ensure total stays within model's context window. Prioritize: system prompt > retrieved chunks > recent messages > summary. Truncate if necessary. **Post-deploy fix:** context window changed from hardcoded 8,000 to configurable `settings.llm.context_window` (default 128,000 for Nova Micro). | ✅ DONE |
| 5.5.3 | Write prompt assembly tests | Verify correct ordering, token budget enforcement, truncation behavior. | ✅ DONE |

#### 5.6 — SSE Streaming Endpoint

| # | Task | Details |
|---|---|---|
| 5.6.1 | `POST /api/chats/{chat_id}/messages` | Accepts user message. Returns `StreamingResponse` (SSE). |
| 5.6.2 | Implement SSE event generator | Async generator that: (1) stores user message in DynamoDB, (2) retrieves context, (3) assembles prompt, (4) calls `generate_stream()`, (5) yields SSE events (`token`, `sources`, `done`). |
| 5.6.3 | Persist complete response | After stream completes, store the full assistant message in DynamoDB (even if client disconnects). |
| 5.6.4 | Implement error SSE event | On LLM failure: yield `event: error` with error details, then close stream. |
| 5.6.5 | Implement graceful fallback | If SSE fails to establish: client can `POST` and then poll `GET /api/chats/{chat_id}/messages` for the response. |
| 5.6.6 | Write SSE streaming tests | Test token-by-token event delivery, error events, mid-stream disconnection handling. |

#### 5.7 — Conversation Memory (Sliding Window + Summary)

| # | Task | Details |
|---|---|---|
| 5.7.1 | Implement `SlidingWindowMemory` | Concrete implementation of `ConversationMemory`. Backed by DynamoDB. |
| 5.7.2 | Implement `get_context()` | Returns `(running_summary, recent_messages)` for a chat. Recent = last N messages (configurable, default 10). Summary = `chat_sessions.running_summary`. |
| 5.7.3 | Implement `add_message()` | Stores message in DynamoDB. Checks if batch fold is needed (i.e., messages outside window ≥ batch_fold_size). |
| 5.7.4 | Implement `trigger_summarization()` | Calls Nova Micro (via `LLMProvider`) to fold old messages into the running summary. Updates `running_summary` and `summary_through_index` in DynamoDB. |
| 5.7.5 | Implement batch folding logic | Every `batch_fold_size` (default 5) messages that fall off the window, trigger a single summarization call. |
| 5.7.6 | Write memory unit tests | Test window sliding, batch fold triggering, summary accumulation across multiple folds. |

#### 5.8 — Frontend: Chat Interface

| # | Task | Details |
|---|---|---|
| 5.8.1 | Create `ChatInterface` component | Right panel (2/3 width). Contains message history + input area. |
| 5.8.2 | Create `MessageList` component | Scrollable list of messages. User messages right-aligned, AI messages left-aligned. Each shows sender + timestamp. Auto-scrolls to bottom on new message. |
| 5.8.3 | Create `MessageBubble` component | Styled chat bubble. Rounded corners, shadow. Supports Markdown rendering for AI responses (use `react-markdown`). |
| 5.8.4 | Create `ChatInput` component | Text input field + send button. Disabled while waiting for response. Supports Enter to send, Shift+Enter for newline. |
| 5.8.5 | Implement SSE client | On message send: `POST /api/chats/{chat_id}/messages` with `Accept: text/event-stream`. Parse SSE events, append tokens to the current AI message in real-time. |
| 5.8.6 | Implement streaming UI state | Show typing indicator while streaming. Append tokens to a growing message bubble. On `done` event, finalize message. On `error` event, show error inline. |
| 5.8.7 | Implement source attribution UI | After `sources` SSE event, display source references below the AI message (e.g., "📄 Paper X, Page 7"). |
| 5.8.8 | Implement SSE fallback | If EventSource fails, fall back to polling `GET /api/chats/{chat_id}/messages` with retry. |
| 5.8.9 | Load chat history on chat selection | When a chat is selected, fetch existing messages via `GET /api/chats/{chat_id}/messages` and render them. |

### Phase 5 Acceptance Criteria

- [x] Chat sessions can be created, listed, and deleted within a project. **(Backend complete, frontend UI complete)**
- [x] Sending a message retrieves relevant document chunks via hybrid search (scoped to project). **(Retrieval service complete with 8/8 tests passing)**
- [x] LLM integration with AWS Bedrock Nova models working. **(BedrockNovaProvider complete with 15/15 tests passing)**
- [x] AI responses stream to the UI in real-time via SSE. **(ChatService + SSE endpoint + React SSE client complete)**
- [ ] Responses are grounded in document content (not hallucinated). **(Requires end-to-end testing — Phase 6)**
- [x] Source attribution (document title, page number) appears with AI responses. **(Sources sent via SSE events, displayed in ChatInterface)**
- [x] Conversation memory works: long conversations maintain context via sliding window + summary. **(SlidingWindowMemory complete with 11/11 tests passing)**
- [x] Summarization uses Nova Micro for cost optimization. **(Interface accepts any LLMProvider; Nova Micro is recommended)**
- [ ] SSE graceful fallback works when streaming connection fails. **(Frontend cancel/error handling present; server-side fallback TBD in Phase 6)**

**Implementation Notes (Phase 5.1-5.8):**
- ✅ DynamoDB tables: `chat_sessions` (with GSI for project queries), `chat_messages`
- ✅ ChatRepository: 10 async methods for full CRUD operations on chats and messages
- ✅ REST API: 6 endpoints (create chat, list chats, get chat, get messages, delete chat, **send message with SSE**)
- ✅ Frontend: Chat types, API client methods (incl. sendMessageStream), AppContext integration
- ✅ React Components: ChatList, CreateChatModal, ChatListItem, **ChatInterface (fully functional with streaming)**
- ✅ UI Layout: 3-panel layout (Projects | Documents/Chats tabs | Chat Interface)
- ✅ RetrievalService: Project-scoped hybrid search with context formatting and source extraction
- ✅ BedrockNovaProvider: Nova model integration with streaming and retry logic
- ✅ System Prompts: RAG Q&A and conversation summarization templates
- ✅ PromptBuilder: Token counting with tiktoken, context window budgeting, priority-based truncation
- ✅ ChatService: Orchestrates full RAG pipeline with SSE streaming
- ✅ SlidingWindowMemory: Sliding window + LLM-based summarization for long conversations
- ✅ **Phase 5 Tests: 89/89 passing** (13 chat repo + 12 router + 8 retrieval + 15 LLM + 21 prompt + 9 chat service + 11 conversation memory = 100% pass rate)

---

## 7. Phase 6 — Integration, Polish & Testing

**Goal**: Full end-to-end flow works reliably. Error handling is robust. UI is polished and responsive.

### Tasks

#### 6.1 — End-to-End Integration Testing

| # | Task | Details |
|---|---|---|
| 6.1.1 | Write E2E test: full workflow | Create project → upload document → wait for processing → create chat → ask question → verify answer cites the document. |
| 6.1.2 | Test multi-project isolation | Upload same document to two projects. Ask a question in Project A — verify only Project A's linked docs are searched. |
| 6.1.3 | Test document deduplication | Upload the same PDF twice. Verify it's processed once, linked twice. |
| 6.1.4 | Test long conversation memory | Send 20+ messages in a chat. Verify early context is preserved via summary. |
| 6.1.5 | Test concurrent uploads | Upload 5 documents simultaneously. Verify all are processed (sequentially by workers, but all eventually reach `ready`). |

#### 6.2 — Error Handling & Graceful Degradation

| # | Task | Details |
|---|---|---|
| 6.2.1 | Backend global exception handler | FastAPI exception handlers for: 404 (not found), 422 (validation), 500 (internal). Return consistent `ErrorResponse` JSON. |
| 6.2.2 | Bedrock failure handling | If Bedrock is unreachable or rate-limited: return a user-friendly error message in the SSE stream, don't crash the server. *(Done: ChatService catches `ClientError`, `EndpointConnectionError`, `RuntimeError` from Bedrock — classifies by error code and emits user-friendly SSE error events. Non-streaming path raises `ServiceUnavailableError`. 9 new tests.)* |
| 6.2.3 | S3 failure handling | If S3 upload fails: return error, don't create document record. If S3 is unreachable for download during processing: retry, then mark document as `failed`. *(Done: `StorageService` now retries transient S3 errors — `InternalError`, `ServiceUnavailable`, `SlowDown`, `RequestTimeout` — with exponential backoff up to 3 attempts. All S3 methods log errors before re-raising.)* |
| 6.2.4 | DynamoDB failure handling | If DynamoDB is unreachable: chat endpoints return 503 with "Service temporarily unavailable". *(Done: `ChatRepository` now distinguishes "not found" from service failures and logs errors. Chats router wraps all DynamoDB calls in try/except returning 503. `ConversationMemory` summarisation errors are non-blocking. `ChatService` degrades gracefully on memory read failures.)* |
| 6.2.5 | Frontend error boundaries | React error boundaries around major components. Toast notifications for API errors. |
| 6.2.6 | Frontend retry logic | Auto-retry failed API calls (1 retry with 2s delay). SSE reconnection with exponential backoff (max 3 attempts). |

#### 6.3 — UI Polish

| # | Task | Details |
|---|---|---|
| 6.3.1 | Responsive layout | Mobile breakpoint: project list becomes a slide-out drawer with hamburger menu toggle. Chat interface takes full width. |
| 6.3.2 | Empty states | "No projects yet — create one!" / "No documents — upload a paper!" / "No chats — start a conversation!" |
| 6.3.3 | Loading states | Skeleton loaders for project list, document list, chat history. Spinner for message sending. Typing indicator during SSE streaming. |
| 6.3.4 | Visual polish | Consistent rounded borders (`rounded-lg`), shadows (`shadow-md`), padding (`p-4`), color scheme. Light mode (dark mode as future enhancement). |
| 6.3.5 | Keyboard shortcuts | Enter to send message, Escape to cancel, Ctrl+N for new chat (optional). |
| 6.3.6 | Markdown rendering in chat | AI responses support Markdown: headers, bold, italic, code blocks, tables, lists. Use `react-markdown` + `remark-gfm`. |

#### 6.4 — Re-Embedding Pipeline

| # | Task | Details |
|---|---|---|
| 6.4.1 | Create re-embed API endpoint | `POST /api/admin/re-embed` — triggers bulk re-embedding of all chunks where `embedding_model_id != current model`. |
| 6.4.2 | Implement re-embed task | Celery task that processes chunks in batches. Updates embeddings + `embedding_model_id`. Handles partial progress (resumable). |
| 6.4.3 | Add mixed-model query support | During re-embedding, search queries only match chunks with the current model ID. |

### Phase 6 Acceptance Criteria

- [ ] Full workflow (create project → upload → chat → get grounded answer) works end-to-end.
- [ ] All error scenarios produce user-friendly messages (not stack traces).
- [ ] UI is responsive on mobile (project list as drawer).
- [ ] Empty states, loading states, and error states are handled in the UI.
- [ ] Re-embedding pipeline can migrate all vectors to a new model.

---

## 8. Phase 7 — Terraform & Deployment

**Goal**: AWS infrastructure is defined in Terraform and the application can be deployed to a production-like environment.

### Tasks

#### 7.1 — Terraform Foundation

| # | Task | Details |
|---|---|---|
| 7.1.1 | Initialize Terraform project | `infra/` directory, `main.tf`, `variables.tf`, `outputs.tf`, `terraform.tfvars`. |
| 7.1.2 | Configure Terraform backend | S3 bucket + DynamoDB table for remote state storage and locking. |
| 7.1.3 | Define provider | AWS provider with configurable region. |
| 7.1.4 | Create environment variable system | `terraform.tfvars` files for dev/prod environments. |

#### 7.2 — AWS Resource Definitions

| # | Task | Details |
|---|---|---|
| 7.2.1 | VPC & Networking | VPC, public/private subnets, NAT gateway, security groups. |
| 7.2.2 | RDS (PostgreSQL + pgvector) | RDS instance, parameter group (enable pgvector), subnet group, security group. |
| 7.2.3 | DynamoDB tables | `chat_sessions` and `chat_messages` tables with correct key schemas. |
| 7.2.4 | S3 bucket | Bucket for document storage, lifecycle policies, encryption. |
| 7.2.5 | ECR repositories | Container registries for backend and worker images. |
| 7.2.6 | ECS / Fargate cluster | Cluster, task definitions (backend, worker), services, auto-scaling. |
| 7.2.7 | Application Load Balancer | ALB, target groups, listener rules, health checks. |
| 7.2.8 | ElastiCache (Redis) | Redis cluster for Celery broker (or switch to SQS — see 7.2.9). |
| 7.2.9 | SQS queues (alternative) | If switching from Celery+Redis to SQS in production: define queues, dead-letter queue, IAM policies. |
| 7.2.10 | IAM roles & policies | ECS task roles with permissions for: Bedrock, S3, DynamoDB, SQS/ElastiCache. |
| 7.2.11 | CloudWatch | Log groups for ECS tasks, basic alarms (5xx rate, high CPU). |
| 7.2.12 | Bedrock model access | Ensure Bedrock model access is enabled for Titan Embeddings V2 and Nova models in the account/region. |

#### 7.3 — Deployment Pipeline

| # | Task | Details |
|---|---|---|
| 7.3.1 | Create Dockerfiles (production) | Multi-stage Dockerfiles using `uv sync --frozen --no-dev` for production dependency installation. Optimized image size with separate build and runtime stages. Copy `uv.lock` and `pyproject.toml` first for Docker layer caching. |
| 7.3.2 | Create deployment script | Script to: build images → push to ECR → update ECS service → run DB migrations. |
| 7.3.3 | Create `terraform plan` / `apply` workflow | Document the deployment steps. Optionally, set up a basic CI/CD pipeline (GitHub Actions or similar). |
| 7.3.4 | Environment configuration for production | Production `.env` values, secrets management (AWS Secrets Manager or SSM Parameter Store). |

### Phase 7 Acceptance Criteria

- [ ] `terraform plan` shows a clean resource creation plan.
- [ ] `terraform apply` provisions all AWS resources.
- [ ] Application deploys to ECS/Fargate and is accessible via ALB.
- [ ] Database migrations run against RDS PostgreSQL.
- [ ] DynamoDB tables are created.
- [ ] Application communicates with Bedrock, S3, and DynamoDB in the AWS environment.

---

## 9. Project Structure

```
research-assist-ai/
├── design/
│   └── phase-1/
│       ├── requirement-specification.md
│       ├── design-doc.md
│       └── implementation-plan.md
│
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                          # FastAPI application entry point
│   │   │
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py                    # Pydantic settings, YAML loader
│   │   │   └── interfaces/
│   │   │       ├── __init__.py              # Barrel export of all interfaces
│   │   │       ├── vector_store.py          # VectorStore protocol
│   │   │       ├── embedding_provider.py    # EmbeddingProvider protocol
│   │   │       ├── llm_provider.py          # LLMProvider protocol
│   │   │       ├── document_parser.py       # DocumentParser protocol
│   │   │       ├── task_queue.py            # TaskQueue protocol
│   │   │       └── conversation_memory.py   # ConversationMemory protocol
│   │   │
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── project.py                   # SQLAlchemy: Project model
│   │   │   ├── document.py                  # SQLAlchemy: Document model
│   │   │   ├── project_document.py          # SQLAlchemy: ProjectDocument link model
│   │   │   └── document_chunk.py            # SQLAlchemy: DocumentChunk model (PGVector)
│   │   │
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── project.py                   # Pydantic: Project request/response schemas
│   │   │   ├── document.py                  # Pydantic: Document schemas
│   │   │   ├── chat.py                      # Pydantic: Chat/message schemas
│   │   │   └── common.py                    # Pydantic: Pagination, errors, envelopes
│   │   │
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── project_repo.py              # Project CRUD (PostgreSQL)
│   │   │   ├── document_repo.py             # Document CRUD (PostgreSQL)
│   │   │   └── chat_repo.py                 # Chat CRUD (DynamoDB)
│   │   │
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── project_service.py           # Project business logic
│   │   │   ├── document_service.py          # Document upload, linking, status
│   │   │   ├── storage_service.py           # S3 operations
│   │   │   ├── ingestion_service.py         # Parse → chunk → embed → store orchestration
│   │   │   ├── retrieval_service.py         # Hybrid search + context formatting
│   │   │   ├── chat_service.py              # Chat orchestration, SSE streaming
│   │   │   └── prompt_builder.py            # Prompt assembly, token budgeting
│   │   │
│   │   ├── implementations/
│   │   │   ├── __init__.py
│   │   │   ├── pgvector_store.py            # VectorStore → PGVector + BM25
│   │   │   ├── titan_embedding_provider.py  # EmbeddingProvider → Bedrock Titan V2
│   │   │   ├── bedrock_nova_provider.py     # LLMProvider → Bedrock Nova
│   │   │   ├── pymupdf4llm_parser.py        # DocumentParser → pymupdf4llm
│   │   │   ├── pdfplumber_parser.py         # DocumentParser → pdfplumber
│   │   │   ├── celery_task_queue.py         # TaskQueue → Celery + Redis
│   │   │   └── sliding_window_memory.py     # ConversationMemory → DynamoDB + Nova Micro
│   │   │
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── projects.py                  # /api/projects/* endpoints
│   │   │   ├── documents.py                 # /api/documents/* endpoints
│   │   │   ├── chats.py                     # /api/chats/* endpoints
│   │   │   └── admin.py                     # /api/admin/* endpoints (re-embed, etc.)
│   │   │
│   │   ├── worker/
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py                # Celery application instance
│   │   │   └── tasks.py                     # Task definitions (process_document, re_embed)
│   │   │
│   │   └── db/
│   │       ├── __init__.py
│   │       ├── base.py                      # SQLAlchemy engine, session, base model
│   │       ├── dynamodb.py                  # DynamoDB client, table references
│   │       └── init_db.py                   # Table creation scripts (DynamoDB, pgvector ext)
│   │
│   ├── alembic/
│   │   ├── alembic.ini
│   │   ├── env.py
│   │   └── versions/                        # Migration files
│   │
│   ├── tests/
│   │   ├── unit/
│   │   ├── integration/
│   │   └── e2e/
│   │
│   ├── config.yaml                          # Application config (defaults)
│   ├── pyproject.toml                       # Python project config + dependencies (PEP 621)
│   ├── uv.lock                              # uv lockfile — reproducible installs (committed)
│   ├── .python-version                      # Python version pin (e.g., "3.12") — used by uv
│   ├── Dockerfile                           # Production Dockerfile (uses uv sync --frozen)
│   └── .env.local                           # Local environment variables (git-ignored)
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── layout/
│   │   │   │   ├── AppLayout.tsx            # Two-panel layout shell
│   │   │   │   └── MobileDrawer.tsx         # Responsive drawer for mobile
│   │   │   ├── projects/
│   │   │   │   ├── ProjectList.tsx           # Left panel project list
│   │   │   │   ├── ProjectCard.tsx           # Individual project card
│   │   │   │   ├── CreateProjectModal.tsx    # New project form
│   │   │   │   └── DocumentUploadArea.tsx    # Document drag-and-drop upload
│   │   │   ├── chats/
│   │   │   │   ├── ChatList.tsx              # Chat session list within a project
│   │   │   │   ├── ChatInterface.tsx         # Right panel chat container
│   │   │   │   ├── MessageList.tsx           # Scrollable message history
│   │   │   │   ├── MessageBubble.tsx         # Individual message (user or AI)
│   │   │   │   ├── ChatInput.tsx             # Text input + send button
│   │   │   │   ├── SourceAttribution.tsx     # Source references below AI messages
│   │   │   │   └── StreamingIndicator.tsx    # Typing/streaming indicator
│   │   │   └── common/
│   │   │       ├── LoadingSpinner.tsx
│   │   │       ├── ErrorBoundary.tsx
│   │   │       ├── EmptyState.tsx
│   │   │       └── Toast.tsx
│   │   │
│   │   ├── context/
│   │   │   └── AppContext.tsx                # Global state (projects, chats, selection)
│   │   │
│   │   ├── hooks/
│   │   │   ├── useProjects.ts
│   │   │   ├── useChats.ts
│   │   │   ├── useMessages.ts
│   │   │   └── useSSE.ts                    # SSE connection + event parsing
│   │   │
│   │   ├── services/
│   │   │   ├── apiClient.ts                 # Centralized Axios/fetch wrapper
│   │   │   ├── projectApi.ts                # Project API calls
│   │   │   ├── documentApi.ts               # Document API calls
│   │   │   └── chatApi.ts                   # Chat API calls
│   │   │
│   │   ├── types/
│   │   │   └── index.ts                     # TypeScript interfaces matching API schemas
│   │   │
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css                        # Tailwind directives
│   │
│   ├── tailwind.config.js
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── package.json
│   └── Dockerfile
│
├── infra/                                   # Terraform (Phase 7)
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── terraform.tfvars
│   └── modules/
│       ├── vpc/
│       ├── rds/
│       ├── dynamodb/
│       ├── s3/
│       ├── ecs/
│       └── iam/
│
├── docker-compose.yml                       # Local development services
├── .gitignore
└── README.md
```

---

## 10. Dependency Map

This shows which tasks/phases depend on others. Tasks within a phase can generally be parallelized unless noted.

```
Phase 1 (Scaffolding)
  │
  ▼
Phase 2 (Abstractions & Models)
  │
  ├──────────────────────────────┐
  ▼                              ▼
Phase 3 (Project Mgmt)     Phase 4 (Document Ingestion)
  │                              │   - Depends on Phase 3 for project linking
  │                              │   - Backend can start without Phase 3 frontend
  │                              │
  └──────────┬───────────────────┘
             ▼
Phase 5 (Chat & RAG)
  │   - Depends on Phase 4 (documents must be indexed)
  │   - Depends on Phase 3 (chats belong to projects)
  │
  ▼
Phase 6 (Integration & Polish)
  │   - Depends on all prior phases
  │
  ▼
Phase 7 (Terraform & Deployment)
  │   - Can start in parallel from Phase 4 onwards (networking, S3, DynamoDB)
  │   - ECS/deployment tasks depend on Phase 6 completion
```

### Cross-Phase Dependencies (Notable)

| Task | Depends On | Reason |
|---|---|---|
| 4.1.3 (Link document to project) | 3.1.x (Project CRUD) | Needs project to exist |
| 4.4 (Embedding generation) | AWS Bedrock access | Needs IAM credentials configured |
| 5.3 (Retrieval) | 4.5 (PGVector store) | Needs indexed documents |
| 5.4 (LLM integration) | AWS Bedrock access | Needs IAM credentials configured |
| 5.7 (Conversation memory) | 5.1 (DynamoDB chat repo) | Needs chat storage layer |
| 5.8.5 (SSE client) | 5.6 (SSE server endpoint) | Client consumes server events |
| 6.4 (Re-embedding) | 4.4 + 4.5 (Embedding + vector store) | Re-processes existing vectors |

---

## 11. Risk Register

| # | Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|---|
| 1 | **Bedrock model access not enabled** | Blocks embedding + LLM work | Medium | Verify Bedrock model access in AWS console early (Phase 1). Request access for Titan Embeddings V2, Nova Micro, Nova Lite, Nova Pro. |
| 2 | **pymupdf4llm poor table extraction on specific PDFs** | Garbled data in chunks | Medium | pdfplumber fallback is already designed. Test with a variety of real research papers early in Phase 4. |
| 3 | **PGVector performance degrades at scale** | Slow retrieval | Low (pet project scale) | Monitor query times. VectorStore abstraction allows migration to Pinecone/OpenSearch if needed. |
| 4 | **Context window overflow** | LLM call fails or truncates | Medium | Token budgeting in prompt builder (Task 5.5.2). Aggressive truncation of older context if budget is exceeded. |
| 5 | **SSE connection blocked by corporate proxy** | No streaming in some network environments | Low | Fallback to polling is already designed (Task 5.6.5, 5.8.8). |
| 6 | **Celery worker crashes during long document processing** | Document stuck in `processing` state | Medium | Add a timeout watchdog: if a document stays in `processing` for > 10 minutes, reset to `queued` for retry. Max 3 retries before `failed`. |
| 7 | **DynamoDB cold start latency** | Slow first chat load | Low | DynamoDB on-demand capacity handles this. Not a concern at pet-project scale. |
| 8 | **Terraform state corruption** | Infrastructure drift, broken deployments | Low | Use S3 + DynamoDB state locking. Never run `terraform apply` concurrently. |
| 9 | **Embedding model change requires full re-embed** | Hours of processing for large document sets | Low (planned for) | Re-embedding pipeline (Task 6.4) handles this. Designed to be resumable and run in background. |
| 10 | **Chunking parameters produce poor retrieval quality** | Irrelevant or missing context in answers | Medium | Parameters are configurable. Plan to experiment with chunk sizes during Phase 5 testing. Start with defaults, tune based on real query results. |

---

## 12. Post-Development Enhancements

### 12.1 Dark Mode (✅ Complete — 2026-03-01)

**Objective:** Add a light/dark theme toggle to the frontend UI.

**Implementation Details:**

| Aspect | Detail |
|---|---|
| **Toggle location** | Sun/Moon icon next to the "Research Assist AI" title in the desktop sidebar header |
| **Icons** | Sun SVG = light mode (current), Moon SVG = dark mode |
| **Persistence** | `localStorage` key `research-assist-theme` |
| **Default** | System preference via `matchMedia('(prefers-color-scheme: dark)')` |
| **Mechanism** | `dark` CSS class toggled on `<html>` element |
| **Tailwind v4** | `@custom-variant dark (&:where(.dark, .dark *));` in `index.css` |

**Files Created:**
- `frontend/src/context/themeContextDef.ts` — `Theme` type, `ThemeContextType` interface, `ThemeContext` (separated from provider for react-refresh compatibility)
- `frontend/src/context/ThemeContext.tsx` — `ThemeProvider` component with localStorage + system preference logic
- `frontend/src/components/ThemeToggle.tsx` — Sun/Moon toggle button component

**Files Modified:**
- `frontend/src/index.css` — Added `@custom-variant dark` directive
- `frontend/src/context/hooks.ts` — Added `useTheme()` hook
- `frontend/src/App.tsx` — Wrapped app in `ThemeProvider`, added `ThemeToggle`, added `dark:` variants to layout
- All 13 UI components updated with `dark:` Tailwind variants: `ProjectList`, `ProjectCard`, `ChatList`, `ChatListItem`, `ChatInterface` (incl. `MessageBubble`, `SourceList`), `DocumentManager`, `DocumentListItem`, `DocumentUploadArea`, `CreateProjectModal`, `CreateChatModal`, `ErrorBoundary`, `Toast`, `MarkdownContent`

**Dark palette conventions:**
- Main backgrounds: `dark:bg-gray-900`
- Cards/panels: `dark:bg-gray-800`
- Inputs/tables: `dark:bg-gray-700`
- Borders: `dark:border-gray-700`
- Text hierarchy: `dark:text-gray-100` / `200` / `300` / `400`
- Status badges/alerts: `dark:bg-{color}-900/30`
- Hover states: `dark:hover:bg-gray-700`

---

*This implementation plan is ready for execution. Begin with Phase 1 and progress sequentially. Phases 3 and 4 backend tasks can partially overlap once Phase 2 is complete.*