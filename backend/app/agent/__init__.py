"""
Trinity Agent Module - Neuro-symbolic penetration testing agent.

Components:
- Guard: Scope and safety validation (Pydantic-based)
- Executor: Command execution with circuit breaker
- Planner: LLM-based attack planning via Ollama
- TrinityAI: Full AI implementation integrating all components
"""

from .guard import validate_scope, validate_safety
from .executor import CommandExecutor, ExecutionResult, CircuitBreaker, ParsedNmapResult
from .planner import AttackPlanner
from .trinity_ai import TrinityAI

__all__ = [
    # Guard
    "validate_scope",
    "validate_safety",
    # Executor
    "CommandExecutor",
    "ExecutionResult",
    "CircuitBreaker",
    "ParsedNmapResult",
    # Planner
    "AttackPlanner",
    # Main AI
    "TrinityAI",
]
