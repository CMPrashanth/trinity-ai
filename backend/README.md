# Trinity Agent Backend

Backend API for Trinity Agent - an autonomous penetration testing platform with LLM-driven planning and graph-based attack path memory.

## 🚀 Quick Start

### Using Docker (Recommended)

1. **Copy environment file**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and change the default passwords!

2. **Start all services**:
   ```bash
   docker-compose up -d
   ```

3. **Check service health**:
   ```bash
   docker-compose ps
   ```

4. **View logs**:
   ```bash
   docker-compose logs -f backend
   ```

5. **Access the API**:
   - API: http://localhost:8080
   - API Docs: http://localhost:8080/api/v1/docs
   - Neo4j Browser: http://localhost:7474
   - ChromaDB HTTP API: http://localhost:8000

### Local Development

1. **Create virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up databases** (use Docker):
   ```bash
   docker-compose up -d postgres neo4j chromadb redis
   ```

4. **Update .env** for local development:
   ```
   POSTGRES_HOST=localhost
   NEO4J_URI=bolt://localhost:7687
   CHROMA_HOST=localhost
   CHROMA_PORT=8000
   REDIS_HOST=localhost
   ```

5. **Run the backend**:
   ```bash
   uvicorn app.main:app --reload --port 8080
   ```

## 📁 Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry
│   ├── config.py            # Configuration
│   ├── database.py          # PostgreSQL connection
│   ├── models/              # SQLAlchemy models
│   │   └── __init__.py      # User, Scan, Vulnerability, Log, Settings
│   ├── schemas/             # Pydantic schemas
│   │   └── __init__.py      # Request/response validation
│   ├── api/                 # API routes
│   │   ├── auth.py          # Authentication (JWT)
│   │   ├── scans.py         # Scan management
│   │   ├── vulnerabilities.py
│   │   ├── graph.py         # Neo4j graph API
│   │   ├── logs.py          # Activity logs
│   │   └── settings.py      # User settings
│   ├── services/            # Business logic
│   │   ├── ai_interface.py  # ⚠️ AI INTEGRATION POINT
│   │   ├── scan_service.py  # Scan orchestration
│   │   ├── graph_service.py # Neo4j operations
│   │   └── vector_service.py # ChromaDB RAG
│   └── utils/
│       └── auth.py          # JWT utilities
├── requirements.txt
├── Dockerfile
├── .env.example
└── README.md
```

## 🤖 AI Integration Guide

### Where to Add Your AI

The AI interface is located in `app/services/ai_interface.py`. It defines an abstract class `AIInterface` with methods you need to implement:

```python
from app.services.ai_interface import AIInterface

class MyTrinityAI(AIInterface):
    def __init__(self, llm_model: str):
        # Initialize your AI/LLM here
        self.llm = your_llm_initialization(llm_model)
    
    async def generate_attack_plan(self, target, scan_profile, config):
        # Use LLM to generate attack plan
        plan = await self.llm.plan(target, scan_profile)
        return plan
    
    async def execute_scan(self, attack_plan, config):
        # Execute the plan with your agent
        result = await your_executor.run(attack_plan)
        return result
    
    # Implement other methods...
```

### Replace the Dummy AI

In `app/services/scan_service.py`, replace `DummyAI` with your implementation:

```python
# Before:
from .ai_interface import DummyAI
self.ai = ai or DummyAI()

# After:
from .ai_interface import MyTrinityAI
self.ai = ai or MyTrinityAI(llm_model)
```

### Key Integration Points

1. **Planning** (`generate_attack_plan`): LLM generates scan strategy
2. **Execution** (`execute_scan`): Agent runs commands with self-healing
3. **Analysis** (`analyze_vulnerability`): RAG-based CVE matching
4. **Graph Updates** (`update_graph`): Store results in Neo4j

## 🗄️ Database Services

### PostgreSQL
- **Purpose**: User accounts, scans, vulnerabilities, logs, settings
- **Access**: localhost:5432
- **Credentials**: See `.env`

### Neo4j
- **Purpose**: Attack graph (hosts, ports, CVEs, relationships)
- **Browser**: http://localhost:7474
- **Bolt**: bolt://localhost:7687

### ChromaDB
- **Purpose**: Vector database for RAG (CVE similarity search)
- **API**: http://localhost:8000
- **Collection**: `cve_knowledge_base`

### Redis
- **Purpose**: Background task queue
- **Access**: localhost:6379

## 🔐 API Authentication

All endpoints (except `/auth/login` and `/auth/register`) require JWT authentication:

1. **Register**: `POST /api/v1/auth/register`
2. **Login**: `POST /api/v1/auth/login` → Returns `access_token`
3. **Use token**: Add header: `Authorization: Bearer <token>`

## 📡 API Endpoints

### Authentication
- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login and get JWT token
- `GET /api/v1/auth/me` - Get current user info

### Scans
- `POST /api/v1/scans` - Create new scan
- `GET /api/v1/scans` - List scans
- `GET /api/v1/scans/{scan_id}` - Get scan details
- `POST /api/v1/scans/{scan_id}/cancel` - Cancel running scan
- `DELETE /api/v1/scans/{scan_id}` - Delete scan

### Vulnerabilities
- `GET /api/v1/vulnerabilities` - List vulnerabilities
- `GET /api/v1/vulnerabilities/stats` - Get statistics
- `GET /api/v1/vulnerabilities/{vuln_id}` - Get details
- `PATCH /api/v1/vulnerabilities/{vuln_id}/status` - Update status

### Graph
- `GET /api/v1/graph` - Get attack graph data
- `GET /api/v1/graph/nodes/{node_id}` - Get node details
- `GET /api/v1/graph/paths` - Find attack paths

### Logs
- `GET /api/v1/logs` - Get activity logs
- `GET /api/v1/logs/components` - List log components

### Settings
- `GET /api/v1/settings` - Get user settings
- `PUT /api/v1/settings` - Update settings
- `POST /api/v1/settings/reset` - Reset to defaults

## 🔧 Development

### Run Tests
```bash
pytest tests/
```

### Database Migrations
```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

### Stop Services
```bash
docker-compose down
```

### Clean Everything
```bash
docker-compose down -v  # Removes volumes too
```

## 🐛 Troubleshooting

### Database Connection Issues
```bash
# Check PostgreSQL
docker-compose exec postgres pg_isready -U trinity

# Check Neo4j
docker-compose exec neo4j cypher-shell -u neo4j -p trinity_neo4j 'RETURN 1'
```

### View Service Logs
```bash
docker-compose logs -f postgres
docker-compose logs -f neo4j
docker-compose logs -f chromadb
docker-compose logs -f backend
```

### Reset Database
```bash
docker-compose down -v postgres
docker-compose up -d postgres
```

## 📝 Environment Variables

See `.env.example` for all available configuration options.

**Important**: Change all default passwords in production!

## 🚨 Security Notes

- Change `SECRET_KEY` in production (use `openssl rand -hex 32`)
- Change all default database passwords
- Use HTTPS in production
- Keep dependencies updated
- Review CORS settings in `config.py`

## 📚 Tech Stack

- **FastAPI**: Modern async Python web framework
- **PostgreSQL**: Relational database
- **Neo4j**: Graph database for attack paths
- **ChromaDB**: Vector database for RAG
- **Redis**: Background task queue
- **SQLAlchemy**: ORM
- **Pydantic**: Data validation
- **JWT**: Authentication

## 🤝 Contributing

1. Make changes in a feature branch
2. Test thoroughly
3. Update documentation
4. Submit PR

## 📄 License

[Your License Here]
