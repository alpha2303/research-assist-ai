# Research Assist AI — Design Document

> **Status**: Design Complete
>
> **Last Updated**: 2025-02-15
>
> **Author**: Rahul (with AI-assisted design - Claude Opus 4.6)

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Technology Stack](#2-technology-stack)
3. [Architecture Overview](#3-architecture-overview)
4. [Frontend Design](#4-frontend-design)
5. [Backend Design](#5-backend-design)
6. [Data Model](#6-data-model)
7. [RAG Pipeline Design](#7-rag-pipeline-design)
8. [Streaming & Communication](#8-streaming--communication)
9. [Authentication](#9-authentication)
10. [Infrastructure & Deployment](#10-infrastructure--deployment)
11. [Local Development](#11-local-development)
12. [Design Principles & Abstractions](#12-design-principles--abstractions)
13. [Confirmed Decisions Summary](#13-confirmed-decisions-summary)
14. [Future Enhancements](#14-future-enhancements)

---

## 1. Project Overview

Research Assist AI is a web application that enables research teams to ingest, aggregate, and converse with research papers. Users organize their work into **projects**, upload research papers, and engage in **chat sessions** where an AI assistant answers questions grounded exclusively in the content of the uploaded papers.

### Core Capabilities

- **Project Management**: Logical grouping of research papers into projects.
- **Document Ingestion**: Upload research papers (PDF) which are parsed, chunked, embedded, and stored for retrieval.
- **Conversational Q&A**: Chat with an AI assistant that answers questions based solely on the content of the project's associated papers.
- **Multi-Chat Support**: Multiple independent chat sessions per project, each with its own conversation history but shared access to the project's document corpus.
- **Source Attribution**: Responses should reference the source document and location (e.g., page number) where the information was found.

---

## 2. Technology Stack

### Confirmed Stack

| Layer | Technology | Notes |
|---|---|---|
| **Frontend** | React + TypeScript + Tailwind CSS | SPA with responsive design |
| **Backend** | Python + FastAPI | Async-native, high performance for I/O-bound workloads |
| **Python Project Manager** | uv (by Astral) | Rust-powered, 10–100x faster than pip. Lockfile (`uv.lock`), Python version management, PEP 621 native. |
| **LLM Provider** | AWS Bedrock | Amazon Nova Micro (development), Nova Lite/Pro (production) |
| **Embedding Model** | Amazon Titan Embeddings V2 (via Bedrock) | 1024 dimensions, 8K token input, ~$0.02/1M tokens |
| **PDF Parser** | pymupdf4llm (primary), pdfplumber (fallback) | Markdown output preserves table structure; fallback for edge cases |
| **Vector Database** | PGVector (PostgreSQL extension) | Runs inside existing PostgreSQL instance |
| **Relational Database** | PostgreSQL | Local for development, Amazon RDS for production |
| **Search Strategy** | Hybrid — PGVector + PostgreSQL BM25 | Vector similarity + keyword search from day one |
| **Chat/Conversation Store** | Amazon DynamoDB | Partition key = `chat_id`, sort key = `timestamp` |
| **File Storage** | Amazon S3 | Source-of-truth for uploaded research papers |
| **Task Queue (Local)** | Celery + Redis | Async document processing; abstracted behind `TaskQueue` interface |
| **Task Queue (Production)** | AWS SQS | Swappable via `TaskQueue` abstraction |
| **Infrastructure as Code** | Terraform | Generalized IaC, provider-agnostic |
| **Containerization** | Docker + Docker Compose | Local development environment; Dockerfiles use `uv sync --frozen` for fast, reproducible builds |

### Rationale for Key Choices

#### Python + FastAPI over Node.js / Go
- Python has the dominant AI/ML ecosystem (LangChain, Boto3, PDF parsers, etc.).
- FastAPI provides async support, automatic OpenAPI docs, and Pydantic-based validation.
- The system is I/O-bound (LLM API calls, vector search, file parsing) — Python's async performance is more than sufficient.
- Performance bottlenecks will be in external service calls (Bedrock, PGVector), not the language runtime.

#### PGVector over Pinecone / OpenSearch
- Zero additional cost — runs as an extension inside the existing PostgreSQL instance.
- Zero additional infrastructure — no separate vector service to manage.
- Sufficient performance for team-scale usage (hundreds to thousands of documents).
- PostgreSQL's built-in full-text search (BM25 via `tsvector`/`tsquery`) enables **hybrid retrieval from day one** at zero additional cost.
- **Abstracted behind a `VectorStore` interface** to allow future migration to Pinecone, OpenSearch, or other providers without business logic changes.

#### Hybrid Search (Vector + BM25) from Day One
- **Vector search** excels at semantic matching ("What methodology was used?" matches "The approach employed was...").
- **BM25 keyword search** excels at exact term matching — critical for research papers which are dense with domain-specific terminology, acronyms, and exact metrics (e.g., "BLEU score", "Table 3", "ResNet-50").
- PostgreSQL BM25 is built-in (`tsvector` column + GIN index) — zero additional cost or infrastructure.
- Retrieval combines both scores via configurable weighted fusion (`bm25_weight` + `vector_weight`).

#### pymupdf4llm with pdfplumber Fallback
- **pymupdf4llm** (part of the PyMuPDF package) converts PDFs to Markdown format, preserving table structure as Markdown tables — ideal for LLM consumption and critical for research papers with result comparison tables.
- **pdfplumber** serves as a fallback parser for PDFs where pymupdf4llm produces poor output (e.g., unusual layouts). It has a dedicated `.extract_tables()` method for robust table extraction.
- Both are lightweight, open-source, and pet-project-friendly — no enterprise dependencies.
- Abstracted behind the `DocumentParser` interface for easy swapping.

#### Celery + Redis (Local) / SQS (Production)
- Document ingestion (parse → chunk → embed → store) is CPU/IO intensive and must run **asynchronously** so the user isn't blocked waiting.
- **Celery + Redis** for local development: Celery is a distributed task queue framework; Redis acts as both the message broker (transporting task messages) and result backend (storing task outcomes). Lightweight and simple to run via Docker Compose.
- **AWS SQS** for production: Fully managed, serverless, auto-scaling message queue.
- **Abstracted behind a `TaskQueue` interface** so the switch from Celery to SQS requires no business logic changes.

#### DynamoDB for Chat Conversations
- Chat messages are append-heavy, read-sequentially — a perfect fit for DynamoDB's partition key + sort key model.
- Fully managed, serverless, auto-scaling on AWS.
- Cost-effective for low-to-moderate traffic.

#### Amazon Titan Embeddings V2
- Native Bedrock integration — same SDK, same billing, same IAM as the LLM.
- Configurable dimensions (256 / 512 / 1024) — start with 1024 for quality, can reduce later to optimize storage.
- 8K token input limit — important for longer research paper chunks.
- Most cost-effective embedding option on Bedrock.
- **Abstracted behind an `EmbeddingProvider` interface** for future model swaps.
- **Embedding model identifier stored in vector metadata** to support re-embedding if models are changed.

#### Amazon Nova (LLM) — Tiered by Environment
- **Development**: Amazon Nova Micro — cheapest, fastest for iteration and testing.
- **Production**: Amazon Nova Lite or Nova Pro — better quality for end-user-facing responses.
- **Abstracted behind an `LLMProvider` interface** to allow model/provider changes without code modifications.
- Bedrock charges per token (input + output) regardless of streaming vs. non-streaming delivery.

---

## 3. Architecture Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                          Frontend (React SPA)                       │
│                   React + TypeScript + Tailwind CSS                  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTPS (REST + SSE)
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     API Gateway / Load Balancer                      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
     ┌────────────────┐ ┌───────────────┐ ┌──────────────────┐
     │  Project &     │ │    Chat       │ │    Document      │
     │  Management    │ │    Service    │ │    Ingestion     │
     │  Service       │ │               │ │    Service       │
     └───────┬────────┘ └───────┬───────┘ └────────┬─────────┘
             │                  │                   │
             ▼                  ▼                   ▼
     ┌──────────────┐  ┌──────────────┐    ┌──────────────┐
     │  PostgreSQL   │  │  DynamoDB    │    │  S3 Bucket   │
     │  (Relational  │  │  (Chat       │    │  (File       │
     │   + PGVector) │  │   History)   │    │   Storage)   │
     └──────────────┘  └──────────────┘    └──────────────┘
                               │
                               ▼
                       ┌──────────────┐
                       │  AWS Bedrock  │
                       │  (Nova +     │
                       │   Titan Emb) │
                       └──────────────┘
```

### Backend Architecture: Microservices

The backend is decomposed into the following logical services:

| Service | Responsibility |
|---|---|
| **Project & Management Service** | CRUD operations for projects, document-project linking, metadata management |
| **Chat Service** | Chat session management, message handling, RAG retrieval, LLM interaction, SSE streaming |
| **Document Ingestion Service** | File upload, PDF parsing, chunking, embedding generation, vector storage |

> **Note**: For initial development, these may run as separate modules within a single FastAPI application (modular monolith), with a clear path to split into independent services later.

---

## 4. Frontend Design

### Layout

The UI consists of a single-page application with two primary vertical sections:

```
┌──────────────────────┬──────────────────────────────────────────┐
│                      │                                          │
│   Project List       │           Chat Interface                 │
│   (1/3 width)        │           (2/3 width)                    │
│                      │                                          │
│ ┌──────────────────┐ │  ┌────────────────────────────────────┐  │
│ │ + New Project    │ │  │                                    │  │
│ ├──────────────────┤ │  │        Chat History                │  │
│ │ Project A      ▼ │ │  │        (scrollable)                │  │
│ │   ├ + New Chat   │ │  │                                    │  │
│ │   ├ Chat 1       │ │  │  ┌──────────────────────────────┐  │  │
│ │   └ Chat 2       │ │  │  │ User message (right-aligned) │  │  │
│ ├──────────────────┤ │  │  └──────────────────────────────┘  │  │
│ │ Project B      ▼ │ │  │  ┌──────────────────────────────┐  │  │
│ │ Project C      ▼ │ │  │  │ AI message (left-aligned)    │  │  │
│ │                  │ │  │  └──────────────────────────────┘  │  │
│ └──────────────────┘ │  │                                    │  │
│                      │  ├────────────────────────────────────┤  │
│                      │  │  [Text input field]     [Send]     │  │
│                      │  └────────────────────────────────────┘  │
└──────────────────────┴──────────────────────────────────────────┘
```

### Left Section — Project List (1/3 width)

- Vertical list view component.
- First item: **"+ New Project"** button.
- Each project is a card with:
  - Project title (left-aligned).
  - Dropdown/expand button (right-aligned).
- Clicking the expand button reveals the chat list for that project (indented).
  - First item in chat list: **"+ New Chat"** button.
  - Each chat item is clickable — opens the chat in the right section.
- Document upload controls are accessible at the project level (e.g., an upload button/area within the expanded project view or a project settings panel).

### Right Section — Chat Interface (2/3 width)

- **Chat History**: Scrollable list of messages, sorted in descending order by timestamp (newest at bottom).
  - User messages: right-aligned.
  - AI messages: left-aligned.
  - Each message displays sender and timestamp.
- **Input Area**: Text input field with a send button at the bottom of the section.
- Streaming responses render incrementally as tokens arrive via SSE.

### Design Guidelines

- All components use **rounded borders** and **shadow effects**.
- **Sufficient padding** between components and screen edges.
- **Responsive design**: Works on desktop and mobile.
  - Mobile: Project list collapses into a drawer/hamburger menu.
- Follow standard UX conventions for chat interfaces.

---

## 5. Backend Design

### API Design (RESTful)

#### Project Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/projects` | Create a new project |
| `GET` | `/api/projects` | List all projects |
| `GET` | `/api/projects/{project_id}` | Get project details |
| `PUT` | `/api/projects/{project_id}` | Update project metadata |
| `DELETE` | `/api/projects/{project_id}` | Delete a project |

#### Document Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/documents/upload` | Upload a document (global) |
| `POST` | `/api/projects/{project_id}/documents` | Link a document to a project |
| `DELETE` | `/api/projects/{project_id}/documents/{document_id}` | Unlink a document from a project |
| `GET` | `/api/projects/{project_id}/documents` | List documents linked to a project |
| `GET` | `/api/documents/{document_id}/status` | Get processing status of a document |

#### Chat Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/projects/{project_id}/chats` | Create a new chat session |
| `GET` | `/api/projects/{project_id}/chats` | List chats in a project |
| `GET` | `/api/chats/{chat_id}/messages` | Get chat message history |
| `POST` | `/api/chats/{chat_id}/messages` | Send a message (returns SSE stream) |
| `DELETE` | `/api/chats/{chat_id}` | Delete a chat session |

### SSE Streaming (Chat Responses)

When a user sends a message via `POST /api/chats/{chat_id}/messages`, the server:
1. Stores the user message in DynamoDB.
2. Retrieves relevant document chunks from PGVector (scoped to the project's linked documents).
3. Assembles the prompt: system instructions + retrieved context + conversation history + user question.
4. Calls Bedrock `invoke_model_with_response_stream()`.
5. Returns a `StreamingResponse` (SSE) — tokens are sent to the client as they arrive.
6. Once the stream completes, the full AI response is persisted to DynamoDB.

#### SSE Event Format

```
event: token
data: {"content": "The", "index": 0}

event: token
data: {"content": " research", "index": 1}

event: token
data: {"content": " shows", "index": 2}

...

event: sources
data: {"sources": [{"document_id": "abc", "title": "Paper X", "page": 7}]}

event: done
data: {"message_id": "msg_123", "total_tokens": 342}

event: error
data: {"error": "Model invocation failed", "code": "BEDROCK_ERROR"}
```

#### Graceful Fallback

- If SSE connection drops mid-stream, the client can fetch the complete message via `GET /api/chats/{chat_id}/messages` once the server finishes generation.
- The backend always persists the full response regardless of client connection state.
- Client implements automatic reconnection with exponential backoff.
- If streaming fails entirely, the system falls back to a synchronous request/response pattern.

---

## 6. Data Model

### Global Document Storage Architecture

Documents and their chunks are stored at the **global level**, not per-project. When a user adds a document to a project, a **linking reference** is created between the project and the document. This architecture minimizes duplicate processing — if the same paper is uploaded to multiple projects, it is parsed, chunked, and embedded only once.

#### Deduplication Strategy

- A **SHA-256 hash** of the uploaded file is computed on upload.
- If a document with the same hash already exists, the existing document is linked to the project instead of re-processing.
- The user is informed that the document was already in the system and has been linked.

### PostgreSQL Schema (Relational + PGVector)

#### `projects` Table

| Column | Type | Description |
|---|---|---|
| `id` | UUID (PK) | Unique project identifier |
| `title` | VARCHAR(255) | Project title |
| `description` | TEXT | Optional project description |
| `created_at` | TIMESTAMP | Creation timestamp |
| `updated_at` | TIMESTAMP | Last update timestamp |

#### `documents` Table (Global)

| Column | Type | Description |
|---|---|---|
| `id` | UUID (PK) | Unique document identifier |
| `title` | VARCHAR(255) | Document title / filename |
| `s3_key` | VARCHAR(512) | S3 object key for the original file |
| `file_hash` | VARCHAR(64) | SHA-256 hash for deduplication |
| `file_size_bytes` | BIGINT | File size |
| `mime_type` | VARCHAR(128) | File MIME type |
| `status` | ENUM | `queued`, `processing`, `ready`, `failed` |
| `page_count` | INTEGER | Number of pages (if applicable) |
| `created_at` | TIMESTAMP | Upload timestamp |

#### `project_documents` Table (Linking)

| Column | Type | Description |
|---|---|---|
| `project_id` | UUID (FK → projects.id) | Project reference |
| `document_id` | UUID (FK → documents.id) | Document reference |
| `linked_at` | TIMESTAMP | When the document was added to the project |
| | **PK**: (`project_id`, `document_id`) | Composite primary key |

#### `document_chunks` Table (PGVector + BM25)

| Column | Type | Description |
|---|---|---|
| `id` | UUID (PK) | Unique chunk identifier |
| `document_id` | UUID (FK → documents.id) | Parent document |
| `chunk_index` | INTEGER | Ordering within the document |
| `content` | TEXT | Raw text content of the chunk |
| `page_number` | INTEGER | Source page number |
| `section_heading` | VARCHAR(512) | Section heading (if detected) |
| `token_count` | INTEGER | Number of tokens in the chunk |
| `embedding_model_id` | VARCHAR(128) | Model used to generate the embedding |
| `embedding` | VECTOR(1024) | Vector embedding (PGVector type) |
| `search_vector` | TSVECTOR | BM25 full-text search vector (auto-populated from `content`) |
| `created_at` | TIMESTAMP | Creation timestamp |

> **Indexes**:
> - HNSW or IVFFlat index on the `embedding` column for fast vector similarity search.
> - GIN index on the `search_vector` column for fast BM25 keyword search.
>
> **Query pattern (hybrid search)**:
> 1. Vector similarity: Retrieve chunks where `document_id IN (SELECT document_id FROM project_documents WHERE project_id = ?)` ordered by cosine similarity.
> 2. BM25 keyword: Retrieve chunks matching `tsquery` from the user's question, filtered by the same document scope.
> 3. Combine both result sets using weighted Reciprocal Rank Fusion: `final_score = (vector_weight × vector_score) + (bm25_weight × bm25_score)`.
> 4. Return top-k results by `final_score`.

### DynamoDB Schema (Chat Conversations)

#### `chat_sessions` Table

| Attribute | Type | Key |
|---|---|---|
| `project_id` | String | Partition Key |
| `chat_id` | String | Sort Key |
| `title` | String | — |
| `running_summary` | String | Running summary of older messages (sliding window) |
| `summary_through_index` | Number | Message index up to which the summary covers |
| `created_at` | String (ISO 8601) | — |
| `updated_at` | String (ISO 8601) | — |

#### `chat_messages` Table

| Attribute | Type | Key |
|---|---|---|
| `chat_id` | String | Partition Key |
| `timestamp` | String (ISO 8601) | Sort Key |
| `message_id` | String | — |
| `sender` | String (`user` / `assistant`) | — |
| `content` | String | — |
| `sources` | List (of source references) | — |
| `token_count` | Number | — |

---

## 7. RAG Pipeline Design

> **Status**: ✅ Confirmed

### 7.1 Document Ingestion Pipeline

When a user uploads a research paper, the following pipeline executes **asynchronously** via the task queue (Celery + Redis locally, SQS in production):

```
User uploads PDF
       │
       ▼
Compute SHA-256 hash → Check for duplicate
       │
       ├─ Duplicate found → Link existing document to project (skip processing)
       │
       └─ New document:
              │
              ▼
       Store original PDF in S3 (source of truth)
              │
              ▼
       Set document status = "processing"
              │
              ▼
       Parse PDF → Markdown (pymupdf4llm)
              │
              ├─ Parse failure → Retry with pdfplumber (fallback)
              │
              ▼
       Chunk Markdown text (recursive splitting)
              │
              ▼
       Generate embeddings per chunk (Titan Embeddings V2 via Bedrock)
              │
              ▼
       Store chunks + embeddings + BM25 search_vector in PGVector
              │
              ▼
       Link document to project (project_documents table)
              │
              ▼
       Set document status = "ready"
```

#### Processing Status Lifecycle

| Status | Meaning |
|---|---|
| `queued` | Upload received, task submitted to queue |
| `processing` | Worker is actively parsing/chunking/embedding |
| `ready` | Document fully processed and available for retrieval |
| `failed` | Processing failed after all retries (error details stored) |

The frontend polls `GET /api/documents/{id}/status` to display real-time progress to the user.

### 7.2 PDF Parsing

#### Primary Parser: pymupdf4llm

- Converts PDF pages to **Markdown format**, preserving:
  - Section headings (as `#`, `##`, `###`)
  - Table structure (as Markdown tables)
  - Paragraph boundaries
  - List formatting
- Markdown output is ideal for both LLM consumption and structured chunking.
- Research paper tables (result comparisons, metrics) are preserved as structured Markdown tables, maintaining row/column relationships.

#### Fallback Parser: pdfplumber

- Activated when pymupdf4llm produces empty or malformed output for a given PDF.
- Has a dedicated `.extract_tables()` method for robust table extraction.
- Output is converted to Markdown format for consistency with the primary parser's output.

#### Parser Selection Logic

```
Try pymupdf4llm.to_markdown(pdf_path)
       │
       ├─ Success (non-empty, valid Markdown) → Use result
       │
       └─ Failure / empty / malformed:
              │
              ▼
       Try pdfplumber extraction → Convert to Markdown
              │
              ├─ Success → Use result
              │
              └─ Failure → Mark document as "failed", log error
```

Both parsers sit behind the `DocumentParser` abstraction, allowing additional parsers (DOCX, HTML, TXT) to be added in the future without modifying the ingestion pipeline.

### 7.3 Chunking Strategy

#### Algorithm: Recursive Character Splitting with Overlap

Text is split using a hierarchy of separators, attempting the most semantically meaningful split first:

**Split hierarchy** (in order of preference):
1. `\n## ` / `\n### ` — Section headers (preserves paper structure)
2. `\n\n` — Paragraph boundaries
3. `\n` — Line breaks
4. `. ` — Sentence boundaries
5. ` ` — Word boundaries (last resort)

#### Default Parameters (Configurable)

| Parameter | Default Value | Config Key |
|---|---|---|
| Target chunk size | 800 tokens | `chunking.chunk_size_tokens` |
| Overlap | 150 tokens | `chunking.overlap_tokens` |
| Strategy | `recursive` | `chunking.strategy` |
| Split separators | `["\n## ", "\n### ", "\n\n", "\n", ". "]` | `chunking.split_separators` |

All chunking parameters are configurable via the application configuration file (see [Section 7.7 — Configuration Strategy](#77-configuration-strategy)).

#### Chunk Metadata

Every chunk stored in PGVector carries rich metadata for retrieval and source attribution:

| Field | Purpose |
|---|---|
| `document_id` | Link back to the source paper |
| `chunk_index` | Ordering within the document |
| `page_number` | Enables "Found on page 7 of Paper X" citations |
| `section_heading` | Provides context for retrieved chunks |
| `token_count` | Used for context window budget calculations |
| `embedding_model_id` | Tracks which model generated the vector (for re-embedding) |
| `search_vector` | BM25 tsvector for keyword search |

### 7.4 Hybrid Retrieval (Vector + BM25)

When a user asks a question, retrieval combines **semantic vector search** and **keyword-based BM25 search**:

```
User question
       │
       ▼
Generate embedding of question (Titan Embeddings V2)
       │
       ├──────────────────────────────────┐
       ▼                                  ▼
Vector similarity search            BM25 keyword search
(PGVector cosine distance)          (PostgreSQL tsquery)
       │                                  │
       ▼                                  ▼
Top-k results + scores              Top-k results + scores
       │                                  │
       └──────────┬───────────────────────┘
                  ▼
    Weighted Reciprocal Rank Fusion
    final_score = (vector_weight × vector_rank_score)
                + (bm25_weight × bm25_rank_score)
                  │
                  ▼
         Top-k final results
                  │
                  ▼
    Filter by project scope:
    document_id IN (SELECT document_id
                    FROM project_documents
                    WHERE project_id = ?)
```

#### Retrieval Parameters (Configurable)

| Parameter | Default Value | Config Key |
|---|---|---|
| Top-k results | 5 | `retrieval.top_k` |
| Similarity threshold | 0.7 | `retrieval.similarity_threshold` |
| Hybrid search enabled | `true` | `retrieval.use_hybrid_search` |
| BM25 weight | 0.3 | `retrieval.bm25_weight` |
| Vector weight | 0.7 | `retrieval.vector_weight` |

#### Why Hybrid Search Matters for Research Papers

| Query Type | Vector Search | BM25 | Winner |
|---|---|---|---|
| Semantic ("What methodology was used?") | ✅ Strong | ❌ Weak | Vector |
| Exact terms ("BLEU score", "ResNet-50") | ❌ Weak | ✅ Strong | BM25 |
| Table references ("Results from Table 3") | ❌ Weak | ✅ Strong | BM25 |
| Conceptual ("Compare model accuracy") | ✅ Strong | ✅ Moderate | Both |

### 7.5 Context Assembly & Prompt Engineering

Once chunks are retrieved, the full prompt is assembled for the LLM:

```
┌─────────────────────────────────────────────────────────────┐
│  System Prompt                                               │
│  "You are a research assistant. Answer questions based       │
│   ONLY on the provided document context. If the answer       │
│   cannot be found in the context, say so. Cite your          │
│   sources with document title and page number."              │
├─────────────────────────────────────────────────────────────┤
│  Retrieved Document Chunks                                   │
│  [Chunk 1: Paper A, Page 3 — "The proposed method..."]       │
│  [Chunk 2: Paper B, Page 7 — "Table 3 shows results..."]    │
│  [Chunk 3: Paper A, Page 12 — "In comparison with..."]      │
├─────────────────────────────────────────────────────────────┤
│  Conversation History (sliding window + summary)             │
│  SUMMARY: "Earlier, the user asked about transformer         │
│   architectures and we discussed attention mechanisms..."    │
│  [Full message N-9] ... [Full message N-1]                   │
├─────────────────────────────────────────────────────────────┤
│  Current User Question                                       │
│  "How does Model A compare to Model B on the F1 metric?"    │
└─────────────────────────────────────────────────────────────┘
```

### 7.6 Conversation Memory: Sliding Window with Summary

Chat sessions maintain **individual memory** using a sliding window with summarization strategy. This balances full detail for recent exchanges with compressed awareness of the entire conversation history.

#### How It Works

- The **last N messages** (default: 10) are included in their **full form** — no information loss for recent context.
- All older messages are **summarized** into a running summary stored in DynamoDB (`chat_sessions.running_summary`).
- When messages fall off the window, they are **batch-folded** into the running summary.

#### Sliding Window Lifecycle

```
Messages 1–10:
  Window = [1, 2, 3, ..., 10]
  Summary = "" (empty — all messages fit in window)

Message 15 arrives:
  Window = [6, 7, 8, ..., 15]
  Messages 1–5 have been folded into summary

Message 20 arrives:
  Window = [11, 12, 13, ..., 20]
  Messages 1–10 are in the summary

Batch folding trigger: every 5 messages that fall off the window
```

#### Batch Folding (Cost Optimization)

Instead of summarizing on every single message, the system uses **batch folding**:

- When **5 messages** (configurable) fall off the sliding window, all 5 are folded into the running summary in a single LLM call.
- This reduces summarization LLM calls by 5x compared to per-message summarization.
- **Amazon Nova Micro** is used specifically for summarization regardless of the Q&A model — cheapest option for this low-complexity task.
- The summary is stored in DynamoDB and reused across subsequent requests — computed once per batch, not on every message.

#### Memory Parameters (Configurable)

| Parameter | Default Value | Config Key |
|---|---|---|
| Recent message count (window size) | 10 | `memory.recent_message_count` |
| Batch fold size | 5 | `memory.batch_fold_size` |
| Summarization model | `amazon.nova-micro-v1:0` | `memory.summarization_model` |
| Max summary tokens | 500 | `memory.max_summary_tokens` |

### 7.7 Configuration Strategy

All pipeline parameters are managed through a **tiered configuration system**:

#### Configuration Tiers

| Tier | Mechanism | Examples |
|---|---|---|
| **Environment** | `.env` files / environment variables | Database URLs, AWS credentials, Bedrock model IDs, S3 bucket names |
| **Application** | YAML config file (`config.yaml`) | Chunk size, overlap, top-k, similarity threshold, memory window size, model parameters |
| **Runtime** | API / database-stored (future) | Per-project overrides, feature flags |

#### Application Config File (`config.yaml`)

```yaml
# RAG Pipeline — Chunking
chunking:
  strategy: "recursive"                               # recursive | fixed | semantic
  chunk_size_tokens: 800
  overlap_tokens: 150
  split_separators: ["\n## ", "\n### ", "\n\n", "\n", ". "]

# RAG Pipeline — Retrieval
retrieval:
  top_k: 5
  similarity_threshold: 0.7
  use_hybrid_search: true
  bm25_weight: 0.3
  vector_weight: 0.7

# Conversation Memory
memory:
  recent_message_count: 10
  batch_fold_size: 5
  summarization_model: "amazon.nova-micro-v1:0"
  max_summary_tokens: 500

# Embedding
embedding:
  model_id: "amazon.titan-embed-text-v2:0"
  dimensions: 1024

# LLM (Q&A)
llm:
  model_id: "amazon.nova-micro-v1:0"                  # dev: nova-micro, prod: nova-lite/pro
  max_output_tokens: 2048
  temperature: 0.3

# Document Processing
document_processing:
  supported_formats: ["application/pdf"]
  max_file_size_mb: 50
  primary_parser: "pymupdf4llm"
  fallback_parser: "pdfplumber"
```

All values can be overridden by environment variables (e.g., `CHUNKING__CHUNK_SIZE_TOKENS=1000`) for deployment flexibility without modifying the config file.

### 7.8 Re-Embedding Pipeline

If the embedding model is changed (e.g., Titan V2 → a future model), all existing vectors become incompatible. The system supports this via:

1. Every vector stores its `embedding_model_id` in the `document_chunks` table.
2. A **re-embedding job** can be triggered that:
   - Queries all chunks where `embedding_model_id != current_model_id`
   - Re-generates embeddings using the new model
   - Updates the vectors and `embedding_model_id` in place
3. During re-embedding, the old vectors remain searchable — the system gracefully handles mixed-model states by only searching chunks matching the current model ID.
4. This job runs via the same task queue infrastructure (Celery/SQS).

---

## 8. Streaming & Communication

### Server-Sent Events (SSE)

The chat response delivery uses **SSE (Server-Sent Events)** over standard HTTP. This was chosen over WebSockets because:

- Chat streaming is **unidirectional** (server → client) — SSE is purpose-built for this.
- Simpler to implement, debug, and test than WebSockets.
- Works through standard HTTP proxies and load balancers without special configuration.
- FastAPI has native support via `StreamingResponse`.
- Falls back gracefully through corporate firewalls and proxies.

### Fallback Strategy

1. **Mid-stream disconnection**: Server continues generating and persists the full response. Client fetches the complete message on reconnect.
2. **SSE connection failure**: Client retries with exponential backoff (max 3 attempts).
3. **Complete streaming failure**: Falls back to synchronous `POST` → poll for response via `GET`.

---

## 9. Authentication

Authentication is **not a requirement** for the initial release. However, the architecture is designed to accommodate it in the future:

- All API endpoints are structured with a clear separation that allows middleware-based auth injection.
- User-scoped data models can be extended with a `user_id` foreign key.
- Frontend routing is structured to support protected routes.
- AWS Cognito is the anticipated auth provider (stays within the AWS ecosystem).

---

## 10. Infrastructure & Deployment

### Infrastructure as Code: Terraform

All AWS infrastructure is managed via **Terraform**, chosen for:
- Provider-agnostic — transferable skills, supports non-AWS services if needed.
- Excellent `plan` → `apply` workflow for safe deployments.
- Rich community module ecosystem.
- HCL is more readable than CloudFormation YAML/JSON.

### AWS Services

| Service | Purpose |
|---|---|
| **S3** | File storage for uploaded research papers |
| **DynamoDB** | Chat session and message storage |
| **RDS (PostgreSQL)** | Relational data + PGVector (production) |
| **Bedrock** | LLM (Nova) and embedding (Titan) inference |
| **ECS / Fargate** | Container orchestration for backend services (production) |
| **API Gateway** | API routing and rate limiting (production) |
| **CloudWatch** | Logging and monitoring |

### Deployment Environments

| Environment | Infrastructure | Notes |
|---|---|---|
| **Local / Dev** | Docker Compose (PostgreSQL + pgvector, Redis) | AWS credentials via profiles for Bedrock/S3/DynamoDB access |
| **Production** | Terraform-managed AWS resources | Full AWS stack |

---

## 11. Local Development

### Docker Compose Services

| Service | Image | Purpose |
|---|---|---|
| **PostgreSQL + pgvector** | `pgvector/pgvector:pg16` | Relational DB + vector storage |
| **Redis** | `redis:7-alpine` | Celery message broker + result backend |
| **Celery Worker** | Custom (app image) | Async document processing (parse, chunk, embed) |
| **LocalStack** (optional) | `localstack/localstack` | Mock S3, DynamoDB for offline dev |

### Configuration

- **Environment-based configuration** via `.env` files (`.env.local`, `.env.dev`, `.env.prod`).
- **Application configuration** via `config.yaml` (see [Section 7.7](#77-configuration-strategy)) for pipeline parameters.
- All service URLs, credentials, model IDs, and feature flags are configurable via environment variables.
- Config file values can be overridden by environment variables (e.g., `CHUNKING__CHUNK_SIZE_TOKENS=1000`).
- AWS credentials for Bedrock access are configured via AWS CLI profiles (`~/.aws/credentials`).

---

## 12. Design Principles & Abstractions

### Key Abstractions

The following components are designed behind **abstract interfaces** (Python protocols / abstract base classes) to allow swapping implementations without modifying business logic:

#### `VectorStore` Interface
- **Purpose**: Abstracts the vector database layer and hybrid search.
- **Current implementation**: `PGVectorStore` (PGVector + PostgreSQL BM25)
- **Future implementations**: `PineconeVectorStore`, `OpenSearchVectorStore`
- **Methods**: `store_embeddings()`, `similarity_search()`, `hybrid_search()`, `delete_by_document_id()`
- **Note**: Hybrid search (vector + BM25) is part of the interface. Implementations that don't support BM25 natively can fall back to vector-only search.

#### `EmbeddingProvider` Interface
- **Purpose**: Abstracts the embedding model used to convert text into vectors.
- **Current implementation**: `TitanEmbeddingProvider` (Amazon Titan Embeddings V2 via Bedrock)
- **Future implementations**: `CohereEmbeddingProvider`, `OpenAIEmbeddingProvider`
- **Methods**: `embed_text()`, `embed_batch()`, `get_model_id()`, `get_dimensions()`
- **Critical rule**: The `embedding_model_id` is stored alongside every vector. If the model changes, the re-embedding pipeline (see [Section 7.8](#78-re-embedding-pipeline)) processes all existing documents with the new model.

#### `LLMProvider` Interface
- **Purpose**: Abstracts the LLM used for Q&A chat responses and summarization.
- **Current implementation**: `BedrockNovaProvider` (Nova Micro for dev, Nova Lite/Pro for prod)
- **Future implementations**: `BedrockClaudeProvider`, `OpenAIProvider`
- **Methods**: `generate()`, `generate_stream()`, `get_model_id()`
- **Note**: Summarization (sliding window memory) uses this same interface but may target a different model (Nova Micro) for cost optimization.

#### `DocumentParser` Interface
- **Purpose**: Abstracts document parsing (file → structured Markdown text).
- **Current implementations**: `PyMuPDF4LLMParser` (primary), `PdfPlumberParser` (fallback)
- **Future implementations**: `DocxParser`, `HtmlParser`, `PlainTextParser`
- **Methods**: `parse(file_path) → MarkdownResult`, `get_supported_formats() → list[str]`
- **Fallback behavior**: The ingestion pipeline tries the primary parser first; on failure, it retries with the fallback parser before marking the document as failed.

#### `TaskQueue` Interface
- **Purpose**: Abstracts the async task queue for document processing.
- **Current implementation**: `CeleryTaskQueue` (Celery + Redis for local development)
- **Future implementation**: `SQSTaskQueue` (AWS SQS for production)
- **Methods**: `submit_task(task_name, payload)`, `get_task_status(task_id)`, `cancel_task(task_id)`
- **Note**: The interface decouples the ingestion pipeline from the specific queuing technology. Switching from Celery to SQS requires only swapping the implementation, not changing any calling code.

#### `ConversationMemory` Interface
- **Purpose**: Abstracts conversation history management (sliding window + summarization).
- **Current implementation**: `SlidingWindowMemory` (DynamoDB-backed, Nova Micro for summarization)
- **Methods**: `get_context(chat_id) → (summary, recent_messages)`, `add_message(chat_id, message)`, `trigger_summarization(chat_id)`
- **Note**: Encapsulates the sliding window logic, batch folding, and summary storage. The chat service calls this interface without knowledge of the memory management strategy.

### Design Principles

1. **Separation of Concerns**: Each service/module has a single, well-defined responsibility.
2. **Interface-Driven Design**: Core integrations (vector store, embeddings, LLM, parser, task queue, conversation memory) are behind abstract interfaces.
3. **Configuration over Code**: Environment, model IDs, chunk sizes, retrieval parameters, and feature flags are configurable via YAML config + environment variable overrides — never hardcoded.
4. **Graceful Degradation**: Streaming falls back to polling; PDF parsing falls back to secondary parser; upload failures are retryable; parsing errors don't crash the pipeline.
5. **Idempotency**: Document uploads are deduplicated by SHA-256 file hash. Re-processing and re-embedding are safe to run multiple times.
6. **Project-Level Isolation**: Vector searches are always scoped to the documents linked to the active project. Cross-project data leakage is prevented at the query level.
7. **Cost Optimization**: Summarization uses the cheapest model (Nova Micro); batch folding reduces LLM calls; configurable embedding dimensions allow storage/quality trade-offs.

---

## 13. Confirmed Decisions Summary

All major design decisions have been confirmed:

| # | Decision | Choice |
|---|---|---|
| 1 | Frontend | React + TypeScript + Tailwind CSS |
| 2 | Backend | Python + FastAPI |
| 3 | LLM Provider | AWS Bedrock — Nova Micro (dev), Nova Lite/Pro (prod) |
| 4 | Embedding Model | Amazon Titan Embeddings V2 (1024 dims) |
| 5 | PDF Parser | pymupdf4llm (primary) + pdfplumber (fallback) |
| 6 | Vector Database | PGVector (PostgreSQL extension) |
| 7 | Search Strategy | Hybrid — Vector (PGVector) + BM25 (PostgreSQL full-text) |
| 8 | Relational Database | PostgreSQL (local dev, RDS for production) |
| 9 | Chat Storage | Amazon DynamoDB |
| 10 | File Storage | Amazon S3 |
| 11 | Task Queue | Celery + Redis (local) / SQS (production) |
| 12 | Conversation Memory | Sliding window + batch-folded summarization |
| 13 | Chat Streaming | SSE (Server-Sent Events) with graceful fallback |
| 14 | Chunking | Recursive splitting, 800 tokens, 150 overlap (configurable) |
| 15 | Configuration | YAML config file + env vars + `.env` files |
| 16 | Infrastructure as Code | Terraform |
| 17 | Local Development | Docker Compose |
| 18 | Document Storage | Global with project linking (dedup via SHA-256) |

---

## 14. Future Enhancements

- [ ] Authentication & authorization (AWS Cognito)
- [ ] Multi-user support with role-based access
- [ ] Additional file format support (DOCX, HTML, TXT, Markdown)
- [ ] Citation highlighting in the UI (link to specific pages/sections in PDF viewer)
- [ ] Project sharing between users
- [ ] Usage analytics and cost tracking dashboard
- [ ] Export chat history (PDF, Markdown)
- [ ] Per-project configuration overrides (runtime config tier)
- [ ] Semantic chunking strategy option
- [ ] Advanced retrieval: re-ranking with a cross-encoder model

---

*This document is complete for the current design phase. The implementation plan will be created in a separate document (`implementation-plan.md`).*
