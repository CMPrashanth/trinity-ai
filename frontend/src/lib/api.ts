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
  scan_type?: string;
  profile: string;
  status: string;
  start_time: string;
  end_time?: string;
  duration?: string;
  progress?: number;
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

export interface ChromaStatus {
  status: "ok" | "unavailable";
  message?: string;
  collection?: string;
  count?: number;
  lastSyncState?: any;
}

export interface CveSearchResult {
  cve_id: string;
  description: string;
  similarity_score?: number;
  metadata?: any;
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

const mapSettingsFromApi = (raw: any): Settings => {
  const blockedList = raw?.blockedCommands ?? raw?.blocked_commands;
  return {
    llm_model: raw?.llmModel ?? raw?.llm_model ?? "",
    max_retries: raw?.maxRetries ?? raw?.max_retries ?? 3,
    execution_timeout: raw?.executionTimeout ?? raw?.execution_timeout ?? 30,
    enable_self_healing: raw?.enableSelfHealing ?? raw?.enable_self_healing ?? true,
    circuit_breaker_enabled: raw?.circuitBreakerEnabled ?? raw?.circuit_breaker_enabled ?? true,
    neo4j_uri: raw?.neo4jUri ?? raw?.neo4j_uri ?? "",
    chroma_db_path: raw?.chromaDbPath ?? raw?.chroma_db_path ?? "",
    graph_hygiene_enabled: raw?.graphHygieneEnabled ?? raw?.graph_hygiene_enabled ?? true,
    allowed_subnet: raw?.allowedSubnet ?? raw?.allowed_subnet ?? "",
    blocked_commands: Array.isArray(blockedList) ? blockedList.join(", ") : (blockedList ?? raw?.blockedCommands ?? ""),
    email_alerts: raw?.emailAlerts ?? raw?.email_alerts ?? false,
    slack_integration: raw?.slackIntegration ?? raw?.slack_integration ?? false,
    alert_on_critical: raw?.alertOnCritical ?? raw?.alert_on_critical ?? true,
    alert_on_circuit_break: raw?.alertOnCircuitBreak ?? raw?.alert_on_circuit_break ?? true,
  };
};

const mapSettingsToApi = (data: Partial<Settings>): Record<string, any> => {
  const payload: Record<string, any> = {};
  if (data.llm_model !== undefined) payload.llmModel = data.llm_model;
  if (data.max_retries !== undefined) payload.maxRetries = data.max_retries;
  if (data.execution_timeout !== undefined) payload.executionTimeout = data.execution_timeout;
  if (data.enable_self_healing !== undefined) payload.enableSelfHealing = data.enable_self_healing;
  if (data.circuit_breaker_enabled !== undefined) payload.circuitBreakerEnabled = data.circuit_breaker_enabled;
  if (data.neo4j_uri !== undefined) payload.neo4jUri = data.neo4j_uri;
  if (data.chroma_db_path !== undefined) payload.chromaDbPath = data.chroma_db_path;
  if (data.graph_hygiene_enabled !== undefined) payload.graphHygieneEnabled = data.graph_hygiene_enabled;
  if (data.allowed_subnet !== undefined) payload.allowedSubnet = data.allowed_subnet;
  if (data.blocked_commands !== undefined) payload.blockedCommands = data.blocked_commands;
  if (data.email_alerts !== undefined) payload.emailAlerts = data.email_alerts;
  if (data.slack_integration !== undefined) payload.slackIntegration = data.slack_integration;
  if (data.alert_on_critical !== undefined) payload.alertOnCritical = data.alert_on_critical;
  if (data.alert_on_circuit_break !== undefined) payload.alertOnCircuitBreak = data.alert_on_circuit_break;
  return payload;
};

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
    const limit = params?.limit;
    const skip = params?.skip;
    const pageSize = limit ?? 10;
    const page = skip != null && pageSize > 0 ? Math.floor(skip / pageSize) + 1 : 1;
    const response = await api.get("/scans", {
      params: {
        page,
        page_size: pageSize,
        status: params?.status,
      }
    });
    return response.data;
  },

  get: async (scanId: string): Promise<Scan> => {
    const response = await api.get(`/scans/${scanId}`);
    return response.data;
  },

  create: async (data: ScanCreate): Promise<Scan> => {
    // Backend expects scanProfile (camelCase); frontend uses scan_profile.
    const payload: any = {
      target: data.target,
      scanProfile: data.scan_profile,
      advancedOptions: data.advancedOptions,
    };
    const response = await api.post("/scans", payload);
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
    const limit = params?.limit;
    const skip = params?.skip;
    const pageSize = limit ?? 50;
    const page = skip != null && pageSize > 0 ? Math.floor(skip / pageSize) + 1 : 1;
    const response = await api.get("/logs", {
      params: {
        page,
        page_size: pageSize,
        level: params?.level,
        component: params?.component,
        search: params?.search,
        scan_id: params?.scan_id,
      }
    });
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
  get: async (scanId?: string | null): Promise<GraphData> => {
    const response = await api.get("/graph", {
      params: scanId ? { scan_id: scanId } : undefined,
    });
    // Backend returns edges with keys {from,to}; react-force-graph expects {source,target}
    const rawEdges: any[] = Array.isArray(response.data?.edges)
      ? response.data.edges
      : Array.isArray(response.data?.links)
        ? response.data.links
        : [];

    const links: GraphLink[] = rawEdges
      .map((edge: any) => {
        const source = edge?.from ?? edge?.from_node ?? edge?.source;
        const target = edge?.to ?? edge?.to_node ?? edge?.target;
        if (!source || !target) return null;
        return {
          source: String(source),
          target: String(target),
          relationship: String(edge?.relationship ?? "CONNECTED"),
          properties: edge?.properties ?? {},
        };
      })
      .filter(Boolean) as GraphLink[];

    const nodes: GraphNode[] = (response.data.nodes ?? []).map((n: any) => ({
      ...n,
      id: String(n.id),
    }));

    return { nodes, links };
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
    return mapSettingsFromApi(response.data);
  },

  update: async (data: Partial<Settings>): Promise<Settings> => {
    const response = await api.put("/settings", mapSettingsToApi(data));
    return mapSettingsFromApi(response.data);
  },

  testN8n: async (): Promise<{ message: string }> => {
    const response = await api.post("/settings/integrations/n8n/test");
    return response.data;
  },

  syncCvesNow: async (): Promise<{ message: string; taskId?: string }> => {
    const response = await api.post("/settings/cve/sync-now");
    return response.data;
  },
};

// CVEs / Chroma utilities
export const cvesAPI = {
  status: async (): Promise<ChromaStatus> => {
    const response = await api.get("/cves/status");
    return response.data;
  },

  seedDemo: async (reset: boolean = false): Promise<{ message: string; added: number; count: number }> => {
    const response = await api.post("/cves/seed-demo", { reset });
    return response.data;
  },

  search: async (q: string, n: number = 5, severity?: string): Promise<{ results: CveSearchResult[] }> => {
    const response = await api.get("/cves/search", { params: { q, n, severity } });
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
