# Trinity Agent - Quick Start Guide

## � Prerequisites

- **Python 3.11+** installed
- **Node.js 18+** or Bun installed
- **PowerShell** (Windows) or Bash (Linux/Mac)

---

## 🚀 How to Run the Application

### **Step 1: Start the Backend**

Open a PowerShell terminal:

```powershell
# Navigate to backend directory
cd "g:\final project\project code\backend"

# Start the FastAPI server
python start_backend.py
```

**Expected output:**
```
🚀 Starting Trinity Agent Backend...
📍 API will be available at: http://localhost:8080
📚 API Docs at: http://localhost:8080/api/v1/docs
⚠️  Using SQLite database (trinity.db)
⚠️  Neo4j and ChromaDB will use mock data if the Docker stack is offline
INFO:     Uvicorn running on http://0.0.0.0:8080
```

✅ **Backend is ready when you see:** `Application startup complete`

**Verify backend:**
- API: http://localhost:8080
- Interactive API Docs: http://localhost:8080/api/v1/docs

---

### **Step 2: Start the Frontend**

Open a **NEW** PowerShell terminal (keep backend running):

```powershell
# Navigate to frontend directory
cd "g:\final project\project code\frontend"

# Start the development server
npm run dev
```

**Expected output:**
```
VITE v5.x.x  ready in xxx ms

➜  Local:   http://localhost:5173/
➜  Network: use --host to expose
```

✅ **Frontend is ready!** Open http://localhost:5173 in your browser

---

## 🧪 Testing the Application

### **1. Access the Application**
Open your browser and navigate to: **http://localhost:5173**

### **2. Create an Account**
1. Click **"Sign In"** button in navbar OR navigate to http://localhost:5173/auth
2. Click **"Create Account"** tab
3. Fill in registration form:
   - Name: Your name
   - Email: your@email.com
   - Password: min 8 characters
4. Click **"Create Account"**

### **3. Login**
1. Switch to **"Sign In"** tab
2. Enter your email and password
3. Click **"Sign In"**

**Note:** Currently using mock authentication - real backend integration pending.

### **4. Explore Features**
- **Dashboard**: View metrics, recent scans, vulnerabilities
- **New Scan**: Configure and launch security scans
- **Attack Graph**: Visualize discovered attack paths
- **Findings**: Browse discovered vulnerabilities
- **Activity Logs**: View agent execution logs
- **Settings**: Configure agent behavior

---

## ✅ Features Currently Working

### **Backend (100% Complete)**

#### **Authentication & Security**
- ✅ User registration with email validation
- ✅ Login with JWT token generation
- ✅ Password hashing (bcrypt)
- ✅ Protected API endpoints
- ✅ Token-based authentication

#### **Scan Management**
- ✅ Create new scans with configuration
- ✅ List all scans with pagination
- ✅ Get scan details by ID
- ✅ Cancel running scans
- ✅ Delete scans
- ✅ Scan status tracking (queued, running, completed, failed)

#### **Vulnerability Management**
- ✅ List vulnerabilities with filtering
- ✅ Search vulnerabilities (CVE, title, target)
- ✅ Filter by severity (critical, high, medium, low)
- ✅ Filter by status (open, confirmed, remediated)
- ✅ Vulnerability statistics
- ✅ Update vulnerability status

#### **Graph Database (Mock)**
- ✅ Get attack graph data
- ✅ Node details retrieval
- ✅ Attack path finding
- ✅ Graph export (JSON, Cypher)
- ✅ Graph clearing

#### **Activity Logs**
- ✅ Log creation with component tracking
- ✅ List logs with pagination
- ✅ Filter by level (info, success, warning, error)
- ✅ Filter by component (Planner, Executor, Observer, Guard)
- ✅ Search logs

#### **User Settings**
- ✅ Get user settings
- ✅ Update settings
- ✅ Reset to defaults
- ✅ Agent configuration (LLM model, retries, timeouts)
- ✅ Database settings
- ✅ Notification preferences

#### **Database**
- ✅ SQLite database (auto-created)
- ✅ All tables and relationships
- ✅ Automatic schema creation
- ✅ Data persistence

#### **AI Integration Placeholder**
- ✅ Abstract interface defined
- ✅ Mock implementation (DummyAI)
- ✅ Returns realistic test data
- ✅ Clear integration points

---

### **Frontend (90% Complete - UI Only)**

#### **UI Components (All Built)**
- ✅ Responsive navbar with navigation
- ✅ Dashboard with metrics panels
- ✅ Scan configuration form
- ✅ Vulnerability table with filtering
- ✅ Activity log viewer
- ✅ Attack graph visualization
- ✅ Settings management interface
- ✅ Login/Register forms
- ✅ Beautiful UI with shadcn/ui components

#### **Pages**
- ✅ Dashboard (Index) page
- ✅ Scan creation page
- ✅ Vulnerabilities page
- ✅ Logs page
- ✅ Graph visualization page
- ✅ Settings page
- ✅ Auth page (Login/Register)

---

## ⚠️ Missing Features (To Be Implemented)

### **Critical - Needed for Demo**

#### **1. Frontend-Backend Integration** ⚠️ **HIGH PRIORITY**
**Status:** Not connected - using mock data

