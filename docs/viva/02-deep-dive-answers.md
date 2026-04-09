# Trinity Viva — Deep Dive Answers (Agent vs Chatbot, Tools, CVEs, n8n)

This document answers common viva questions in a “judge-style” precise way.

## 1) Is this a chatbot or an agent?

### What a chatbot is
A chatbot is mainly an **interface pattern**: a user sends text, the system replies with text.

### What an agent is
An agent is defined by **capability**, not UI:
- it can **plan**
- it can **take actions** (call tools, run commands)
- it can **observe results**
- it can **adapt** (retry/self-heal/backtrack)

### What Trinity is in this repo
In your current demo:
- There is **no chat UI required**.
- The “agent” is triggered by a **scan request** (button → API call), not a conversational loop.
- It is still an agent because it:
  - generates a plan
  - runs real tools
  - parses evidence
  - generates findings

So the best viva line is:
> “Trinity is an *action-taking agent pipeline* exposed through an API; it’s not just a text chatbot.”

## 2) What happens after the agent runs (deep detail)

After the scan starts:
1. **DB state** changes: QUEUED → RUNNING → COMPLETED/FAILED.
2. **Logs** accumulate (Planner/Guard/Tool/Observer).
3. **Evidence extraction**: hosts/ports/services are parsed.
4. **RAG enrichment**: observed services are turned into Chroma queries.
5. **Vulnerability records** are created from the CVE candidates.
6. **Graph sync** (optional): Neo4j nodes/edges are updated.
7. **Webhooks** (optional): n8n receives scan lifecycle events.
8. **Frontend** polls and renders the results.

## 3) “Only known tools can be used” — how do we add new tools?

### Why the tool set is restricted
Your project intentionally restricts tools for:
- safety (reduce destructive capability)
- reproducibility (same Docker image everywhere)
- evaluation stability (demo works repeatedly)

The planner prompt literally tells the LLM: “use only these tools installed in the container.”

### How to add a new tool (clean engineering approach)
To add a tool safely, you typically do three changes:
1. **Install it in the Docker image** (apt-get or pip)
2. **Teach the planner about it** (update the planner system prompt and/or deterministic plan templates)
3. **Guard it** (add validation rules / allowlists / safe defaults)

This is the answer to “How do we overcome only-known-tools?”
- We don’t “bypass” the restriction.
- We **extend the allowed tool registry** and guardrails in a controlled way.

### Using “other products” (external tools) without installing them
Two safe patterns:
- **Microservice adapter**: Trinity calls an internal API that runs the external scanner (keeps Trinity container minimal).
- **Plugin interface**: define a tool contract (name, args schema, safety policy), then load tools as plugins.

## 4) How CVE data is accessed (where it comes from)

Trinity uses 2 sources:
1. **NVD live feed** (real CVEs)
   - A Celery beat task periodically calls NVD API.
   - Results are normalized (id/description/metadata) and upserted into Chroma.
2. **Fallback/demo CVE set**
   - If Chroma is unavailable, the vector service can return fallback CVEs.

Key point for viva:
> “The CVE knowledge base is not hardcoded; it’s synced from NVD and embedded in Chroma for semantic retrieval.”

## 5) If a tool runs, how does it run?

Execution method:
- Each tool command is executed as a subprocess inside the backend/worker container.
- stdout/stderr/exit code are captured.
- timeouts prevent hangs.
- circuit breaker prevents infinite failure loops.

## 6) What exactly is matched between tool result and Chroma?

There is **no magical direct matching** like “Nmap output contains CVE-XXXX”.

The matching is semantic:
1. Tool output → parsed “service facts”:
   - service name (http/https/smb/etc)
   - product (e.g., Apache/nginx)
   - version (if detected)
2. The agent creates a query string:
   - `"<service> <product> <version>"`
3. Chroma searches for similar CVE descriptions and returns nearest neighbors.

That’s why it’s called RAG / vector similarity retrieval.

Viva line:
> “We match *observed service fingerprints* to *CVE embeddings* using semantic similarity in ChromaDB.”

## 7) What role does n8n play here, and how is it currently used?

### What n8n is in this architecture
n8n is an automation/orchestration tool. In Trinity it is used as an:
- **intel monitor / automation endpoint**
- **event sink** for scan lifecycle + CVE sync

### What your current code does
Your code sends best-effort webhooks to n8n:
- scan started/completed
- CVE sync completed

It does not block scans if n8n is down.

### What you can claim honestly
- “n8n is integrated as an automation layer for notifications and pipeline hooks.”
- “Core scanning works without it; n8n enhances observability and integration.”

## 8) A strict judge’s “limitations” question — how to answer

Be confident and honest:
- Vulnerability findings in this build are primarily **CVE candidates** from RAG + observed services.
- This is not the same as proving exploitability.
- The design is intentionally evidence-grounded: the agent reasons from observed ports/services before retrieving CVEs.

Strong concluding line:
> “We separate *evidence collection* (tools) from *knowledge enrichment* (CVE RAG) and keep both under guardrails.”
