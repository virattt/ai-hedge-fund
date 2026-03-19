# Milestone 7: Cloud Deployment — Hosting

**Goal:** Containerize frontend + backend together and deploy so the app is accessible from anywhere, not just localhost.

**Risk:** Medium
**Dependencies:** None (can start anytime)

## Key Decisions

- Separate Dockerfiles for backend (FastAPI + uvicorn) and frontend (multi-stage: npm build → nginx)
- Production `docker-compose.prod.yml` with 3 services: backend, frontend (nginx), optional ollama
- Keep SQLite with Docker volume mount (simpler for single-user; PostgreSQL is overkill here)
- nginx serves frontend static files AND reverse-proxies `/api` to backend (single port exposure)
- Make CORS origins configurable via `ALLOWED_ORIGINS` env var (currently hardcoded to localhost)
- Make `DATABASE_URL` configurable (currently hardcoded SQLite path)
- Simple API key auth middleware for production (optional, via `API_AUTH_KEY` env var)

## Tasks

- [ ] Create `docker/Dockerfile.backend` — Python 3.11-slim, Poetry install, uvicorn entrypoint
- [ ] Create `docker/Dockerfile.frontend` — Stage 1: node build, Stage 2: nginx with built assets
- [ ] Create `docker/nginx.conf` — Serves frontend at `/`, proxies `/api` to backend:8000
- [ ] Create `docker/docker-compose.prod.yml` — Services: frontend (port 80/443), backend (internal 8000), ollama (optional)
- [ ] Create `docker/.env.example` — Template with all required env vars documented
- [ ] Make CORS origins configurable in `app/backend/main.py` — read from `ALLOWED_ORIGINS` env var
- [ ] Make `DATABASE_URL` configurable in `app/backend/database/connection.py` — env var with SQLite fallback
- [ ] Verify frontend `VITE_API_URL` works in production build
- [ ] Integration test: `docker compose up` and verify full flow

## Files to Create

| File | Purpose |
|------|---------|
| `docker/Dockerfile.backend` | Backend container (Python 3.11, Poetry, uvicorn) |
| `docker/Dockerfile.frontend` | Frontend container (multi-stage: node build → nginx) |
| `docker/nginx.conf` | nginx config: static files + reverse proxy to backend |
| `docker/docker-compose.prod.yml` | Production compose with frontend, backend, optional ollama |
| `docker/.env.example` | Documented env var template |

## Files to Modify

| File | Change |
|------|--------|
| `app/backend/main.py` | Read CORS origins from `ALLOWED_ORIGINS` env var |
| `app/backend/database/connection.py` | Read `DATABASE_URL` env var with SQLite fallback |
| `app/frontend/src/services/api.ts` | Verify `VITE_API_URL` works in production (likely already does) |

## Verification

1. `docker compose -f docker/docker-compose.prod.yml up --build`
2. Access frontend at `http://localhost` (port 80)
3. Frontend loads, can create flows, run hedge fund analysis
4. Data persists across container restarts (volume mount)