**What's missing:**
- API client utility (`src/lib/api.ts`)
- Fetch data from real backend instead of mock data
- Authentication context for token management
- Protected routes (redirect if not logged in)

**Files to update:**
- `src/pages/Auth.tsx` - Connect to real login/register API
- `src/pages/Index.tsx` - Fetch real dashboard data
- `src/pages/Scan.tsx` - Submit scans to backend
- `src/pages/Vulnerabilities.tsx` - Fetch vulnerabilities
- `src/pages/Logs.tsx` - Fetch activity logs
- `src/pages/Settings.tsx` - Save/load settings

**Estimated time:** 4-6 hours

#### **2. Authentication Flow** ⚠️ **HIGH PRIORITY**
**Status:** Backend ready, frontend not connected

**Missing:**
- Store JWT token after login
- Send token with API requests
- Auto-logout on token expiry
- Protected route wrapper

**Estimated time:** 2 hours

#### **3. Real AI Agent Implementation** ⚠️ **YOUR MAIN WORK**
**Status:** Placeholder only (DummyAI)

**What to implement in `backend/app/services/ai_interface.py`:**
```python
class YourAIAgent(AIInterface):
    async def generate_attack_plan():
        # Your LLM-based planning logic
        
    async def execute_scan():
        # Your autonomous execution logic
        
    async def self_heal_script():
        # Your LLM script rewriting logic
        
    async def analyze_vulnerability():
        # Your RAG-based CVE matching
        
    async def update_graph():
        # Your Neo4j graph updates
```

**Estimated time:** Depends on your AI implementation

---

### **Optional - Can Skip for Demo**

#### **Database Services**
- ❌ Real Neo4j integration (using mock graph data)
- ❌ Real ChromaDB integration (using mock CVE data)
- ❌ PostgreSQL (using SQLite)

#### **Advanced Features**
- ❌ Real-time updates (WebSockets)
- ❌ Background task queue (Celery + Redis)
- ❌ PDF report generation
- ❌ Email notifications
- ❌ Scan scheduling
- ❌ Multi-user collaboration
- ❌ Role-based access control

#### **Security Enhancements**
- ❌ Rate limiting
- ❌ Input sanitization
- ❌ Password strength requirements
- ❌ Account lockout

#### **Testing**
- ❌ Unit tests
- ❌ Integration tests
- ❌ E2E tests

---

## 🐛 Troubleshooting

### **Backend won't start**

**Problem:** `ModuleNotFoundError`
```powershell
cd "g:\final project\project code\backend"
pip install -r requirements.txt
```

**Problem:** Port 8080 already in use
- Close the other application using port 8080
- Or change port in `start_backend.py`: `port=8081`

### **Frontend won't start**

**Problem:** Dependencies missing
```powershell
cd "g:\final project\project code\frontend"
npm install
```

**Problem:** Port 5173 already in use
- Frontend will automatically use next available port

### **Can't access the application**

**Check both services are running:**
- Backend: http://localhost:8080 should show `{"message": "Trinity Agent API"}`
- Frontend: http://localhost:5173 should show the dashboard

---

## 📂 Project Structure

```
project code/
├── backend/                    # FastAPI backend
│   ├── app/
│   │   ├── api/               # API route handlers
│   │   ├── models/            # Database models
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # Business logic
│   │   │   └── ai_interface.py  # ⚠️ YOUR AI GOES HERE
│   │   └── utils/             # Helper functions
│   ├── start_backend.py       # Backend entry point
│   ├── requirements.txt       # Python dependencies
│   └── .env                   # Configuration
├── frontend/                   # React frontend
│   ├── src/
│   │   ├── pages/             # Route pages
│   │   ├── components/        # UI components
│   │   └── lib/               # Utilities
│   └── package.json           # Node dependencies
└── docker-compose.yml         # Docker setup (optional)
```

---

## 🎯 Quick Demo Checklist

For your 50% project review:

### ✅ **Ready Now:**
- [x] Backend API fully functional
- [x] Frontend UI built and beautiful
- [x] Authentication endpoints working
- [x] All database models created
- [x] Mock data for all features
- [x] API documentation available

### ⚠️ **To Complete (4-6 hours):**
- [ ] Connect frontend to backend API
- [ ] Implement login/register flow
- [ ] Show real data in dashboard
- [ ] Create/list scans from frontend

### 🤖 **Your Core Work:**
- [ ] Implement actual AI agent
- [ ] Add real scanning logic
- [ ] Integrate LLM for planning
- [ ] Add self-healing mechanisms

---

## 📞 Next Steps

1. **Test the current setup:** Both backend and frontend should run
2. **Familiarize with the codebase:** Explore the API docs
3. **Plan frontend-backend integration:** Decide which pages to connect first
4. **Start your AI implementation:** Begin with the `ai_interface.py` file

---

## 🎓 For Your Review

**What to demonstrate:**
- ✅ Working backend API with full CRUD operations
- ✅ Beautiful, responsive frontend UI
- ✅ Database schema and relationships
- ✅ Clear architecture and code organization
- ⚠️ Frontend-backend connection (if time permits)
- 🤖 AI integration placeholder ready for your implementation

**Estimated completion:** 50-60% (Infrastructure complete, AI pending)

Good luck with your demo! 🚀
