---
inclusion: always
---

# Coding standards

## General

- Simple over clever. Small functions with one job. No dead code, no commented-out code.
- No placeholder functionality presented as complete; no `TODO` for core features.
- Names say what things are: `match_score`, not `ms`; `ApplicationStatus`, not `Status2`.
- Keep the spec in sync: if behavior changes, update `requirements.md`/`design.md` in the same change.

## Python (backend)

- Python 3.12, fully type-annotated public functions (Ruff `ANN` rules); no `Any` in service or engine signatures.
- Format: `ruff format` (line length 100, Black style); lint: `ruff check` (rules `E,F,I,B,UP,ANN,S,SIM,RUF`); `black --check` must pass.
- Naming: `snake_case` functions/modules, `PascalCase` classes, `UPPER_SNAKE` constants; files end with their role: `job_service.py`, `job_repository.py`.
- SQLAlchemy 2 style only: `Mapped[...]`, `mapped_column`, `select()`; never string-built SQL.
- Pydantic v2: `model_config = ConfigDict(extra="forbid")` on request models; enums are `StrEnum`; constrained fields via `Field(min_length=..., max_length=...)`, `Annotated`.
- Pure engines take and return frozen `@dataclass(frozen=True)` values; use `fractions.Fraction` for score arithmetic.
- Dependencies are injected (FastAPI `Depends`, constructor arguments); no module-level sessions or global mutable state. Time comes from the injected `Clock`.
- Errors: raise subclasses of `AppError` from services (`NotFoundError`, `InvalidStatusTransitionError`, …); never raise `HTTPException` outside `app/api`; never `except Exception: pass`. Catch narrow exceptions at integration boundaries (httpx, file I/O) and translate them.
- Logging: `logger = logging.getLogger(__name__)`; no `print`. Never log secrets, resume text or request bodies.

## TypeScript (frontend)

- `strict: true`, `noUncheckedIndexedAccess: true`; no `any` (use `unknown` + narrowing); no non-null `!` except on `document.getElementById('root')`.
- Format with Prettier (2 spaces, single quotes, trailing commas, width 100); lint with ESLint flat config (`typescript-eslint`, `react-hooks`, `jsx-a11y`).
- Naming: components `PascalCase.tsx`, hooks `useThing.ts`, other modules `camelCase.ts`; types/interfaces `PascalCase`; constants `UPPER_SNAKE`.
- Function components only; props typed with an explicit `interface XProps`; default exports only for pages.
- API types live in `src/types/api.ts` and mirror backend field names exactly (snake_case JSON is kept as-is in types).
- Data access only via hooks in `src/hooks/` built on `src/api/*`; components never call `fetch`.

## Component structure

- A component file holds one exported component plus small private helpers.
- Order inside a component: hooks → derived values → handlers → JSX.
- Every page handles loading (Skeleton), empty (EmptyState with next action) and error (ErrorState with retry).
- Interactive elements are native (`button`, `a`, `input`, `select`) or have full keyboard and ARIA support; every input has a `<label>`.
- Styling with Tailwind utility classes using design tokens; extract repeated patterns into `components/ui/`.

## Error handling

- Backend: one envelope `{"error": {"code", "message", "details"}}`; codes are `UPPER_SNAKE` (`NOT_FOUND`, `VALIDATION_ERROR`, `DUPLICATE_APPLICATION`, `INVALID_STATUS_TRANSITION`, `RESUME_EMPTY`, `INGESTION_SOURCE_UNAVAILABLE`, `PAYLOAD_TOO_LARGE`, `UNKNOWN_DEMO_USER`, `DEMO_USER_NOT_SEEDED`, `DATABASE_UNAVAILABLE`, `INTERNAL_ERROR`).
- Frontend: `api/client.ts` converts non-2xx responses to `ApiError(code, message, status, details)`; UI shows `message` in a toast or inline field errors for 422.
- Recoverable external failures degrade gracefully (fallback, template provider) and are logged at WARNING.

## Type safety

- Backend: request → Pydantic schema → service DTO/dataclass → ORM; responses built from schemas with `model_validate`.
- Frontend: every API function returns a typed `Promise<T>`; no casting JSON to wide types without a type.

## API conventions

- Plural nouns: `/api/jobs`, `/api/applications`; sub-resources for per-user state: `/api/jobs/{id}/bookmark`.
- `GET` read, `POST` create/compute, `PUT` full replace or idempotent set, `PATCH` partial update, `DELETE` remove/unset.
- Status codes: 200 OK, 201 Created, 204 No Content, 401, 404, 409, 413, 422, 502, 503, 500.
- JSON fields `snake_case`; dates `YYYY-MM-DD`; timestamps ISO-8601 UTC with `Z`.
- Lists that can grow are paginated with `page`/`page_size` and return `{items, total, page, page_size, total_pages}`.
