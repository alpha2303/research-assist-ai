# Implementation Standards and Best Practices

> **Last Updated**: 2026-02-21
>
> This document captures the coding standards, architectural patterns, and best practices established during Phases 1-3 of the Research Assist AI project.

---

## Table of Contents

1. [Backend Standards](#backend-standards)
2. [Frontend Standards](#frontend-standards)
3. [Testing Standards](#testing-standards)
4. [Database Standards](#database-standards)
5. [API Design Standards](#api-design-standards)
6. [Development Workflow](#development-workflow)

---

## Backend Standards

### Code Style and Quality

**Python Style Guidelines:**
- Follow **PEP 8** for all Python code
- Follow **Google Python Style Guide** for docstrings and documentation
- Maximum line length: 88 characters (Black formatter default)
- Use `ruff` for linting and formatting (combines black, isort, flake8)
- Use `mypy` for static type checking

**Type Annotations:**
- All function parameters must have type hints
- All function return types must be explicitly annotated
- Use `Optional[T]` for nullable values
- Use `list[T]` and `dict[K, V]` (Python 3.9+ syntax) instead of `List[T]` and `Dict[K, V]`
- Complex types should use type aliases for clarity

**Docstrings:**
- All public modules, classes, and functions must have docstrings
- Use Google-style docstring format:
  ```python
  def function_name(arg1: str, arg2: int) -> bool:
      """Brief description of function.
      
      Longer description if needed with additional details
      about the function's behavior.
      
      Args:
          arg1: Description of arg1
          arg2: Description of arg2
          
      Returns:
          Description of return value
          
      Raises:
          ValueError: Description of when this error occurs
      """
  ```

**Import Organization:**
```python
# Standard library imports
import os
from typing import Optional

# Third-party imports
from fastapi import APIRouter
from sqlalchemy.ext.asyncio import AsyncSession

# Local application imports
from app.models.database import Project
from app.schemas.project import ProjectCreate
```

### Architecture Patterns

**Layered Architecture:**
```
routers/        # API endpoints (thin layer, delegates to services)
  └── services/    # Business logic (orchestration, validation)
      └── repositories/  # Data access (database queries)
          └── models/       # Database models (SQLAlchemy ORM)
```

**Repository Layer:**
- Handle all database operations (CRUD)
- Use async SQLAlchemy with proper session management
- Return ORM models, not schemas
- Include proper type hints for all methods
- Example pattern:
  ```python
  class ProjectRepository:
      def __init__(self, session: AsyncSession):
          self.session = session
          
      async def create(self, project_data: dict[str, Any]) -> Project:
          """Create a new project in the database."""
          project = Project(**project_data)
          self.session.add(project)
          await self.session.commit()
          await self.session.refresh(project)
          return project
  ```

**Service Layer:**
- Orchestrate business logic
- Validate inputs (can use Pydantic or custom validation)
- Convert between ORM models and Pydantic schemas
- Handle errors and exceptions with proper messages
- Use dependency injection for repositories
- Example pattern:
  ```python
  class ProjectService:
      def __init__(self, repository: ProjectRepository):
          self.repository = repository
          
      async def create_project(self, data: ProjectCreate) -> ProjectResponse:
          """Create a new project with validation."""
          project = await self.repository.create(data.model_dump())
          return ProjectResponse.model_validate(project)
  ```

**Router Layer:**
- Define API endpoints with proper HTTP methods
- Use FastAPI dependency injection
- Return appropriate HTTP status codes
- Handle exceptions with HTTPException
- Example pattern:
  ```python
  @router.post("/projects", status_code=201, response_model=ProjectResponse)
  async def create_project(
      data: ProjectCreate,
      session: AsyncSession = Depends(get_session)
  ) -> ProjectResponse:
      """Create a new project."""
      service = ProjectService(ProjectRepository(session))
      return await service.create_project(data)
  ```

### Dependency Injection

Use FastAPI's dependency injection system:
```python
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Database session dependency."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

### Error Handling

- Use custom exception classes for business logic errors
- Convert exceptions to HTTPException in routers
- Provide meaningful error messages
- Include proper HTTP status codes (400 for validation, 404 for not found, 500 for server errors)

---

## Frontend Standards

### Code Style and Quality

**TypeScript Configuration:**
- Strict mode enabled in `tsconfig.json`
- `verbatimModuleSyntax: true` - requires explicit type imports
- Use type-only imports: `import type { Project } from './types'`
- No implicit any, strict null checks
- Use ESLint with React rules

**Component Structure:**
```typescript
/**
 * ComponentName - Brief description
 * 
 * Features:
 * - Feature 1
 * - Feature 2
 */

import { useState, useEffect } from 'react';
import type { Props } from './types';

export default function ComponentName({ prop1, prop2 }: Props) {
  // Implementation
}
```

### Component Patterns

**Smart vs Presentational Components:**
- **Smart (Container) Components**: Handle data fetching, state management, business logic (e.g., `ProjectList`)
- **Presentational Components**: Display data, fire callbacks, no API calls (e.g., `ProjectCard`)

**Component Organization:**
```typescript
// 1. Imports (grouped: react, third-party, local)
import { useState, useEffect, useCallback } from 'react';
import type { Project } from '../types';

// 2. Type definitions
interface Props {
  // ...
}

// 3. Component definition
export default function Component({ props }: Props) {
  // 4. State declarations
  const [state, setState] = useState();
  
  // 5. Memoized callbacks
  const callback = useCallback(() => {}, [deps]);
  
  // 6. Effects
  useEffect(() => {}, [deps]);
  
  // 7. Event handlers
  const handleClick = () => {};
  
  // 8. Render
  return (/* JSX */);
}
```

### State Management

**Context + useReducer Pattern:**
```typescript
// Define discriminated union types for type-safe actions
type Action =
  | { type: 'SET_PROJECTS'; payload: Project[] }
  | { type: 'ADD_PROJECT'; payload: Project }
  | { type: 'DELETE_PROJECT'; payload: string };

// Reducer with exhaustive type checking
function reducer(state: State, action: Action): State {
  switch (action.type) {
    case 'SET_PROJECTS':
      return { ...state, projects: action.payload };
    // ...
  }
}

// Custom hooks for accessing context
export function useProjects() {
  const { state } = useAppContext();
  return state.projects;
}
```

### Modal Implementation

**Use React Portals for proper stacking:**
```typescript
import { createPortal } from 'react-dom';

export default function Modal({ isOpen, onClose }: Props) {
  if (!isOpen) return null;
  
  // Handle ESC key
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [onClose]);
  
  const modalContent = (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50"
         onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div className="bg-white rounded-lg p-6">
        {/* Modal content */}
      </div>
    </div>
  );
  
  return createPortal(modalContent, document.body);
}
```

### API Integration

**Centralized API Service:**
```typescript
// api/client.ts
import axios from 'axios';

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// api/projects.ts
export const projectService = {
  async getProjects(): Promise<Project[]> {
    const response = await apiClient.get<Project[]>('/projects');
    return response.data;
  },
  // ...
};
```

### CSS (Tailwind CSS v4)

**Configuration:**
- Use `@import "tailwindcss";` in CSS files (NOT the old `@tailwind` directives)
- Configure PostCSS with `@tailwindcss/postcss` plugin
- Use utility-first approach consistently

**Common Patterns:**
```tsx
// Layout
<div className="flex h-screen">
  <div className="w-1/3 overflow-y-auto">Left panel</div>
  <div className="flex-1 overflow-y-auto">Right panel</div>
</div>

// Cards
<div className="bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow">

// Buttons
<button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors">

// Forms
<input className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500">
```

---

## Testing Standards

### Backend Testing (pytest)

**Test Structure:**
```python
# tests/conftest.py - shared fixtures
@pytest.fixture
async def async_session():
    """Create test database and session."""
    # Setup
    yield session
    # Teardown

# tests/test_feature.py
async def test_feature_name(async_session):
    """Test description following Given-When-Then."""
    # Given: Setup test data
    project = await create_test_project(async_session)
    
    # When: Execute the test action
    result = await service.do_something(project.id)
    
    # Then: Assert expected outcome
    assert result.status == "success"
```

**Testing Patterns:**
- Use `pytest-asyncio` for async tests
- Create fixtures for common test data
- Use `httpx.AsyncClient` with `ASGITransport` for API testing
- Test database isolation: create/drop tables per test or use transactions with rollback
- Mock external services (AWS, etc.) using `pytest-mock` or `unittest.mock`
- Aim for 80%+ code coverage on critical paths

**API Integration Tests:**
```python
@pytest.fixture
async def async_client(async_session):
    """HTTP client for testing API endpoints."""
    app.dependency_overrides[get_session] = lambda: async_session
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client

async def test_create_project_success(async_client):
    """Test successful project creation."""
    response = await async_client.post(
        "/api/projects",
        json={"title": "Test Project", "description": "Test"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Test Project"
```

### Frontend Testing

- Use React Testing Library for component tests
- Use Vitest for unit tests (Vite-native)
- Test user interactions, not implementation details
- Mock API calls with MSW (Mock Service Worker)

---

## Database Standards

### PostgreSQL with SQLAlchemy

**Model Conventions:**
```python
class ModelName(Base):
    """Brief description of model."""
    __tablename__ = "table_name"
    
    # Primary key - always UUID
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("uuid_generate_v4()"))
    
    # Foreign keys
    parent_id = Column(UUID(as_uuid=True), ForeignKey("parent.id", ondelete="CASCADE"), nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships (use viewonly=True for many-to-many with explicit association tables)
    children = relationship("Child", back_populates="parent", cascade="all, delete-orphan")
    related = relationship("Related", secondary="association_table", viewonly=True)
```

**Indexes:**
- Add indexes for frequently queried columns
- Use HNSW for vector similarity with explicit operator class:
  ```python
  Index(
      "idx_chunks_embedding_hnsw",
      "embedding",
      postgresql_using="hnsw",
      postgresql_ops={"embedding": "vector_cosine_ops"}
  )
  ```
- Create GIN indexes for TSVECTOR columns (BM25 search)

**Migrations (Alembic):**
- One migration per logical change
- Always test migrations: upgrade → downgrade → upgrade
- Include data migrations if needed
- Review auto-generated migrations before committing

### DynamoDB

**Table Design:**
- Use composite keys (partition key + sort key) for query flexibility
- Include GSIs (Global Secondary Indexes) for alternate access patterns
- Use ISO 8601 timestamps for sorting
- Design for single-table patterns when appropriate

---

## API Design Standards

### RESTful Conventions

**HTTP Methods:**
- `GET` - Retrieve resources (safe, idempotent)
- `POST` - Create resources (201 Created)
- `PUT` - Full update (200 OK or 204 No Content)
- `PATCH` - Partial update (200 OK)
- `DELETE` - Remove resources (204 No Content)

**Status Codes:**
- `200 OK` - Successful GET/PUT/PATCH
- `201 Created` - Successful POST (include Location header)
- `204 No Content` - Successful DELETE
- `400 Bad Request` - Validation error
- `404 Not Found` - Resource doesn't exist
- `422 Unprocessable Entity` - Semantic validation error
- `500 Internal Server Error` - Server error

**URL Structure:**
```
/api/projects                    # Collection
/api/projects/{project_id}       # Resource
/api/projects/{project_id}/documents  # Nested collection
```

**Response Format:**
```json
{
  "id": "uuid",
  "title": "string",
  "created_at": "2026-02-21T10:00:00Z",
  "updated_at": "2026-02-21T10:00:00Z"
}
```

**Pagination:**
```json
{
  "items": [...],
  "total": 100,
  "limit": 20,
  "offset": 0
}
```

**Error Format:**
```json
{
  "detail": "Error message",
  "error_code": "PROJECT_NOT_FOUND"  # Optional
}
```

---

## Development Workflow

### Git Workflow

**Branch Naming:**
- `feature/description` - New features
- `fix/description` - Bug fixes
- `refactor/description` - Code refactoring
- `docs/description` - Documentation updates

**Commit Messages:**
```
type(scope): brief description

Longer description if needed with details about
what changed and why.

Fixes #123
```

Types: `feat`, `fix`, `refactor`, `docs`, `test`, `chore`

### Code Review Checklist

- [ ] Code follows style guidelines (PEP 8, TypeScript conventions)
- [ ] All functions have type hints and docstrings
- [ ] Tests are included and passing
- [ ] No console.log or debug statements left in code
- [ ] Error handling is appropriate
- [ ] Performance considerations addressed
- [ ] Security best practices followed
- [ ] Documentation updated if needed

### Development Environment

**Backend:**
```bash
cd backend
uv sync                    # Install dependencies
uv run pytest             # Run tests
uv run mypy app           # Type check
uv run ruff check app     # Lint
uv run alembic upgrade head  # Run migrations
uv run uvicorn app.main:app --reload  # Start dev server
```

**Frontend:**
```bash
cd frontend
npm install               # Install dependencies
npm run dev              # Start dev server
npm run build            # Production build
npm run lint             # Run linter
```

**Docker:**
```bash
docker-compose up         # Start all services
docker-compose up -d      # Start in background
docker-compose logs backend  # View logs
docker-compose down       # Stop all services
```

---

## Performance Considerations

### Backend

- Use async/await for all I/O operations
- Batch database queries when possible
- Use connection pooling (SQLAlchemy default)
- Index frequently queried columns
- Use pagination for list endpoints
- Cache configuration objects (don't reload on every request)

### Frontend

- Use React.memo() for expensive components
- Use useMemo() and useCallback() to prevent unnecessary re-renders
- Lazy load routes and heavy components
- Debounce user input for search/filter
- Use virtual scrolling for long lists
- Optimize bundle size with code splitting

---

## Security Considerations

- Never commit secrets to git (use `.env` files, add to `.gitignore`)
- Validate all user inputs on backend (don't trust frontend validation)
- Use parameterized queries (SQLAlchemy handles this)
- Implement CORS properly (configure allowed origins)
- Use HTTPS in production
- Implement rate limiting for API endpoints
- Sanitize error messages (don't leak implementation details)
- Use prepared statements for raw SQL
- Keep dependencies updated (security patches)

---

## Documentation Standards

### Code Comments

- Use comments to explain **why**, not **what**
- Keep comments up-to-date with code changes
- Remove commented-out code (use git history instead)
- Use docstrings for public APIs
- Add TODO comments with issue numbers: `# TODO(#123): Description`

### README Files

Each major component should have a README:
- Purpose and overview
- Installation instructions
- Usage examples
- Configuration options
- API documentation (or link to it)
- Testing instructions

### API Documentation

- Use FastAPI's automatic OpenAPI docs
- Add descriptions to endpoints
- Document request/response schemas
- Include example requests/responses
- Document error cases

---

## Conclusion

These standards are living documents and should be updated as we learn and improve our practices throughout the project. Consistency is key to maintainability.

For questions or suggestions about these standards, discuss in team meetings or create an issue.
