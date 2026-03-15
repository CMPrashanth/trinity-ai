# ChromaDB + n8n Automation Guide (CVE/RAG)

This guide explains **exactly how CVE data gets into ChromaDB**, how the backend uses it for RAG, and how **n8n fits into the automation loop** in this repo.

## 1) What’s already implemented in this repo

### ChromaDB (Vector/RAG)
- Backend service: `backend/app/services/vector_service.py`
  - Collection: `cve_knowledge_base`
  - Methods:
    - `bulk_add_cves([...])` (upsert many)
    - `search_similar_cves(query)` (RAG lookup)
    - `seed_demo_cves(reset=...)` (curated “famous CVEs” seed)

### NVD feed ingestion (automation)
- Fetch + normalize NVD updates: `backend/app/services/cve_feed_service.py`
- Scheduled job (Celery beat): `backend/app/celery_app.py`
- Task that runs the sync and notifies n8n: `backend/app/tasks/cve_tasks.py`
- Manual trigger endpoint (queues task): `POST /api/v1/settings/cve/sync-now`

### n8n integration points
Backend sends **webhook events** to `N8N_WEBHOOK_URL`:
- `n8n_test` (manual test from UI): `POST /api/v1/settings/integrations/n8n/test`
- `scan_started`, `scan_completed` (scan lifecycle)
- `cve_sync_completed` (CVE sync lifecycle from Celery)


## 2) Data model: what to store in ChromaDB

Chroma documents are stored as:
- `id`: CVE id string (e.g. `CVE-2021-44228`)
- `document`: a plain-English description
- `metadata`: JSON object, recommended keys:
  - `severity`: `critical|high|medium|low|unknown`
  - `year`: integer
  - `tags`: list of strings (optional)
  - `references`: list of URLs (optional)
  - `source`: e.g. `nvd` or `demo`

In this repo, the seed file is:
- `backend/app/data/demo_cves.json`


## 3) “Properly add data” options (choose one)

### Option A — Seed a curated demo set (fastest for your paper/demo)
This loads `backend/app/data/demo_cves.json` into ChromaDB.

API:
- `POST /api/v1/cves/seed-demo` with body `{ "reset": false }`

### Option B — Sync from NVD (real-world-ish)
This fetches CVEs from NVD and upserts them into ChromaDB.

Paths:
- Automatic: Celery beat runs `app.tasks.cve_tasks.sync_cve_feed` every `CVE_SYNC_INTERVAL_HOURS`
- Manual: `POST /api/v1/settings/cve/sync-now` queues the task

Notes:
- NVD rate limits exist. If you hit them, add an `NVD_API_KEY`.

### Option C — Add your own small CVE set
Add CVEs to `backend/app/data/demo_cves.json` and re-run seed with `reset=true`.


## 4) How the AI uses ChromaDB during a scan

In `backend/app/agent/trinity_ai.py`, vulnerability analysis calls:
- `VectorService.search_similar_cves(query=service + version)`

So if Nmap detects something like `OpenSSL 1.0.x`, the query becomes something like:
- `"openssl 1.0"`

Chroma returns the nearest CVEs (by embedding similarity), and the agent can use those as context.

This is why seeding demo CVEs is useful even if your lab targets don’t map to exact real CVEs: it proves the **RAG loop** and **retrieval plumbing** are working.


## 5) Quick verification steps (recommended)

### 5.1 Check Chroma status
- `GET /api/v1/cves/status`

### 5.2 Seed demo CVEs
- `POST /api/v1/cves/seed-demo` body `{ "reset": false }`

### 5.3 Search
- `GET /api/v1/cves/search?q=openssl%20tls&n=5`


## 6) PowerShell examples (Windows)

### 6.1 Login and capture JWT
```powershell
$base = "http://localhost:8001/api/v1"  # change if your backend port differs
$login = Invoke-RestMethod -Method Post -Uri "$base/auth/login" -ContentType "application/json" -Body (@{
  email = "YOUR_EMAIL"; password = "YOUR_PASSWORD"
} | ConvertTo-Json)
$token = $login.access_token
$headers = @{ Authorization = "Bearer $token" }
```

### 6.2 Seed demo CVEs
```powershell
Invoke-RestMethod -Method Post -Uri "$base/cves/seed-demo" -Headers $headers -ContentType "application/json" -Body '{"reset":false}'
```

### 6.3 Search
```powershell
Invoke-RestMethod -Method Get -Uri "$base/cves/search?q=http2%20dos&n=5" -Headers $headers
```

### 6.4 Trigger NVD sync now (queues Celery task)
```powershell
Invoke-RestMethod -Method Post -Uri "$base/settings/cve/sync-now" -Headers $headers
```


## 7) How to build the n8n workflow (matches the architecture diagram)

### Recommended (current repo design)
- **Backend is the ingestion engine** (NVD → normalize → Chroma).
- **n8n is the automation/monitoring layer** (receive events → notify/store/dashboard).

Create an n8n workflow:
1. **Webhook** node
   - Method: `POST`
   - Path: `cve-sync` (so URL is `/webhook/cve-sync`)
2. Optional: **Switch** node on `{{$json.event}}`
   - `cve_sync_completed`
   - `scan_started`
   - `scan_completed`
   - `n8n_test`
3. Then do what you want:
   - Store summary in a DB/Google Sheet
   - Send Slack/Email
   - Update a dashboard
4. End with **Respond to Webhook** (200 OK)

Backend config:
- `N8N_WEBHOOK_URL` should be: `http://n8n:5678/webhook/cve-sync` (default in compose)

### Alternative (n8n drives ingestion)
If you want n8n to *start* the sync:
- Add a **Cron** node → **HTTP Request** node calling:
  - `POST http://backend:8001/api/v1/settings/cve/sync-now`
  - Include `Authorization: Bearer <token>`

Caution: that endpoint is user-authenticated; easiest approach is:
- In n8n, first call `/auth/login` to get a token and store it (or manually paste a token).


## 8) Demo-friendly defaults

- Use curated seed first (`/cves/seed-demo`) so retrieval works immediately.
- Then enable NVD sync if you want “real feed” behavior.


## 9) Safety note

This repo is for scanning **systems you own or have explicit permission to test**. The demo CVEs here are stored as **high-level metadata** (no exploit instructions) to keep the demo safe.
