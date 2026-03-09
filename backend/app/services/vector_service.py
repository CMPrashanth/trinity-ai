"""ChromaDB vector database service for RAG"""

from typing import List, Dict, Any, Optional
from ..config import settings

# Make chromadb optional - use fallback data if not installed
try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    CHROMADB_AVAILABLE = True
except ImportError:
    chromadb = None
    ChromaSettings = None
    CHROMADB_AVAILABLE = False
    print("⚠️  chromadb not installed - using fallback CVE data")


class VectorService:
    """Service for ChromaDB vector operations (RAG system)"""
    
    def __init__(self):
        self.client = None
        self.collection = None
        self._connect()
    
    def _connect(self):
        """Connect to ChromaDB"""
        if not CHROMADB_AVAILABLE:
            print("⚠️  ChromaDB not available - using fallback data")
            return
            
        try:
            # Try to connect to ChromaDB server
            self.client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT
            )
            
            # Get or create collection for CVE data
            self.collection = self.client.get_or_create_collection(
                name="cve_knowledge_base",
                metadata={"description": "CVE vulnerability knowledge base for RAG"}
            )
            
            print("✅ Connected to ChromaDB")
            
        except Exception as e:
            print(f"⚠️  ChromaDB connection failed: {e}")
            print("   Falling back to persistent client")
            
            try:
                # Fallback to persistent client
                self.client = chromadb.Client(ChromaSettings(
                    chroma_db_impl="duckdb+parquet",
                    persist_directory=settings.CHROMA_PERSIST_DIR
                ))
                
                self.collection = self.client.get_or_create_collection(
                    name="cve_knowledge_base",
                    metadata={"description": "CVE vulnerability knowledge base for RAG"}
                )
                
                print("✅ Using ChromaDB persistent client")
                
            except Exception as e2:
                print(f"⚠️  ChromaDB persistent client failed: {e2}")
                print("   RAG features will use fallback data")
    
    async def add_cve_data(
        self,
        cve_id: str,
        description: str,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Add CVE data to vector database"""
        
        if not self.collection:
            return
        
        try:
            self.collection.upsert(
                documents=[description],
                metadatas=[metadata or {}],
                ids=[cve_id]
            )
            print(f"✅ Added {cve_id} to vector database")
            
        except Exception as e:
            print(f"⚠️  Failed to add CVE data: {e}")
    
    async def search_similar_cves(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar CVEs using vector similarity
        
        This is the core RAG functionality - finds relevant CVEs based on
        service information, error messages, or vulnerability descriptions.
        """
        
        if not self.collection:
            return self._get_fallback_cves(query)
        
        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=n_results,
                where=filter_metadata
            )
            
            # Format results
            cves = []
            for i in range(len(results['ids'][0])):
                cves.append({
                    "cve_id": results['ids'][0][i],
                    "description": results['documents'][0][i],
                    "similarity_score": 1.0 - results['distances'][0][i] if 'distances' in results else 0.9,
                    "metadata": results['metadatas'][0][i] if 'metadatas' in results else {}
                })
            
            return cves
            
        except Exception as e:
            print(f"⚠️  CVE search failed: {e}")
            return self._get_fallback_cves(query)
    
    async def bulk_add_cves(self, cve_list: List[Dict[str, Any]]):
        """Bulk add CVE data to vector database"""
        
        if not self.collection:
            return
        
        try:
            ids = [cve['cve_id'] for cve in cve_list]
            documents = [cve['description'] for cve in cve_list]
            metadatas = [cve.get('metadata', {}) for cve in cve_list]
            
            self.collection.upsert(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )
            
            print(f"✅ Added {len(cve_list)} CVEs to vector database")
            
        except Exception as e:
            print(f"⚠️  Bulk CVE add failed: {e}")
    
    async def get_cve_by_id(self, cve_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve specific CVE by ID"""
        
        if not self.collection:
            return None
        
        try:
            result = self.collection.get(ids=[cve_id])
            
            if result['ids']:
                return {
                    "cve_id": result['ids'][0],
                    "description": result['documents'][0],
                    "metadata": result['metadatas'][0] if 'metadatas' in result else {}
                }
        
        except Exception as e:
            print(f"⚠️  CVE retrieval failed: {e}")
        
        return None
    
    async def delete_cve(self, cve_id: str):
        """Delete CVE from vector database"""
        
        if not self.collection:
            return
        
        try:
            self.collection.delete(ids=[cve_id])
            print(f"✅ Deleted {cve_id} from vector database")
            
        except Exception as e:
            print(f"⚠️  CVE deletion failed: {e}")
    
    async def clear_collection(self):
        """Clear all data from collection"""
        
        if not self.client:
            return
        
        try:
            self.client.delete_collection("cve_knowledge_base")
            self.collection = self.client.create_collection(
                name="cve_knowledge_base",
                metadata={"description": "CVE vulnerability knowledge base for RAG"}
            )
            print("🧹 Cleared CVE vector database")
            
        except Exception as e:
            print(f"⚠️  Collection clear failed: {e}")
    
    def _get_fallback_cves(self, query: str) -> List[Dict[str, Any]]:
        """Return fallback CVE data when ChromaDB is unavailable"""
        
        # Mock CVE data for common services
        fallback_data = [
            {
                "cve_id": "CVE-2024-3094",
                "description": "XZ Utils Backdoor - Malicious code in liblzma library affecting SSH",
                "similarity_score": 0.92,
                "metadata": {"severity": "critical", "cvss": "10.0"}
            },
            {
                "cve_id": "CVE-2023-44487",
                "description": "HTTP/2 Rapid Reset Attack - Protocol vulnerability in HTTP/2 implementations",
                "similarity_score": 0.88,
                "metadata": {"severity": "high", "cvss": "7.5"}
            },
            {
                "cve_id": "CVE-2023-3817",
                "description": "OpenSSL DH Key Generation Issue - Vulnerability in OpenSSL key generation",
                "similarity_score": 0.85,
                "metadata": {"severity": "medium", "cvss": "5.3"}
            }
        ]
        
        # Simple keyword matching for fallback
        query_lower = query.lower()
        if "ssh" in query_lower or "openssh" in query_lower:
            return [fallback_data[0]]
        elif "http" in query_lower or "web" in query_lower:
            return [fallback_data[1]]
        elif "ssl" in query_lower or "tls" in query_lower:
            return [fallback_data[2]]
        
        return fallback_data[:3]
    
    async def initialize_knowledge_base(self):
        """Initialize ChromaDB with common CVE data"""
        
        if not self.collection:
            return
        
        # Sample CVE data to initialize the knowledge base
        sample_cves = [
            {
                "cve_id": "CVE-2024-3094",
                "description": "XZ Utils contains malicious backdoor code in liblzma library affecting SSH authentication. Remote code execution possible.",
                "metadata": {"severity": "critical", "cvss": "10.0", "year": "2024"}
            },
            {
                "cve_id": "CVE-2023-44487",
                "description": "HTTP/2 Rapid Reset Attack allows denial of service through rapid stream resets in HTTP/2 protocol implementations.",
                "metadata": {"severity": "high", "cvss": "7.5", "year": "2023"}
            },
            {
                "cve_id": "CVE-2023-3817",
                "description": "OpenSSL vulnerability in Diffie-Hellman key generation process affecting versions prior to 3.0.10.",
                "metadata": {"severity": "medium", "cvss": "5.3", "year": "2023"}
            },
            {
                "cve_id": "CVE-2024-0567",
                "description": "GnuTLS certificate chain validation bypass vulnerability allowing man-in-the-middle attacks.",
                "metadata": {"severity": "high", "cvss": "7.1", "year": "2024"}
            },
            {
                "cve_id": "CVE-2024-1086",
                "description": "Linux kernel nf_tables use-after-free vulnerability enabling local privilege escalation.",
                "metadata": {"severity": "critical", "cvss": "7.8", "year": "2024"}
            }
        ]
        
        try:
            await self.bulk_add_cves(sample_cves)
            print("✅ Initialized CVE knowledge base with sample data")
        except Exception as e:
            print(f"⚠️  Knowledge base initialization failed: {e}")
