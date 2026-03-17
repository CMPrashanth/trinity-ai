# Trinity-AI — Handoff Context (Demo + Paper Alignment)

## What this project is (in code, not marketing)

This stack is a Docker Compose app with:
- **Frontend**: React/Vite UI
- **Backend**: FastAPI API + SQLAlchemy + scan orchestration
- **Worker**: Celery worker/beat for background tasks
- **Services**: Postgres (state), Redis (queue), Neo4j (graph), ChromaDB (RAG-ish store), Ollama (LLM), n8n (workflows)

## “Is the AI real?” — what happens on a scan

When you create a scan from the UI:
1. **Frontend → Backend**: `POST /api/v1/scans` creates a scan record.
2. Backend `ScanService.run_scan()`:
   - Loads `UserSettings` to build `execution_config` (notably `allowed_cidrs`, `blocked_commands`).
   - Emits n8n webhook `scan_started` (if configured).
3. **Planner (LLM)**: `TrinityAI.generate_attack_plan()` calls **Ollama** in JSON mode to propose scan steps.
   - If Ollama fails, the planner has a deterministic fallback plan (e.g., an `nmap` step), so scans can still run.
4. **Guardrails**: `Guard.validate_scope()` ensures targets are inside `allowed_cidrs` and blocks disallowed commands (simple token checks).
5. **Executor (real tools)**: `Executor` runs real subprocess commands via `asyncio.create_subprocess_shell` inside the backend container.
   - For Nmap, there is dedicated execution/parsing logic.
6. **Results**: vulnerabilities are normalized + persisted; scan logs are stored.
7. **Graph**: if enabled, backend calls `TrinityAI.update_graph()` which writes host/port/vuln nodes to Neo4j.
8. Emits n8n webhook `scan_completed`.

How to verify it’s not “hallucinated execution”:
- Check backend logs for the **exact shell commands** executed.
- Check scan logs in the UI (Logs page) for Executor entries.
- Verify artifacts: Nmap XML parsing results, vulnerability records, Neo4j nodes.

## GPU requirements (Ollama)

- **GPU is NOT required**. Ollama can run purely on CPU.
- A GPU only affects **speed/throughput**.
- If you want GPU in Docker, you typically need NVIDIA Container Toolkit + a compose config that passes through the GPU. (Not required for the demo.)

## Current known blockers / sharp edges

### 1) Docker Desktop engine instability (external)
At times, Docker Desktop has returned `500 Internal Server Error` for basic operations (e.g., `docker ps`).
- This blocks starting the vulnerable lab profile and can interrupt development.

### 2) Graph UI not rendering (was partly contract-related)
- Backend returns edges with keys `{from, to}`.
- react-force-graph expects `{source, target}`.
- Fix applied in the frontend API mapping so `graphAPI.get()` transforms edges into links.

If graph is still empty after that:
- Neo4j may be unreachable (GraphService has a mock fallback).
- Or scans may not be writing expected nodes/ports/vulns (check backend logs for `Observer`/`Graph` entries).

### 3) ChromaDB / RAG stability
- Vector/RAG integration exists but often falls back due to client/config/migration warnings.
- For paper alignment, treat RAG as **partially implemented** unless you confirm Chroma is healthy.

## Paper vs current implementation (practical gap list)

Fully implemented (in practice):
- LLM-based planning call path via Ollama (JSON output)
- Real tool execution via subprocess (not simulated)
- Scope enforcement via `ipaddress` (IPv4 host + IPv4 CIDR)
- Neo4j graph service + API exist

Partially implemented / simplified vs likely paper claims:
- **Guardrails**: mostly substring-based blocked-token checks + scope checks, not a full typed/verified action schema.
- **LangGraph**: used for CVE enrichment workflow, not a full agentic pentest state machine.
- **RAG**: present but reliability depends on ChromaDB health.
- **Attack graph**: persistence exists; UI depends on correct link mapping and Neo4j connectivity.

## Vulnerable demo environment (local-only)

Compose has an opt-in lab profile with intentionally vulnerable apps on an isolated Docker subnet:
- `bkimminich/juice-shop` (HTTP) at fixed IP `10.10.0.11`
- `webgoat/webgoat` at fixed IP `10.10.0.12`

Notes:
- Bindings are to `127.0.0.1` ports for safety.
- Only run scans against targets you own/control.

Suggested demo flow:
1. Start core stack.
2. Start lab profile.
3. Set `SCOPE_SUBNET=10.10.0.0/24` (or add it in user settings).
4. Run scans against `10.10.0.11` and `10.10.0.12`.
5. Verify:
   - Executor logs show real commands
   - Vulnerabilities list populates
   - Graph page shows nodes/links (if Neo4j up)

### Demo seed data (so UI is not empty)

Important: Postgres/Neo4j/Chroma store their data in **Docker volumes**, which are not committed to git.
If you want the UI to show populated scans/vulnerabilities/logs immediately (useful for screenshots), run:

- `docker compose up -d --build`
- Seed relational DB (creates 2 completed scans + vulnerabilities + logs + demo admin user):
   - `docker compose exec backend python -m scripts.seed_demo_db --reset`
- Optional: seed a small Neo4j topology (best-effort):
   - `docker compose exec backend python -m scripts.seed_demo_db --reset --with-graph`

Demo login created by the seeder:
- Email: `demo@trinity.local`
- Password: `demo1234`

## Where to look in code

Key files:
- Planner: `backend/app/agent/planner.py`
- Guard: `backend/app/agent/guard.py`
- Executor: `backend/app/agent/executor.py`
- Orchestrator: `backend/app/agent/trinity_ai.py`
- Scan orchestration: `backend/app/services/scan_service.py`
- Graph service/API: `backend/app/services/graph_service.py`, `backend/app/api/graph.py`
- Frontend graph: `frontend/src/pages/Graph.tsx`, API mapping in `frontend/src/lib/api.ts`

## TODOs (next highest value)

- If Docker engine is stable: bring up lab profile and run a full scan end-to-end.
- If graph still empty: verify Neo4j connection + ensure graph write path is executed on completed scans.
- Decide if paper alignment needs: stronger guardrails schema, stable Chroma/RAG, broader toolchain beyond Nmap.
