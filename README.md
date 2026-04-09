# Trinity Agent Framework for Stateful Penetration Testing

Trinity is an AI-assisted penetration testing framework that combines automated scanning, vulnerability correlation, graph-based attack visualization, and retrieval-augmented CVE context.

## Highlights

- AI-assisted scan planning and execution workflow
- Stateful attack graph visualization (Neo4j)
- CVE knowledge and semantic lookup (ChromaDB)
- Scan orchestration with background workers (Celery + Redis)
- React frontend dashboard for scans, vulnerabilities, logs, and graph exploration

## Repository Structure

- `backend/` FastAPI backend, services, tasks, and API routes
- `frontend/` Vite + React + TypeScript UI
- `docs/` viva notes and supporting documentation
- `docker-compose.yml` multi-service local stack

## Core Tech Stack

- Backend: FastAPI, SQLAlchemy, Celery, Redis
- Frontend: React, TypeScript, Vite, Tailwind
- Databases: SQLite/PostgreSQL, Neo4j, ChromaDB
- AI/RAG: LangChain/LangGraph, Ollama/Groq adapters

## Prerequisites

- Docker Desktop (recommended)
- Python 3.10+
- Node.js 18+

## Quick Start

1. Clone and open the project:

```bash
git clone <your-repo-url>
cd trinity-ai
```

2. Create backend environment file (if needed):

```bash
cp backend/.env.example backend/.env
```

3. Start infrastructure services:

```bash
docker compose up -d
```

4. Run backend:

```bash
cd backend
pip install -r requirements.txt
python start_backend.py
```

5. Run frontend:

```bash
cd ../frontend
npm install
npm run dev
```

Frontend default URL: `http://localhost:5173`

## Database Components

- Neo4j (graph): `bolt://localhost:7687`, browser: `http://localhost:7474`
- ChromaDB (vector): `http://localhost:8000`
- SQL store: SQLite by default (`backend/trinity.db`) unless configured for PostgreSQL

## Inspecting Stored Data

Use the included helper script:

```bash
python backend/scripts/inspect_databases.py
```

This prints:

- Neo4j node and relationship counts
- Recent scan IDs in graph data
- Chroma collections and document counts

## Notes

- This framework is intended for authorized lab environments and approved targets only.
- See `QUICK_START.md` and `TESTING_GUIDE.md` for additional details.

## License

This project is licensed under the MIT License. See the `LICENSE` file.
