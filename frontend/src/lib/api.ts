import axios, { AxiosError } from "axios";

// Get API URL from environment variable
const envApiUrl = import.meta.env.VITE_API_URL;
const API_BASE_URL = envApiUrl || "http://localhost:8080/api/v1";

// Create axios instance
export const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor to add JWT token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem("token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    // Handle 401 Unauthorized - token expired or invalid
    if (error.response?.status === 401) {
      localStorage.removeItem("token");
      localStorage.removeItem("user");
      window.location.href = "/auth";
    }
    return Promise.reject(error);
  }
);

// Types
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface User {
  id: number;
  email: string;
  name: string;
  is_active: boolean;
  is_admin: boolean;
  created_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  name: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface Scan {
  id: number;
  scan_id: string;
  target: string;
  profile: string;
  status: string;
  start_time: string;
  end_time?: string;
  findings: {
    critical: number;
    high: number;
    medium: number;
    low: number;
    info: number;
  };
  created_at: string;
}

export interface ScanCreate {
  target: string;
  scan_profile: "quick" | "full" | "stealth" | "web";
  advancedOptions?: {
    enableRAG: boolean;
    circuitBreaker: boolean;
    graphMemory: boolean;
    autoHeal: boolean;
  };
}

export interface Vulnerability {
  id: number;
  vuln_id: string;
  cve: string;
  title: string;
  description: string | null;
  severity: string;
  cvss_score: string | null;
  target: string;
  port: string;
  service: string | null;
  status: string;
  exploit_available: boolean;
  references: string[];
  remediation: string | null;
  discovered_at: string;
}

export interface VulnerabilitySeverityBreakdown {
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
}

export interface VulnerabilityStats {
  total: number;
  by_severity: VulnerabilitySeverityBreakdown;
}

export interface Log {
  id: number;
  timestamp: string;
  level: string;
  component: string;
  message: string;
  details?: string;
}

export interface Settings {
  llm_model: string;
  max_retries: number;
  execution_timeout: number;
  enable_self_healing: boolean;
  circuit_breaker_enabled: boolean;
  neo4j_uri: string;
  chroma_db_path: string;
  graph_hygiene_enabled: boolean;
  allowed_subnet: string;
  blocked_commands: string;
  email_alerts: boolean;
  slack_integration: boolean;
  alert_on_critical: boolean;
  alert_on_circuit_break: boolean;
}

export interface GraphNode {
  id: string;
  label: string;
  type: string;
  properties?: any;
}

export interface GraphLink {
  source: string;
  target: string;
  relationship: string;
  properties?: any;
}

export interface GraphData {
  nodes: GraphNode[];
  links: GraphLink[];
}

export interface DashboardActivityItem {
  id: number;
  type: "scan_start" | "vuln_found" | "scan_complete" | "error" | "retry" | "circuit_break";
  message: string;
  target?: string | null;
  timestamp: string;
  details?: string | null;
}

export interface DashboardActivityResponse {
  activities: DashboardActivityItem[];
}

// API Methods

// Authentication
export const authAPI = {
  login: async (credentials: LoginRequest) => {
    const response = await api.post<TokenResponse>("/auth/login", credentials);
    return response.data;
  },

  register: async (data: RegisterRequest): Promise<User> => {
    const response = await api.post("/auth/register", data);
    return response.data;
  },

  getCurrentUser: async (): Promise<User> => {
    const response = await api.get("/auth/me");
    return response.data;
  },

  logout: () => {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
  },
};

// Scans
export const scansAPI = {
  list: async (params?: { skip?: number; limit?: number, status?: string }): Promise<{ scans: Scan[], total: number }> => {
    const response = await api.get("/scans", { params });
    return response.data;
  },

  get: async (scanId: string): Promise<Scan> => {
    const response = await api.get(`/scans/${scanId}`);
    return response.data;
  },

  create: async (data: ScanCreate): Promise<Scan> => {
    const response = await api.post("/scans", data);
    return response.data;
  },

  delete: async (scanId: string): Promise<void> => {
    await api.delete(`/scans/${scanId}`);
  },
};

// Vulnerabilities
export const vulnerabilitiesAPI = {
  list: async (params?: {
    skip?: number;
    limit?: number;
    severity?: string;
    status?: string;
    search?: string;
  }): Promise<{ vulnerabilities: Vulnerability[], total: number }> => {
    const response = await api.get("/vulnerabilities", { params });
    return response.data;
  },

  get: async (vulnId: number): Promise<Vulnerability> => {
    const response = await api.get(`/vulnerabilities/${vulnId}`);
    return response.data;
  },

  stats: async (): Promise<VulnerabilityStats> => {
    const response = await api.get("/vulnerabilities/stats");
    return response.data;
  },
};

// Logs
export const logsAPI = {
  list: async (params?: {
    skip?: number;
    limit?: number;
    level?: string;
    component?: string;
    search?: string;
    scan_id?: number;
  }): Promise<{ logs: Log[], total: number }> => {
    const response = await api.get("/logs", { params });
    return response.data;
  },
};

// Dashboard
export const dashboardAPI = {
  activity: async (params?: { limit?: number }): Promise<DashboardActivityResponse> => {
    const response = await api.get("/dashboard/activity", { params });
    return response.data;
  },
};

// Graph
export const graphAPI = {
  get: async (): Promise<GraphData> => {
    const response = await api.get("/graph");
    // The backend sends "edges", but react-force-graph wants "links"
    return { nodes: response.data.nodes, links: response.data.edges };
  },

  getNode: async (nodeId: string): Promise<GraphNode> => {
    const response = await api.get(`/graph/nodes/${nodeId}`);
    return response.data;
  },
};

// Settings
export const settingsAPI = {
  get: async (): Promise<Settings> => {
    const response = await api.get("/settings");
    return response.data;
  },

  update: async (data: Partial<Settings>): Promise<Settings> => {
    const response = await api.put("/settings", data);
    return response.data;
  },
};

// Agent Status
export interface AgentComponent {
  id: string;
  name: string;
  status: "online" | "offline" | "warning" | "degraded";
  description: string;
  details: Record<string, any>;
}

export interface SystemInfo {
  cpu: { percent: number; cores: number };
  memory: { percent: number; used_gb: number; total_gb: number };
  disk: { percent: number; used_gb: number; total_gb: number };
  platform: string;
  python_version: string;
}

export interface AgentStatus {
  status: "online" | "offline" | "degraded" | "warning";
  timestamp: string;
  uptime: number;
  components: AgentComponent[];
  system: SystemInfo;
  activity: {
    activeScans: number;
    queuedScans: number;
  };
}

export const agentAPI = {
  getStatus: async (): Promise<AgentStatus> => {
    const response = await api.get("/agent/status");
    return response.data;
  },
};

export default api;
