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
                if scan_id:
                    node_query = """
                    MATCH (n)
                    WHERE n.scan_id = $scan_id
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
                    props = record["properties"]
                    nodes.append({
                        "id": str(record["id"]),
                        "label": props.get("label", props.get("name", "Unknown")),
                        "type": record["type"].lower(),
                        "properties": props
                    })
                
                # Query for edges
                if scan_id:
                    edge_query = """
                    MATCH (a)-[r]->(b)
                    WHERE a.scan_id = $scan_id
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
                        "properties": record["properties"]
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
                query = """
                MERGE (h:Host {ip: $ip})
                SET h.scan_id = $scan_id, h.updated_at = datetime()
                """
                for key, value in properties.items():
                    query += f", h.{key} = ${key}"
                
                session.run(query, ip=ip, scan_id=scan_id, **properties)
                return True
        except Exception as e:
            print(f"⚠️  Create host node failed: {e}")
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
                query = """
                MATCH (h:Host {ip: $host_ip})
                MERGE (p:Port {number: $port, host_ip: $host_ip})
                SET p.service = $service, p.version = $version, p.scan_id = $scan_id
                MERGE (h)-[:HAS_PORT]->(p)
                """
                session.run(query, host_ip=host_ip, port=port, service=service, version=version, scan_id=scan_id)
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
                query = """
                MATCH (h:Host {ip: $host_ip})
                MERGE (c:CVE {cve_id: $cve_id})
                SET c.severity = $severity, c.cvss = $cvss, c.title = $title, c.scan_id = $scan_id
                MERGE (h)-[:VULNERABLE_TO]->(c)
                """
                session.run(query, host_ip=host_ip, cve_id=cve_id, severity=severity, cvss=cvss, title=title, scan_id=scan_id)
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
    ) -> bool:
        """Create RUNS_SERVICE relationship between Host and Port."""
        
        if not self.driver:
            print(f"📊 [Mock] Would create service relationship: {host_ip}:{port} -> {service_name}")
            return True
        
        try:
            with self.driver.session() as session:
                query = """
                MATCH (h:Host {ip: $host_ip})-[:HAS_PORT]->(p:Port {number: $port})
                MERGE (s:Service {name: $service_name})
                SET s.banner = $banner
                MERGE (p)-[:RUNS_SERVICE]->(s)
                """
                session.run(query, host_ip=host_ip, port=port, service_name=service_name, banner=banner)
                return True
        except Exception as e:
            print(f"⚠️  Create service relationship failed: {e}")
            return False
        
        except Exception as e:
            print(f"⚠️  Clear graph failed: {e}")
    
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
                {"id": "host-1", "label": "192.168.1.1", "type": "host", "properties": {}},
                {"id": "host-2", "label": "192.168.1.42", "type": "host", "properties": {}},
                {"id": "host-3", "label": "192.168.1.105", "type": "host", "properties": {}},
                {"id": "port-1", "label": "22/SSH", "type": "port", "properties": {"parent": "host-2"}},
                {"id": "port-2", "label": "80/HTTP", "type": "port", "properties": {"parent": "host-2"}},
                {"id": "port-3", "label": "443/HTTPS", "type": "port", "properties": {"parent": "host-3"}},
                {"id": "port-4", "label": "3306/MySQL", "type": "port", "properties": {"parent": "host-3"}},
                {"id": "cve-1", "label": "CVE-2024-3094", "type": "cve", "properties": {"severity": "critical"}},
                {"id": "cve-2", "label": "CVE-2023-44487", "type": "cve", "properties": {"severity": "high"}},
                {"id": "cve-3", "label": "CVE-2023-3817", "type": "cve", "properties": {"severity": "medium"}},
            ],
            "edges": [
                {"from": "host-1", "to": "host-2", "relationship": "CONNECTED", "properties": {}},
                {"from": "host-1", "to": "host-3", "relationship": "CONNECTED", "properties": {}},
                {"from": "host-2", "to": "port-1", "relationship": "HAS_PORT", "properties": {}},
                {"from": "host-2", "to": "port-2", "relationship": "HAS_PORT", "properties": {}},
                {"from": "host-3", "to": "port-3", "relationship": "HAS_PORT", "properties": {}},
                {"from": "host-3", "to": "port-4", "relationship": "HAS_PORT", "properties": {}},
                {"from": "port-1", "to": "cve-1", "relationship": "VULNERABLE_TO", "properties": {}},
                {"from": "port-3", "to": "cve-2", "relationship": "VULNERABLE_TO", "properties": {}},
                {"from": "port-4", "to": "cve-3", "relationship": "VULNERABLE_TO", "properties": {}},
            ],
            "metadata": {"note": "Mock data - Neo4j not connected"}
        }
    
    def __del__(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
