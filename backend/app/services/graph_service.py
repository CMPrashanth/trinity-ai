"""Neo4j graph database service"""

from typing import Optional, List, Dict, Any
from ..config import settings

# Make neo4j optional - use mock data if not installed
try:
    from neo4j import GraphDatabase
    NEO4J_AVAILABLE = True
except ImportError:
    GraphDatabase = None
    NEO4J_AVAILABLE = False
    print("⚠️  neo4j driver not installed - using mock graph data")


class GraphService:
    """Service for Neo4j graph operations"""

    @staticmethod
    def _json_safe(value: Any) -> Any:
        """Convert Neo4j/native values into JSON-serializable primitives."""

        if value is None or isinstance(value, (str, int, float, bool)):
            return value

        if isinstance(value, (list, tuple)):
            return [GraphService._json_safe(item) for item in value]

        if isinstance(value, dict):
            return {str(k): GraphService._json_safe(v) for k, v in value.items()}

        # Neo4j temporal/spatial types (e.g., neo4j.time.DateTime) are not JSON-serializable.
        # We convert them to strings to avoid FastAPI serialization failures.
        module_name = getattr(value.__class__, "__module__", "")
        if module_name.startswith("neo4j."):
            return str(value)

        # Last resort: stringify unknown objects.
        return str(value)
    
    def __init__(self):
        self.driver = None
        self._connect()
    
    def _connect(self):
        """Connect to Neo4j database"""
        if not NEO4J_AVAILABLE:
            print("⚠️  Neo4j driver not available - using mock data")
            return
            
        try:
            self.driver = GraphDatabase.driver(
                settings.NEO4J_URI,
                auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)
            )
            print("✅ Connected to Neo4j")
        except Exception as e:
            print(f"⚠️  Neo4j connection failed: {e}")
            print("   Graph features will use mock data")
    
    async def get_graph(self, scan_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve graph data from Neo4j
        
        Returns nodes and edges for visualization
        """
        
        if not self.driver:
            return self._get_mock_graph()
        
        try:
            with self.driver.session() as session:
                # Query for nodes
                #
                # IMPORTANT:
                # We store scan history in `scan_ids` (list) + `last_scan_id`.
                # Older nodes may only have `scan_id`.
                if scan_id:
                    node_query = """
                    MATCH (n)
                    WHERE $scan_id IN coalesce(n.scan_ids, [n.scan_id])
                    RETURN id(n) as id, labels(n)[0] as type, properties(n) as properties
                    """
                    nodes_result = session.run(node_query, scan_id=scan_id)
                else:
                    node_query = """
                    MATCH (n)
                    RETURN id(n) as id, labels(n)[0] as type, properties(n) as properties
                    LIMIT 100
                    """
                    nodes_result = session.run(node_query)
                
                nodes = []
                for record in nodes_result:
                    props = self._json_safe(record["properties"])
                    node_type = record["type"]

                    label = props.get("label") or props.get("name")
                    if not label:
                        if node_type == "Host":
                            label = props.get("ip") or "Unknown Host"
                        elif node_type == "Port":
                            number = props.get("number")
                            service = props.get("service")
                            if number and service:
                                label = f"{number}/{service}"
                            elif number:
                                label = str(number)
                            else:
                                label = "Unknown Port"
                        elif node_type == "CVE":
                            label = props.get("cve_id") or props.get("title") or "Unknown CVE"
                        else:
                            label = "Unknown"

                    nodes.append({
                        "id": str(record["id"]),
                        "label": label,
                        "type": node_type.lower(),
                        "properties": props
                    })
                
                # Query for edges
                if scan_id:
                    edge_query = """
                    MATCH (a)-[r]->(b)
                    WHERE (
                        $scan_id IN coalesce(r.scan_ids, [])
                        OR (
                            $scan_id IN coalesce(a.scan_ids, [a.scan_id])
                            AND $scan_id IN coalesce(b.scan_ids, [b.scan_id])
                        )
                    )
                    RETURN id(a) as from, id(b) as to, type(r) as relationship, properties(r) as properties
                    """
                    edges_result = session.run(edge_query, scan_id=scan_id)
                else:
                    edge_query = """
                    MATCH (a)-[r]->(b)
                    RETURN id(a) as from, id(b) as to, type(r) as relationship, properties(r) as properties
                    LIMIT 100
                    """
                    edges_result = session.run(edge_query)
                
                edges = []
                for record in edges_result:
                    edges.append({
                        "from": str(record["from"]),
                        "to": str(record["to"]),
                        "relationship": record["relationship"],
                        "properties": self._json_safe(record["properties"])
                    })
                
                return {
                    "nodes": nodes,
                    "edges": edges,
                    "metadata": {"scan_id": scan_id, "total_nodes": len(nodes), "total_edges": len(edges)}
                }
        
        except Exception as e:
            print(f"⚠️  Neo4j query failed: {e}")
            return self._get_mock_graph()
    
    async def get_node_details(self, node_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific node"""
        
        if not self.driver:
            return None
        
        try:
            with self.driver.session() as session:
                query = """
                MATCH (n)
                WHERE id(n) = $node_id
                RETURN labels(n)[0] as type, properties(n) as properties
                """
                result = session.run(query, node_id=int(node_id))
                record = result.single()
                
                if record:
                    return {
                        "type": record["type"],
                        "properties": record["properties"]
                    }
        except Exception as e:
            print(f"⚠️  Node query failed: {e}")
        
        return None
    
    async def find_paths(
        self,
        source: Optional[str] = None,
        target: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Find attack paths between nodes"""
        
        if not self.driver:
            return []
        
        try:
            with self.driver.session() as session:
                if source and target:
                    query = """
                    MATCH path = shortestPath((a)-[*]-(b))
                    WHERE id(a) = $source AND id(b) = $target
                    RETURN path
                    """
                    result = session.run(query, source=int(source), target=int(target))
                else:
                    query = """
                    MATCH path = (a)-[*1..3]->(b)
                    WHERE labels(a)[0] = 'Host' AND labels(b)[0] = 'CVE'
                    RETURN path
                    LIMIT 10
                    """
                    result = session.run(query)
                
                paths = []
                for record in result:
                    path_data = record["path"]
                    paths.append({
                        "nodes": [str(node.id) for node in path_data.nodes],
                        "length": len(path_data.relationships)
                    })
                
                return paths
        
        except Exception as e:
            print(f"⚠️  Path query failed: {e}")
        
        return []
    
    async def clear_graph(self, scan_id: Optional[str] = None):
        """Clear graph data (graph hygiene)"""
        
        if not self.driver:
            return
        
        try:
            with self.driver.session() as session:
                if scan_id:
                    query = """
                    MATCH (n {scan_id: $scan_id})
                    DETACH DELETE n
                    """
                    session.run(query, scan_id=scan_id)
                else:
                    query = "MATCH (n) DETACH DELETE n"
                    session.run(query)
                
                print(f"🧹 Graph cleared for scan: {scan_id or 'all'}")
        
        except Exception as e:
            print(f"⚠️  Clear graph failed: {e}")
    
    # ========== Trinity AI Integration Methods ==========
    
    async def create_host_node(self, ip: str, scan_id: str, **properties) -> bool:
        """Create a Host node in Neo4j."""
        
        if not self.driver:
            print(f"📊 [Mock] Would create Host node: {ip}")
            return True
        
        try:
            with self.driver.session() as session:
                properties.setdefault("label", ip)
                properties.setdefault("name", ip)
                query = """
                MERGE (h:Host {ip: $ip})
                SET h.scan_id = $scan_id,
                    h.last_scan_id = $scan_id,
                    h.updated_at = datetime(),
                    h.scan_ids = CASE
                        WHEN h.scan_ids IS NULL THEN [$scan_id]
                        WHEN $scan_id IN h.scan_ids THEN h.scan_ids
                        ELSE h.scan_ids + $scan_id
                    END
                """
                for key, value in properties.items():
                    query += f", h.{key} = ${key}"
                
                session.run(query, ip=ip, scan_id=scan_id, **properties)
                return True
        except Exception as e:
            print(f"⚠️  Create host node failed: {e}")
            return False

    async def create_network_node(
        self,
        cidr: str,
        scan_id: str,
        name: Optional[str] = None,
        **properties,
    ) -> bool:
        """Create a Network node in Neo4j."""

        cidr = (cidr or "").strip()
        if not cidr:
            return False

        if not self.driver:
            print(f"📊 [Mock] Would create Network node: {cidr}")
            return True

        try:
            with self.driver.session() as session:
                label = name or cidr
                properties.setdefault("label", label)
                properties.setdefault("name", label)
                query = """
                MERGE (n:Network {cidr: $cidr})
                SET n.scan_id = $scan_id,
                    n.last_scan_id = $scan_id,
                    n.updated_at = datetime(),
                    n.scan_ids = CASE
                        WHEN n.scan_ids IS NULL THEN [$scan_id]
                        WHEN $scan_id IN n.scan_ids THEN n.scan_ids
                        ELSE n.scan_ids + $scan_id
                    END
                """
                for key, value in properties.items():
                    query += f", n.{key} = ${key}"

                session.run(query, cidr=cidr, scan_id=scan_id, **properties)
                return True
        except Exception as e:
            print(f"⚠️  Create network node failed: {e}")
            return False

    async def connect_host_to_network(
        self,
        cidr: str,
        host_ip: str,
        scan_id: str,
        relationship: str = "IN_NETWORK",
    ) -> bool:
        """Connect a Host node to a Network node."""

        cidr = (cidr or "").strip()
        host_ip = (host_ip or "").strip()
        if not cidr or not host_ip:
            return False

        if not self.driver:
            print(f"📊 [Mock] Would connect Host {host_ip} -> Network {cidr}")
            return True

        if not relationship.isidentifier():
            relationship = "IN_NETWORK"

        try:
            with self.driver.session() as session:
                query = f"""
                MATCH (h:Host {{ip: $host_ip}})
                MATCH (n:Network {{cidr: $cidr}})
                MERGE (h)-[r:{relationship}]->(n)
                SET h.scan_id = $scan_id,
                    h.last_scan_id = $scan_id,
                    n.scan_id = $scan_id,
                    n.last_scan_id = $scan_id,
                    r.last_scan_id = $scan_id,
                    h.scan_ids = CASE
                        WHEN h.scan_ids IS NULL THEN [$scan_id]
                        WHEN $scan_id IN h.scan_ids THEN h.scan_ids
                        ELSE h.scan_ids + $scan_id
                    END,
                    n.scan_ids = CASE
                        WHEN n.scan_ids IS NULL THEN [$scan_id]
                        WHEN $scan_id IN n.scan_ids THEN n.scan_ids
                        ELSE n.scan_ids + $scan_id
                    END,
                    r.scan_ids = CASE
                        WHEN r.scan_ids IS NULL THEN [$scan_id]
                        WHEN $scan_id IN r.scan_ids THEN r.scan_ids
                        ELSE r.scan_ids + $scan_id
                    END
                """
                session.run(query, host_ip=host_ip, cidr=cidr, scan_id=scan_id)
                return True
        except Exception as e:
            print(f"⚠️  Connect host to network failed: {e}")
            return False
    
    async def create_port_node(
        self,
        host_ip: str,
        port: int,
        service: str,
        version: Optional[str] = None,
        scan_id: str = "",
    ) -> bool:
        """Create a Port node and link to Host via HAS_PORT relationship."""
        
        if not self.driver:
            print(f"📊 [Mock] Would create Port node: {host_ip}:{port}/{service}")
            return True
        
        try:
            with self.driver.session() as session:
                label = f"{port}/{service}" if service else str(port)
                query = """
                MATCH (h:Host {ip: $host_ip})
                MERGE (p:Port {number: $port, host_ip: $host_ip})
                SET p.service = $service,
                    p.version = $version,
                    p.scan_id = $scan_id,
                    p.last_scan_id = $scan_id,
                    p.updated_at = datetime(),
                    p.label = $label,
                    p.name = $label,
                    p.scan_ids = CASE
                        WHEN p.scan_ids IS NULL THEN [$scan_id]
                        WHEN $scan_id IN p.scan_ids THEN p.scan_ids
                        ELSE p.scan_ids + $scan_id
                    END,
                    h.scan_id = $scan_id,
                    h.last_scan_id = $scan_id,
                    h.scan_ids = CASE
                        WHEN h.scan_ids IS NULL THEN [$scan_id]
                        WHEN $scan_id IN h.scan_ids THEN h.scan_ids
                        ELSE h.scan_ids + $scan_id
                    END
                MERGE (h)-[r:HAS_PORT]->(p)
                SET r.last_scan_id = $scan_id,
                    r.scan_ids = CASE
                        WHEN r.scan_ids IS NULL THEN [$scan_id]
                        WHEN $scan_id IN r.scan_ids THEN r.scan_ids
                        ELSE r.scan_ids + $scan_id
                    END
                """
                session.run(query, host_ip=host_ip, port=port, service=service, version=version, scan_id=scan_id, label=label)
                return True
        except Exception as e:
            print(f"⚠️  Create port node failed: {e}")
            return False
    
    async def create_vulnerability_node(
        self,
        host_ip: str,
        cve_id: str,
        severity: str,
        cvss: Optional[float] = None,
        title: str = "",
        scan_id: str = "",
    ) -> bool:
        """Create a CVE node and link to Host via VULNERABLE_TO relationship."""
        
        if not self.driver:
            print(f"📊 [Mock] Would create CVE node: {cve_id} ({severity})")
            return True
        
        try:
            with self.driver.session() as session:
                label = cve_id
                query = """
                MATCH (h:Host {ip: $host_ip})
                MERGE (c:CVE {cve_id: $cve_id})
                SET c.severity = $severity,
                    c.cvss = $cvss,
                    c.title = $title,
                    c.scan_id = $scan_id,
                    c.last_scan_id = $scan_id,
                    c.updated_at = datetime(),
                    c.label = $label,
                    c.name = $label,
                    c.scan_ids = CASE
                        WHEN c.scan_ids IS NULL THEN [$scan_id]
                        WHEN $scan_id IN c.scan_ids THEN c.scan_ids
                        ELSE c.scan_ids + $scan_id
                    END,
                    h.scan_id = $scan_id,
                    h.last_scan_id = $scan_id,
                    h.scan_ids = CASE
                        WHEN h.scan_ids IS NULL THEN [$scan_id]
                        WHEN $scan_id IN h.scan_ids THEN h.scan_ids
                        ELSE h.scan_ids + $scan_id
                    END
                MERGE (h)-[r:VULNERABLE_TO]->(c)
                SET r.last_scan_id = $scan_id,
                    r.scan_ids = CASE
                        WHEN r.scan_ids IS NULL THEN [$scan_id]
                        WHEN $scan_id IN r.scan_ids THEN r.scan_ids
                        ELSE r.scan_ids + $scan_id
                    END
                """
                session.run(query, host_ip=host_ip, cve_id=cve_id, severity=severity, cvss=cvss, title=title, scan_id=scan_id, label=label)
                return True
        except Exception as e:
            print(f"⚠️  Create vulnerability node failed: {e}")
            return False
    
    async def create_service_relationship(
        self,
        host_ip: str,
        port: int,
        service_name: str,
        banner: Optional[str] = None,
        scan_id: str = "",
    ) -> bool:
        """Create RUNS_SERVICE relationship between Host and Port."""
        
        if not self.driver:
            print(f"📊 [Mock] Would create service relationship: {host_ip}:{port} -> {service_name}")
            return True
        
        try:
            with self.driver.session() as session:
                query = """
                MATCH (h:Host {ip: $host_ip})-[:HAS_PORT]->(p:Port {number: $port, host_ip: $host_ip})
                MERGE (s:Service {name: $service_name, scan_id: $scan_id})
                SET s.banner = $banner, s.updated_at = datetime(), s.label = $service_name, s.name = $service_name
                MERGE (p)-[r:RUNS_SERVICE]->(s)
                SET p.scan_id = $scan_id,
                    p.last_scan_id = $scan_id,
                    p.scan_ids = CASE
                        WHEN p.scan_ids IS NULL THEN [$scan_id]
                        WHEN $scan_id IN p.scan_ids THEN p.scan_ids
                        ELSE p.scan_ids + $scan_id
                    END,
                    r.last_scan_id = $scan_id,
                    r.scan_ids = CASE
                        WHEN r.scan_ids IS NULL THEN [$scan_id]
                        WHEN $scan_id IN r.scan_ids THEN r.scan_ids
                        ELSE r.scan_ids + $scan_id
                    END
                """
                session.run(
                    query,
                    host_ip=host_ip,
                    port=port,
                    service_name=service_name,
                    banner=banner,
                    scan_id=scan_id,
                )
                return True
        except Exception as e:
            print(f"⚠️  Create service relationship failed: {e}")
            return False
    
    async def export_graph(self, format: str, scan_id: Optional[str] = None) -> Dict[str, Any]:
        """Export graph in various formats"""
        
        graph_data = await self.get_graph(scan_id)
        
        if format == "json":
            return graph_data
        elif format == "graphml":
            # Convert to GraphML format
            return {"format": "graphml", "data": "GraphML export not yet implemented"}
        elif format == "cypher":
            # Generate Cypher statements
            cypher_statements = []
            for node in graph_data["nodes"]:
                cypher_statements.append(
                    f"CREATE (n:{node['type']} {{label: '{node['label']}'}});"
                )
            return {"format": "cypher", "statements": cypher_statements}
        
        return graph_data
    
    def _get_mock_graph(self) -> Dict[str, Any]:
        """Return mock graph data when Neo4j is unavailable"""
        return {
            "nodes": [
                {"id": "net-1", "label": "10.10.0.0/24", "type": "network", "properties": {"cidr": "10.10.0.0/24"}},
                {"id": "host-1", "label": "10.10.0.11 (juice-shop)", "type": "host", "properties": {"ip": "10.10.0.11", "role": "juice-shop"}},
                {"id": "host-2", "label": "10.10.0.12 (webgoat)", "type": "host", "properties": {"ip": "10.10.0.12", "role": "webgoat"}},
                {"id": "port-1", "label": "3000/HTTP", "type": "port", "properties": {"number": 3000, "service": "http", "parent": "host-1"}},
                {"id": "port-2", "label": "8080/HTTP", "type": "port", "properties": {"number": 8080, "service": "http", "parent": "host-2"}},
                {"id": "svc-1", "label": "http", "type": "service", "properties": {"name": "http"}},
                {"id": "cve-1", "label": "CVE-2023-44487", "type": "cve", "properties": {"severity": "high", "cvss": 7.5}},
                {"id": "cve-2", "label": "CVE-2024-3094", "type": "cve", "properties": {"severity": "critical", "cvss": 10.0}},
            ],
            "edges": [
                {"from": "host-1", "to": "net-1", "relationship": "IN_NETWORK", "properties": {}},
                {"from": "host-2", "to": "net-1", "relationship": "IN_NETWORK", "properties": {}},
                {"from": "host-1", "to": "port-1", "relationship": "HAS_PORT", "properties": {}},
                {"from": "host-2", "to": "port-2", "relationship": "HAS_PORT", "properties": {}},
                {"from": "port-1", "to": "svc-1", "relationship": "RUNS_SERVICE", "properties": {}},
                {"from": "port-2", "to": "svc-1", "relationship": "RUNS_SERVICE", "properties": {}},
                {"from": "host-1", "to": "cve-1", "relationship": "VULNERABLE_TO", "properties": {}},
                {"from": "host-2", "to": "cve-2", "relationship": "VULNERABLE_TO", "properties": {}},
            ],
            "metadata": {"note": "Mock data - Neo4j not connected"}
        }
    
    def __del__(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
