"""Services package"""

from .ai_interface import AIInterface, DummyAI
from .scan_service import ScanService
from .graph_service import GraphService
from .vector_service import VectorService
from .ollama_client import OllamaClient

try:
    from .langchain_service import LangChainService
except Exception:  # pragma: no cover
    LangChainService = None

try:
    from .langgraph_workflow import LangGraphSecurityWorkflow
except Exception:  # pragma: no cover
    LangGraphSecurityWorkflow = None

from .cve_feed_service import CVEFeedService

# Note: TrinityAI should be imported from app.agent, not from services
# to avoid circular imports (TrinityAI depends on services)

__all__ = [
    "AIInterface",
    "DummyAI",
    "ScanService",
    "GraphService",
    "VectorService",
    "OllamaClient",
    "LangChainService",
    "LangGraphSecurityWorkflow",
    "CVEFeedService",
]
