## Initial Requirements
We will be building an application that will be capable of ingesting and aggregating research papers provided by our team. The team should be able to then converse with the system to ask questions about the papers and receive answers only based on the content of the papers.

### Design idea:

#### High-level Logic Design
- Application will have a web-based interface for users to interact with the system.
- User will start with creating a "project". A project will be a logical abstraction that will contain all the research papers related to a specific research project.
- A project can have multiple chat sessions, each "chat" representing a conversation between the user and the system related to the research project. Chats within a project can have shared context to help answer questions more accurately, but individual memory so that there is no interference in between different chats.
  - **Shared context**: All chats within a project have access to the same document corpus (vector embeddings scoped to the project's linked documents).
  - **Individual memory**: Each chat session maintains its own conversation history stored independently.
- Research papers can be uploaded at project level, and should be available to all chats within the project. Appropriate user interface components should be designed to facilitate this process.
- **Document storage is global**: Research papers and their processed chunks/embeddings are stored at a global level. Adding a document to a project creates a linking reference (project_id ↔ document_id) rather than duplicating the document data. This minimizes redundant chunking and embedding when the same paper is used across multiple projects. Deduplication is achieved via SHA-256 file hashing on upload.

#### UI Design
- **Frontend Technology**: React + TypeScript + Tailwind CSS (Single Page Application)
- The UI will be designed to be intuitive and user-friendly.
- The main page will consist of two vertical sections:
- Left section: Project list
   - Size: 1/3rd of the screen width
   - This section will contain a list view component. First item of the list will be a button to create a new project. Rest of the items will be the projects created by the user.
   - Projects here can be represented as a card item with the project title on the left and a dropdown expand button on the right.
   - Clicking on the dropdown expand button will expand the list of chats in the project with the similar list view behavior with a slight indentation.
   - First button in the chat list will be a button to create a new chat. Rest of the items will be the chats created by the user. Clicking on a chat will open up the chat in the chat interface section on the right side.
   - Document upload controls are accessible at the project level (e.g., an upload button/area within the expanded project view or a project settings panel).
- Right section: Chat interface
  - Size: 2/3rd of the screen width
  - This section will contain a chat interface with a chat history and a text input field to send messages.
  - Chat history will be displayed in a scrollable list with each message having a sender and a timestamp. Messages will be sorted in descending order by timestamp. User messages should be aligned to the right side of the section, while agent messages should be left aligned, like in standard chat interfaces.
  - Chat responses are delivered via **Server-Sent Events (SSE)** for real-time token streaming. Tokens are rendered incrementally as they arrive from the server.
  - AI responses should include source attribution (document title, page number) so users can verify where the information came from.
- The UI will be designed to be responsive and work well on both desktop and mobile devices.
  - On mobile, the project list collapses into a drawer/hamburger menu.
- All components will have a rounded border and a shadow effect to improve the visual appeal. Sufficient padding will be added to ensure that the components are not too close to the edges of the screen. Follow standard UX guidelines.

#### Backend Design
- Cloud Backend: AWS
- Backend Architecture: Microservices (may start as a modular monolith with clear service boundaries, with a path to split into independent services later)
- Programming Language: **Python** — Best ecosystem for AI/ML workloads (LangChain, Boto3, PDF parsing). Performance concerns are mitigated since the system is I/O-bound (LLM API calls, vector search) rather than CPU-bound.
- Python Project Manager: **uv** (by Astral) — Rust-powered, 10–100x faster than pip. Manages dependencies, virtual environments, and Python versions in a single tool. Generates `uv.lock` for reproducible builds across dev and production. PEP 621 `pyproject.toml` native. Dockerfiles use `uv sync --frozen` for fast, cache-friendly container builds.
- Framework: **FastAPI** — Async-native, automatic OpenAPI/Swagger documentation, Pydantic-based validation, native SSE support via `StreamingResponse`.
- LLM Provider: **AWS Bedrock**
  - Development: Amazon Nova Micro (cost-optimized for iteration and testing)
  - Production: Amazon Nova Lite / Nova Pro (higher quality for end-user responses)
  - Abstracted behind an `LLMProvider` interface to allow model/provider swaps without code changes.
- Embedding Model: **Amazon Titan Embeddings V2** (via Bedrock)
  - 1024 dimensions (configurable: 256 / 512 / 1024)
  - 8K token input limit
  - ~$0.02 per 1M input tokens (most cost-effective on Bedrock)
  - Abstracted behind an `EmbeddingProvider` interface. The `embedding_model_id` is stored alongside every vector in the database to support future model migration and re-embedding.
- Chat Response Delivery: **SSE (Server-Sent Events)** for real-time token streaming.
  - Chosen over WebSockets because chat streaming is unidirectional (server → client).
  - Graceful fallback: if SSE fails, the system falls back to synchronous request/response with polling. Mid-stream disconnections are handled by persisting the full response server-side regardless of client connection state.
- Database:
  - Chat conversation: **Amazon DynamoDB** — Partition key (`chat_id`) + sort key (`timestamp`) model is a perfect fit for append-heavy, sequential-read chat patterns. Fully managed, serverless, auto-scaling.
  - File Storage: **S3 Bucket** for storing original uploaded research papers (source of truth).
  - Vector Storage: **PGVector** (PostgreSQL extension) — Runs inside the existing PostgreSQL instance, zero additional cost or infrastructure. Sufficient performance for team-scale usage. **Abstracted behind a `VectorStore` interface** to allow future migration to Pinecone, OpenSearch, or other dedicated vector databases without modifying business logic. Current implementation: `PGVectorStore`. The code design must ensure this abstraction is in place from day one.
  - Relational Database: **PostgreSQL** — Superior JSON support, advanced querying, pgvector extension. Running locally for development, Amazon RDS for production.
- Document Parsing:
  - Primary parser: **pymupdf4llm** — Converts PDFs to Markdown format, preserving table structure as Markdown tables. Critical for research papers with result comparison tables.
  - Fallback parser: **pdfplumber** — Activated when pymupdf4llm produces empty or malformed output. Has a dedicated `.extract_tables()` method for robust table extraction.
  - Both are lightweight, open-source, and pet-project-friendly — no enterprise dependencies.
  - Abstracted behind a `DocumentParser` interface to support adding new file formats (DOCX, HTML, TXT) without changing the ingestion pipeline. Initial support: PDF only.
- Search Strategy: **Hybrid — Vector (PGVector) + BM25 (PostgreSQL full-text search)** from day one.
  - Vector search handles semantic matching; BM25 handles exact term matching (critical for research paper terminology, acronyms, table references).
  - BM25 is built into PostgreSQL (`tsvector` + GIN index) — zero additional cost or infrastructure.
  - Results are combined via configurable weighted Reciprocal Rank Fusion (`vector_weight: 0.7`, `bm25_weight: 0.3`).
- Async Document Processing:
  - Document ingestion (parse → chunk → embed → store) runs asynchronously via a task queue so the user is not blocked.
  - Local development: **Celery + Redis** — Celery is the task queue framework; Redis acts as both the message broker and result backend.
  - Production: **AWS SQS** — Fully managed, serverless, auto-scaling.
  - Abstracted behind a `TaskQueue` interface so switching from Celery to SQS requires no business logic changes.
- Conversation Memory: **Sliding window with batch-folded summarization**.
  - Last N messages (default: 10) are included in full — no information loss for recent context.
  - Older messages are batch-folded into a running summary stored in DynamoDB using a dedicated LLM call (Amazon Nova Micro for cost optimization).
  - Batch folding: every 5 messages that fall off the window are summarized in a single LLM call (reduces summarization costs by ~5x compared to per-message summarization).
  - The LLM receives: system prompt + retrieved document chunks + running summary + recent full messages + current question.

#### Authentication
- Authentication is not a requirement for this project at the moment. But keep room in the design to accommodate future authentication needs.
  - All API endpoints are structured to allow middleware-based auth injection.
  - Data models can be extended with a `user_id` foreign key.
  - Frontend routing supports protected routes.
  - AWS Cognito is the anticipated future auth provider.

#### Infrastructure & Deployment
- Infrastructure as Code: **Terraform** — Provider-agnostic, transferable skills, excellent `plan` → `apply` workflow, rich community module ecosystem.
- Local Development: **Docker Compose** for local services (PostgreSQL with pgvector, Redis for task queue). AWS credentials configured via CLI profiles for Bedrock/S3/DynamoDB access.
- Configuration Strategy (tiered):
  - **Environment tier**: `.env` files (`.env.local`, `.env.dev`, `.env.prod`) for service URLs, AWS credentials, Bedrock model IDs, S3 bucket names.
  - **Application tier**: YAML config file (`config.yaml`) for pipeline parameters — chunk size, overlap, top-k retrieval count, similarity threshold, memory window size, BM25/vector weights, model parameters. All values are overridable via environment variables (e.g., `CHUNKING__CHUNK_SIZE_TOKENS=1000`).
  - **Runtime tier** (future): API / database-stored per-project overrides and feature flags.

#### RAG Pipeline
- Document ingestion flow: Upload → SHA-256 dedup check → S3 storage → PDF parse (pymupdf4llm, fallback pdfplumber) → Recursive chunk splitting (800 tokens default, 150 overlap, configurable) → Embedding generation (Titan V2) → Store chunks + vectors + BM25 tsvector in PGVector → Link document to project.
- Retrieval flow: User question → Generate question embedding → Hybrid search (vector similarity + BM25 keyword) scoped to project's linked documents → Weighted rank fusion → Top-k chunks → Assemble prompt (system prompt + chunks + conversation memory + question) → Stream response via SSE.
- Re-embedding pipeline: If the embedding model changes, a bulk re-embedding job processes all chunks where `embedding_model_id` differs from the current model. Old vectors remain searchable during migration. Runs via the same task queue infrastructure.

#### Key Design Principles
1. **Interface-Driven Design**: Core integrations (vector store, embeddings, LLM, document parser, task queue, conversation memory) are behind abstract interfaces (Python protocols / abstract base classes) to allow swapping implementations.
2. **Global Document Storage with Project Linking**: Documents are stored and processed once globally; projects reference them via a many-to-many linking table to avoid duplicate chunking/embedding.
3. **Configuration over Code**: Environment, model IDs, chunk sizes, and feature flags are configurable — not hardcoded.
4. **Graceful Degradation**: Streaming falls back to polling; PDF parsing falls back to secondary parser; upload failures are retryable; parsing errors don't crash the pipeline.
5. **Idempotency**: Document uploads are deduplicated by SHA-256 file hash. Re-processing is safe to run multiple times.
6. **Source Attribution**: Every vector chunk stores metadata (document ID, page number, section heading, embedding model ID) to enable citation in chat responses.
7. **Cost Optimization**: Summarization uses the cheapest model (Nova Micro); batch folding reduces LLM calls; configurable embedding dimensions allow storage/quality trade-offs.

---

> **Reference**: See `design-doc.md` for the full design document with architecture diagrams, data models, API specifications, and detailed rationale for all design decisions.