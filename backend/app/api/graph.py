"""Graph visualization API routes"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..schemas import GraphResponse
from ..models import User
from ..utils.auth import get_current_user
from ..services.graph_service import GraphService

router = APIRouter()


@router.get("/graph", response_model=GraphResponse)
async def get_graph_data(
    scan_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get attack graph data from Neo4j"""
    graph_service = GraphService()
    
    try:
        graph_data = await graph_service.get_graph(scan_id)
        return graph_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve graph data: {str(e)}"
        )


@router.get("/graph/nodes/{node_id}")
async def get_node_details(
    node_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get detailed information about a specific node"""
    graph_service = GraphService()
    
    try:
        node_data = await graph_service.get_node_details(node_id)
        
        if not node_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Node not found"
            )
        
        return node_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve node data: {str(e)}"
        )


@router.get("/graph/paths")
async def get_attack_paths(
    source: Optional[str] = None,
    target: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Get attack paths between nodes"""
    graph_service = GraphService()
    
    try:
        paths = await graph_service.find_paths(source, target)
        return {"paths": paths}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find paths: {str(e)}"
        )


@router.delete("/graph", status_code=status.HTTP_204_NO_CONTENT)
async def clear_graph(
    scan_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Clear graph data (graph hygiene)"""
    if not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    graph_service = GraphService()
    
    try:
        await graph_service.clear_graph(scan_id)
        return None
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to clear graph: {str(e)}"
        )


@router.post("/graph/export")
async def export_graph(
    format: str = Query("json", regex="^(json|graphml|cypher)$"),
    scan_id: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Export graph data in various formats"""
    graph_service = GraphService()
    
    try:
        exported_data = await graph_service.export_graph(format, scan_id)
        return exported_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to export graph: {str(e)}"
        )
