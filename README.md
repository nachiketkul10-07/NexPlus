# NexPulse

**OBSERVE | DETECT | RESPOND**

NexPulse is a developer observability and incident response workspace. It collects HTTP request telemetry, derives persisted metric samples and structured logs, evaluates alert rules, and keeps incident evidence and investigation history together.

## Architecture

- `frontend/`: React, TypeScript, Vite, Tailwind CSS, and Framer Motion.
- `backend/`: FastAPI, async SQLAlchemy, authentication, telemetry, alert evaluation, incidents, and advisory AI.
- `demo-app/`: controllable FastAPI application that emits real request signals, including slow and failing endpoints.
- `docker-compose.yml`: local development stack, including demo tooling.
- `docker-compose.production.yml`: hardened, HTTPS production stack for a private single-team installation.

Telemetry flows from the demo service through the authenticated ingestion API into the database. Each accepted HTTP event also derives request count, latency, and error metric samples and a structured log. The workspace reads those persisted records from the query API.

## Run locally on Windows

Use three terminals from the repository root. The Python environment must have the packages in `backend/requirements.txt` and `demo-app/requirements.txt` installed.

1. Start the API:

   ```powershell
   cd backend
   .\venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
   ```

   PostgreSQL is used when reachable. For local development the backend falls back to `backend/pulseops_dev.db` (SQLite) if its configured PostgreSQL target is unavailable. Redis-dependent controls have an in-memory fallback.

2. Start the demo application:

   ```powershell
   cd demo-app
   ..\backend\venv\Scripts\python.exe -m uvicorn app:app --host 127.0.0.1 --port 8001
   ```

   To target a non-default API address, set `PULSEOPS_INGEST_URL` to that server's `/api/v1/telemetry/events` endpoint before starting the demo app. The demo service key must match the configured development service; never reuse development credentials in a deployed environment.

3. Start the frontend:

   ```powershell
   cd frontend
   npm install
   npm run dev
   ```

   Vite serves the app at `http://localhost:5173` and proxies `/api` to `http://127.0.0.1:8000`. Set `NEXPULSE_BACKEND_TARGET` if the API runs on a different port.

For the local administrator view, sign in with the development-only account `admin@pulseops.io` / `AdminPass123!` and open Overview. The Admin Operational Control Center includes **Run end-to-end demo**, which sends healthy, slow, and failing traffic through the monitored Demo Application and evaluates alert rules. Then review Services, Metrics, Logs, Alerts, Incidents, AI Assistance, Reports, and Settings from the workspace menu. These seeded credentials are for local development only; do not deploy them.

The Demo Application also exposes `POST http://localhost:8001/api/demo/run`. Its individual endpoints are `GET /api/health`, `/api/users`, `/api/orders`, `/api/slow`, and `/api/error`. Set `VITE_DEMO_APP_URL` when the demo service runs at a different address.

## Connect a GitHub repository

From **Services → Connect GitHub repository**, paste a GitHub HTTPS repository URL. NexPulse looks up repository metadata and the names of common root manifest files, then creates a monitored service linked to that repository. Private repositories require an optional fine-grained GitHub token restricted to that repository with **Contents: read-only** access; NexPulse uses it only for the lookup and does not save it. Rotate/revoke that token in GitHub if it was pasted into an untrusted environment.

Repository fetching does not clone, build, run, or deploy source code. The service continues to receive telemetry only after its deployed runtime is instrumented to send signals to NexPulse. After connection, copy the one-time ingest key and keep it in the runtime’s secret manager or GitHub Actions secrets—never commit it. The connection dialog provides a sample request to validate ingestion. Public-repository preview uses GitHub’s unauthenticated API allowance, so use a narrowly scoped token if you encounter GitHub rate limits.

## Configuration

Copy `.env.example` to `.env` and set deployment-specific database, Redis, signing, CORS, and AI provider values. The Groq API key is consumed by the backend only. Without a provider key, incident analysis uses the deterministic evidence fallback. Do not commit `.env` or expose ingestion credentials in browser code.

## Docker

```powershell
docker compose up --build
```

The Compose configuration supplies PostgreSQL and Redis for containerized use. Check `docker-compose.yml` and `.env.example` for service ports and required deployment settings.

## Production deployment readiness

**Do not use the development Compose file for a public deployment.** The production Compose file publishes only Caddy on ports 80/443; the API, PostgreSQL, and Redis stay on private Docker networks. It disables public registration, demo controls, API docs, and Prometheus, requires PostgreSQL and authenticated Redis, enables Secure/HttpOnly/SameSite cookies and host/origin checks, applies container privilege/resource limits, and runs migrations before the API starts.

This version is suitable only for a private, single-team deployment. It does not scope services, telemetry, alerts, or incidents to an organization, so it is **not ready for public multi-tenant SaaS or storing unrelated customers’ data**. Before that use, add organization ownership and authorization to every query and mutation, then add invitation/email verification, password reset/change, MFA, and security review. Do not expose it to customer accounts until those controls are implemented and independently reviewed.

### Before starting production

1. Provision a host with Docker Compose v2, a DNS name pointing to it, and inbound TCP 80/443. Docker must be installed; the earlier local shell reported that the `docker` command was unavailable.
2. Copy `.env.production.example` to `.env.production` and restrict that file to the deployment operator. Generate independent random values for `SECRET_KEY`, PostgreSQL admin password, restricted application database password, and Redis password using a password manager or cryptographic generator. Put only the password URL-encoded form in the database/Redis URLs. Keep this file out of Git and backups that are not encrypted. For managed hosting, use its secret manager instead of a checked-in env file. The API connects with a separate database role that is not the PostgreSQL administrator.
3. Set `NEXPULSE_DOMAIN`, and make `ALLOWED_ORIGINS=https://<same-domain>` and `TRUSTED_HOSTS=<same-domain>`. Ensure the database and Redis URLs use the same credentials set for their containers. Set `AI_API_KEY` only if enabling live AI analysis; the key is server-side. AI is advisory and sends selected incident context to the configured provider.
4. Review and populate the initial administrator only after the containers are up and migrations have completed. Create the administrator interactively from the API container; the password is not passed on the command line:

   ```powershell
   docker compose --env-file .env.production -f docker-compose.production.yml up --build -d
   docker compose --env-file .env.production -f docker-compose.production.yml exec backend python -m app.db.create_initial_admin
   ```

   Add any additional operators with `python -m app.db.create_operator`. Keep public registration disabled.
5. Check `https://<your-domain>/health`, confirm HTTPS works, and verify backup/restore procedures for PostgreSQL and Redis before accepting operational data. Restrict host access, patch the OS and images regularly, monitor disk use and failed logins, and rotate secrets if exposed. Back up `.env.production` only in an encrypted secret store.

The production compose file is a single-host baseline, not a substitute for managed database backups, host hardening, vulnerability scanning, incident response, or an external penetration test. Security controls reduce risk; no configuration can guarantee protection from every attack. The production stack has not been container-run in this environment because Docker is not installed here.

## Verification

```powershell
cd frontend
npm test
npm run build

cd ..\backend
.\venv\Scripts\python.exe -m pytest tests -q

cd ..\demo-app
..\backend\venv\Scripts\python.exe -m pytest test_app.py -q
```

## Current scope

- AI analysis is advisory. Hypotheses need operator review; AI does not execute remediation.
- Live Groq analysis requires a server-side API key. The evidence-based fallback remains available without one.
- The UI reports data returned by the configured backend. Availability and incident metrics depend on telemetry actually received and persisted.
