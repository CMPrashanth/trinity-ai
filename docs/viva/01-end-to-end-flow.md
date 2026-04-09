# Trinity Viva — End-to-End Flow (Request → Agent → Tools → Findings)

This document explains what *actually happens* in this repo when you start a scan from the UI.

> Scope note (for viva): Trinity is designed for **authorized lab environments**. The agent enforces scope restrictions and blocks unsafe command patterns.

## 0) Components involved (what runs where)

- **Frontend (React)**: user clicks “Start Scan”, then polls for scan status + logs + vulnerabilities.
- **Backend API (FastAPI)**: authenticates the user (JWT), creates scan records, exposes endpoints for scans/logs/vulns/graph.
- **Worker (Celery)**: runs the scan in the background (so the API request returns immediately).
- **Agent runtime (`TrinityAI`)**:
  - **Planner**: generates a multi-step plan of tool commands.
  - **Guard**: checks scope + safety constraints.
  - **Executor**: runs commands, captures output, applies timeouts + circuit-breaker.
  - **Observer**: parses results into structured facts and persists them.
- **Data stores**:
  - Postgres (scan records, logs, vulnerabilities)
  - Neo4j (optional attack graph)
  - ChromaDB (vector DB for CVE retrieval / RAG)
- **n8n**: webhook receiver for scan/CVE events (optional monitoring/automation).

## 1) User request: “Start Scan” from the UI

### 1.1 Frontend → Backend request

The frontend calls the backend `POST /api/v1/scans` with JSON like:

```json
{
  "target": "10.10.0.0/24",
  "scan_profile": "quick",
  "advancedOptions": {
    "enableRAG": true,
    "circuitBreaker": true,
    "graphMemory": true,
    "autoHeal": true
  }
}
```

### 1.2 Backend response

The backend immediately returns a created scan (status is queued), including a `scan_id` the UI uses to fetch details:

```json
{
  "scan_id": "scan-<random>",
  "status": "QUEUED",
  "target": "10.10.0.0/24",
  "profile": "QUICK"
}
```

## 2) Background execution: why the UI returns instantly

In the scan API route, the backend queues a Celery task (`run_scan.delay(scan.id)`).

Effect:
- The HTTP request finishes fast.
- The long-running scan happens in a worker container.

## 3) Agent start: ScanService orchestrates the run

The Celery worker calls `ScanService.start_scan(scan_db_id)`.

Inside this method:
1. It loads user settings (timeouts, retries, allowed CIDRs, blocked tokens).
2. It sets scan status to `RUNNING` and writes initial logs.
3. It calls the agent:
   - `generate_attack_plan(target, scan_profile, config)`
   - `execute_scan(attack_plan, config)`
4. It persists:
   - logs
   - vulnerabilities
   - optional graph updates
5. It marks scan `COMPLETED` or `FAILED`.

## 4) Planner: how the plan is generated (LLM vs deterministic)

Planner logic produces an `AttackPlan` with `steps[]` where each step is a command string + description.

Important project detail for viva:
- For reliability, this project often uses **deterministic fallback plans** for `quick/full/stealth` profiles.
- Ollama/LLM planning is available, but can be bypassed depending on config (demo-stability choice).

## 5) Guard: what is validated before any tool runs

There are two main checks:

### 5.1 Scope validation
- Target must be in the allowed subnet(s).
- Sources:
  - global default via environment `SCOPE_SUBNET`
  - or per-user setting `allowed_subnet`

### 5.2 Safety validation
- The command string is checked for blocked tokens.
- Examples of what a guard can block:
  - destructive patterns
  - disallowed flags
  - any user-configured blocked command tokens

Result:
- If a step is blocked, it does **not execute**.

## 6) Executor: how commands actually run

For each approved step, the agent runs the command using an async subprocess shell.

Key runtime protections:
- **Timeouts**: prevents hangs.
- **Circuit breaker**: stops repeated failures per tool type.
- **Normalization**: fixes common plan mistakes (e.g., removes invalid Nmap flags, avoids `-sS` + `-sT` together).

Outputs captured per step:
- stdout
- stderr
- exit code
- duration

These are appended into the scan’s log stream.

## 7) Observer: parsing tool output into facts

### 7.1 Parsing Nmap output
If a step contains Nmap output, the agent parses:
- discovered hosts
- open ports
- service identification (service name + product + version where present)

These facts become the “evidence layer” Trinity uses.

### 7.2 CVE retrieval (RAG)
The agent builds a query from observed services, typically:

```
<service> <product> <version>
```

Then calls Chroma:
- `VectorService.search_similar_cves(query, n_results=3)`

Chroma returns candidate CVEs with:
- `cve_id`
- `description`
- `similarity_score`
- `metadata` (severity/cvss/references if present)

The agent converts these candidates into `VulnerabilityFinding` objects.

## 8) Persisting results (DB + graph)

### 8.1 Vulnerabilities in Postgres
The backend converts `VulnerabilityFinding` into DB `Vulnerability` rows.

### 8.2 Graph update in Neo4j (optional)
If enabled, the agent writes nodes/edges like:
- Host nodes
- Port/service nodes
- CVE nodes
- relationships (host exposes port; port associated with CVE)

If Neo4j is unreachable, the graph feature can degrade gracefully.

## 9) n8n events: what is emitted

The backend sends best-effort webhooks to n8n:
- `scan_started`
- `scan_completed`
- `cve_sync_completed`

These are not required for core scanning; they are for monitoring/automation.

## 10) UI updates: how the frontend sees progress

The UI typically polls:
- scan status (`GET /scans` and `GET /scans/{scan_id}`)
- logs (`GET /logs`, optionally filtered by scan)
- vulnerabilities (`GET /vulnerabilities`, optionally filtered by scan)
- graph data (`GET /graph`) when you open the Graph page

The “proof” during demo:
- Logs show tool execution entries.
- Vulnerabilities populate after service identification + RAG lookup.
- Graph updates when enabled and Neo4j is available.
