#!/usr/bin/env python3
"""
MCP Server - Code Analysis Tools

Exposes project analysis capabilities via Model Context Protocol.
Directly uses service functions without redundancy.
Includes LangSmith integration for token tracking and observability.
"""

import ast
import asyncio
import hashlib
import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional
from functools import wraps

from mcp.server import Server, InitializationOptions
from mcp.server.stdio import stdio_server
from mcp import types

# LangSmith integration
try:
    from langsmith import Client
    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    # Warning will be logged after logger is initialized

# Handle imports whether running as module or standalone script
try:
    # When running as part of the package
    from src.core.services.relationship_service import RelationshipExtractor
    from src.core.services.project_service import ProjectAnalyzer, ArchitectureVisitor
    from src.core.services.discovery_tools import (
        find_entry_points,
        list_modules,
        get_file_metadata,
    )
except ImportError:
    # When running as standalone MCP server
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from relationship_service import RelationshipExtractor
    from project_service import ProjectAnalyzer, ArchitectureVisitor
    from discovery_tools import find_entry_points, list_modules, get_file_metadata

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Log LangSmith availability
if not LANGSMITH_AVAILABLE:
    logger.warning("LangSmith not available. Install with: pip install langsmith")

server = Server("code-analysis-mcp")

# =============================================================================
# LANGSMITH CONFIGURATION
# =============================================================================

# Initialize LangSmith client if available
langsmith_client: Optional[Any] = None

if LANGSMITH_AVAILABLE:
    langsmith_api_key = os.getenv("LANGSMITH_API_KEY")
    langsmith_project = os.getenv("LANGSMITH_PROJECT", "code-analysis-mcp")
    
    if langsmith_api_key:
        try:
            langsmith_client = Client(api_key=langsmith_api_key)
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_PROJECT"] = langsmith_project
            logger.info(f"LangSmith tracking enabled for project: {langsmith_project}")
            
            # Startup self-test: create a quick run to confirm connectivity
            try:
                import uuid as _uuid
                from datetime import datetime, timezone
                _test_id = _uuid.uuid4()
                _now = datetime.now(timezone.utc)
                langsmith_client.create_run(
                    name="mcp_server_startup",
                    run_type="tool",
                    id=_test_id,
                    project_name=langsmith_project,
                    inputs={"event": "server_started"},
                    start_time=_now,
                )
                langsmith_client.update_run(
                    run_id=_test_id,
                    outputs={"status": "ok"},
                    end_time=_now,
                )
                logger.info(f"LangSmith self-test PASSED (run {_test_id})")
            except Exception as st_err:
                logger.warning(f"LangSmith self-test FAILED: {st_err}")
                logger.warning("Traces may not appear in dashboard. Check API key and network.")
                
        except Exception as e:
            logger.warning(f"Failed to initialize LangSmith: {e}")
            langsmith_client = None
    else:
        logger.info("LangSmith API key not found. Set LANGSMITH_API_KEY to enable tracking.")
else:
    logger.info("LangSmith not installed. Token tracking disabled.")

# Token counting via tiktoken
try:
    import tiktoken
    _encoding = tiktoken.get_encoding("cl100k_base")
    def _count_tokens(text: str) -> int:
        return len(_encoding.encode(str(text)))
    TIKTOKEN_AVAILABLE = True
except ImportError:
    def _count_tokens(text: str) -> int:
        return len(str(text)) // 4  # rough estimate
    TIKTOKEN_AVAILABLE = False
    logger.warning("tiktoken not available, using rough token estimate")


def track_tool_call(func):
    """Decorator to track tool calls with LangSmith including token counts."""
    @wraps(func)
    async def wrapper(name: str, arguments: dict) -> list:
        start_time = time.time()
        project_name = os.getenv("LANGSMITH_PROJECT", "code-analysis-mcp")

        # Count input tokens
        input_str = json.dumps(arguments, default=str)
        input_tokens = _count_tokens(input_str)

        # If LangSmith is not available, just run the tool
        if not (LANGSMITH_AVAILABLE and langsmith_client):
            res = await func(name, arguments)
            logger.info(f"Tool '{name}' completed in {time.time() - start_time:.2f}s (no tracking)")
            return res

        import uuid as _uuid
        from datetime import datetime, timezone
        run_id = _uuid.uuid4()
        _now = lambda: datetime.now(timezone.utc)

        # Open a run *before* executing the tool
        try:
            langsmith_client.create_run(
                name=f"mcp_tool_{name}",
                run_type="llm",
                id=run_id,
                project_name=project_name,
                inputs={"tool": name, "arguments": arguments},
                start_time=_now(),
                extra={
                    "metadata": {
                        "tool_name": name,
                        "source": "claude_desktop_mcp",
                    },
                },
            )
            logger.info(f"LangSmith: opened run {run_id} for '{name}' (input: {input_tokens} tokens)")
        except Exception as log_err:
            logger.warning(f"LangSmith create_run failed: {log_err}")
            res = await func(name, arguments)
            return res

        # Execute the actual tool
        try:
            res = await func(name, arguments)
            execution_time = time.time() - start_time

            # Count output tokens
            output_str = str(res)
            output_tokens = _count_tokens(output_str)
            total_tokens = input_tokens + output_tokens

            # Close the run with outputs and token usage
            # LangSmith expects usage_metadata at the top level of extra
            # and token_usage inside outputs for the dashboard to display tokens
            try:
                langsmith_client.update_run(
                    run_id=run_id,
                    outputs={
                        "result": output_str[:1000],
                        "llm_output": {
                            "token_usage": {
                                "prompt_tokens": input_tokens,
                                "completion_tokens": output_tokens,
                                "total_tokens": total_tokens,
                            },
                            "model_name": "mcp-tool",
                        },
                    },
                    end_time=_now(),
                    extra={
                        "metadata": {
                            "tool_name": name,
                            "execution_time_seconds": round(execution_time, 3),
                            "status": "success",
                        },
                        "usage_metadata": {
                            "input_tokens": input_tokens,
                            "output_tokens": output_tokens,
                            "total_tokens": total_tokens,
                        },
                    },
                )
                logger.info(
                    f"LangSmith: closed run {run_id} for '{name}' "
                    f"({execution_time:.2f}s, tokens: {input_tokens}→{output_tokens}, total: {total_tokens})"
                )
            except Exception as log_err:
                logger.warning(f"LangSmith update_run failed: {log_err}")

            return res

        except Exception as e:
            execution_time = time.time() - start_time

            # Close the run with error
            try:
                langsmith_client.update_run(
                    run_id=run_id,
                    outputs={"error": str(e)},
                    error=str(e),
                    end_time=_now(),
                    extra={
                        "metadata": {
                            "tool_name": name,
                            "execution_time_seconds": round(execution_time, 3),
                            "status": "error",
                        },
                        "usage_metadata": {
                            "input_tokens": input_tokens,
                            "output_tokens": 0,
                            "total_tokens": input_tokens,
                        },
                    },
                )
            except Exception as log_err:
                logger.warning(f"LangSmith update_run (error) failed: {log_err}")

            raise

    return wrapper

# =============================================================================
# TOOL DEFINITIONS
# =============================================================================

TOOLS = [
    types.Tool(
        name="analyze_file",
        description="Parse single Python file using ArchitectureVisitor. Extracts classes, methods, attributes with AST.",
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to Python file"},
            },
            "required": ["file_path"],
        },
    ),
    types.Tool(
        name="analyze_project",
        description="Full project analysis using ProjectAnalyzer: scans tree and parses all Python files with AST.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Project root directory"},
            },
            "required": ["path"],
        },
    ),
    types.Tool(
        name="extract_relationships",
        description="Extract class relationships using RelationshipExtractor. Returns inheritance/composition + Mermaid diagram.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Project root directory"},
                "focus_classes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: filter diagram to specific classes",
                },
            },
            "required": ["path"],
        },
    ),
    types.Tool(
        name="get_core_classes",
        description="Find most connected classes using RelationshipExtractor.get_core_classes() - architectural hubs.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Project root directory"},
                "min_connections": {
                    "type": "integer",
                    "description": "Minimum relationship count (default: 2)",
                },
            },
            "required": ["path"],
        },
    ),
    types.Tool(
        name="find_entry_points",
        description="Identify main application entry points (manage.py, settings.py, etc). Fast discovery without AST parsing.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Project root directory"},
            },
            "required": ["path"],
        },
    ),
    types.Tool(
        name="list_modules",
        description="List Python modules with basic stats (LOC, class count) using fast regex. No AST parsing.",
        inputSchema={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Directory path"},
                "pattern": {"type": "string", "description": "Glob pattern (default: **/*.py)"},
                "exclude_tests": {"type": "boolean", "description": "Skip test files (default: true)"},
                "exclude_private": {"type": "boolean", "description": "Skip __pycache__ (default: true)"},
            },
            "required": ["path"],
        },
    ),
    types.Tool(
        name="get_file_metadata",
        description="Get file metadata (size, mtime, hash, imports) without full AST parsing. Fast pre-flight check.",
        inputSchema={
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Path to Python file"},
                "include_imports": {"type": "boolean", "description": "Extract imports via regex (default: true)"},
            },
            "required": ["file_path"],
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    """Return available tools."""
    return TOOLS


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def _validate_path(path: str, must_be_dir: bool = False, must_be_file: bool = False) -> Path:
    """Validate and resolve a path."""
    resolved = Path(path).resolve()
    if not resolved.exists():
        raise ValueError(f"Path does not exist: {path}")
    if must_be_dir and not resolved.is_dir():
        raise ValueError(f"Path is not a directory: {path}")
    if must_be_file and not resolved.is_file():
        raise ValueError(f"Path is not a file: {path}")
    return resolved


def _prune(obj):
    """Recursively remove None, empty lists, empty dicts, empty strings."""
    if isinstance(obj, dict):
        return {k: _prune(v) for k, v in obj.items()
                if v is not None and v != [] and v != {} and v != ""}
    elif isinstance(obj, list):
        return [_prune(item) for item in obj]
    return obj


def _json_response(data: Any) -> list[types.TextContent]:
    """Create compact JSON response — prunes empty values, no indentation."""
    cleaned = _prune(data)
    return [types.TextContent(type="text", text=json.dumps(cleaned, separators=(',', ':'), default=str))]


def _error_response(error: str) -> list[types.TextContent]:
    """Create error response."""
    return [types.TextContent(type="text", text=json.dumps({"error": error}, separators=(',', ':')))]


async def _run_sync(func, *args, **kwargs):
    """Run synchronous function in thread pool to avoid blocking."""
    return await asyncio.to_thread(func, *args, **kwargs)


# =============================================================================
# SMART CACHING — auto-invalidates when source files change
# =============================================================================

class _SmartCache:
    """
    TTL + content-hash cache for expensive tool results.
    Invalidates when:
      - Any .py file is added/removed/modified (project-level hash changes)
      - TTL expires (default 5 minutes)
    """

    def __init__(self, ttl_seconds: int = 300):
        self.ttl = ttl_seconds
        self._store: dict[str, dict] = {}  # key -> {"hash": str, "result": Any, "ts": float}

    @staticmethod
    def _project_hash(path: str) -> str:
        """Fast hash of all .py file paths + mtimes. ~2 ms for 50 files."""
        root = Path(path).resolve()
        parts = []
        for py in sorted(root.rglob("*.py")):
            try:
                parts.append(f"{py}:{py.stat().st_mtime_ns}")
            except OSError:
                continue
        return hashlib.md5("|".join(parts).encode()).hexdigest()

    @staticmethod
    def _file_hash(path: str) -> str:
        """Fast hash for a single file (mtime + size)."""
        p = Path(path)
        st = p.stat()
        return f"{st.st_mtime_ns}:{st.st_size}"

    def get(self, key: str, hash_val: str) -> Any | None:
        """Return cached result if hash matches and TTL is valid."""
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry["hash"] != hash_val:
            return None
        if (time.time() - entry["ts"]) > self.ttl:
            return None
        return entry["result"]

    def put(self, key: str, hash_val: str, result: Any):
        self._store[key] = {"hash": hash_val, "result": result, "ts": time.time()}

    def stats(self) -> dict:
        return {"entries": len(self._store), "keys": list(self._store.keys())}


_cache = _SmartCache(ttl_seconds=300)


def _slim_class(cls: dict) -> dict:
    """Compress a class dict from ArchitectureVisitor — first-line doc, compact attrs."""
    out = {"name": cls["name"]}
    if cls.get("bases"):
        out["bases"] = cls["bases"]
    desc = cls.get("description") or ""
    if desc:
        out["doc"] = desc.strip().split('\n')[0][:120]
    if cls.get("methods"):
        out["methods"] = [
            {"name": m["name"], "args": m.get("args", []), "returns": m.get("returns")}
            for m in cls["methods"]
        ]
    if cls.get("attributes"):
        out["attrs"] = [{"name": a["name"], "type": a.get("type", "?")} for a in cls["attributes"][:10]]
    return out


def _slim_func(fn: dict) -> dict:
    """Compress a function dict — drop docstrings entirely."""
    out = {"name": fn["name"], "args": fn.get("args", [])}
    if fn.get("returns"):
        out["returns"] = fn["returns"]
    return out


# =============================================================================
# TOOL HANDLERS - Thin wrappers around service functions
# =============================================================================

def _tool_analyze_file(file_path: Path) -> dict:
    """Wrapper for ArchitectureVisitor.visit() — cached per-file."""
    if file_path.suffix != ".py":
        raise ValueError(f"Not a Python file: {file_path}")

    key = f"analyze_file:{file_path}"
    h = _cache._file_hash(str(file_path))
    cached = _cache.get(key, h)
    if cached is not None:
        logger.info(f"CACHE HIT: {key}")
        return cached

    with open(file_path, "r", encoding="utf-8") as f:
        source = f.read()

    tree = ast.parse(source)
    visitor = ArchitectureVisitor()
    visitor.visit(tree)

    result = {
        "file": file_path.name,
        "classes": [_slim_class(c) for c in visitor.structure],
        "functions": [_slim_func(f) for f in visitor.global_functions],
    }
    _cache.put(key, h, result)
    return result


def _get_project_tree(path: str) -> dict:
    """Shared cached project analysis — used by multiple tools."""
    key = f"project_tree:{path}"
    h = _cache._project_hash(path)
    cached = _cache.get(key, h)
    if cached is not None:
        logger.info(f"CACHE HIT: {key}")
        return cached
    analyzer = ProjectAnalyzer(path)
    result = analyzer.analyze()
    _cache.put(key, h, result)
    return result


def _tool_analyze_project(path: str) -> dict:
    """Wrapper for ProjectAnalyzer.analyze() — cached."""
    return _get_project_tree(path)


def _tool_extract_relationships(path: str, focus_classes: list[str] | None) -> dict:
    """Wrapper for RelationshipExtractor operations — uses cached project tree."""
    tree = _get_project_tree(path)

    extractor = RelationshipExtractor()
    extractor.extract_from_json(tree)

    mermaid = extractor.to_mermaid(focus_on=focus_classes)

    return {
        "relationships": extractor.to_dict(),
        "mermaid_diagram": mermaid,
        "total_classes": len(extractor.classes),
    }


def _tool_get_core_classes(path: str, min_connections: int) -> dict:
    """Wrapper for RelationshipExtractor.get_core_classes() — uses cached project tree."""
    tree = _get_project_tree(path)

    extractor = RelationshipExtractor()
    extractor.extract_from_json(tree)

    core = extractor.get_core_classes(min_connections=min_connections)
    relationships = extractor.to_dict(filter_orphans=False)

    # Slim details: only relationships + top-3 method names, no attrs/descriptions
    details = {}
    for name in core:
        if name in relationships:
            r = relationships[name]
            details[name] = {
                "module": r["module"],
                "inherits": r.get("inherits", []),
                "uses": r.get("uses", []),
                "methods": r.get("methods", [])[:3],
            }

    return {
        "core_classes": core,
        "details": details,
    }


def _tool_find_entry_points(path: str) -> dict:
    """Wrapper for discovery_tools.find_entry_points() — cached."""
    key = f"find_entry_points:{path}"
    h = _cache._project_hash(path)
    cached = _cache.get(key, h)
    if cached is not None:
        logger.info(f"CACHE HIT: {key}")
        return cached
    result = find_entry_points(path)
    result.pop("success", None)
    result.pop("total_entry_points", None)
    _cache.put(key, h, result)
    return result


def _tool_list_modules(
    path: str,
    pattern: str,
    exclude_tests: bool,
    exclude_private: bool
) -> dict:
    """Wrapper for discovery_tools.list_modules() — cached."""
    key = f"list_modules:{path}:{pattern}:{exclude_tests}:{exclude_private}"
    h = _cache._project_hash(path)
    cached = _cache.get(key, h)
    if cached is not None:
        logger.info(f"CACHE HIT: {key}")
        return cached
    result = list_modules(
        path=path,
        pattern=pattern,
        exclude_tests=exclude_tests,
        exclude_private=exclude_private,
        include_stats=True
    )
    # Remove redundant fields to cut tokens ~40%
    result.pop("success", None)
    result.pop("path", None)  # caller already knows the path
    for m in result.get("modules", []):
        m.pop("name", None)   # derivable from path
        m.pop("size", None)   # lines is more useful
    _cache.put(key, h, result)
    return result


def _tool_get_file_metadata(file_path: Path, include_imports: bool) -> dict:
    """Wrapper for discovery_tools.get_file_metadata() — cached per-file."""
    key = f"get_file_metadata:{file_path}:{include_imports}"
    h = _cache._file_hash(str(file_path))
    cached = _cache.get(key, h)
    if cached is not None:
        logger.info(f"CACHE HIT: {key}")
        return cached
    result = get_file_metadata(str(file_path), include_imports=include_imports)
    result.pop("success", None)
    # Shorten path to just the file name
    if "path" in result:
        result["path"] = Path(result["path"]).name
    _cache.put(key, h, result)
    return result


# =============================================================================
# MAIN TOOL DISPATCHER
# =============================================================================


@server.call_tool()
@track_tool_call
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    """Dispatch tool calls to service wrappers with LangSmith tracking."""
    logger.info(f"Tool called: {name}")

    try:
        if name == "analyze_file":
            path = _validate_path(arguments["file_path"], must_be_file=True)
            result = await _run_sync(_tool_analyze_file, path)
            return _json_response(result)

        elif name == "analyze_project":
            path = _validate_path(arguments["path"], must_be_dir=True)
            result = await _run_sync(_tool_analyze_project, str(path))
            return _json_response(result)

        elif name == "extract_relationships":
            path = _validate_path(arguments["path"], must_be_dir=True)
            focus = arguments.get("focus_classes")
            result = await _run_sync(_tool_extract_relationships, str(path), focus)
            return _json_response(result)

        elif name == "get_core_classes":
            path = _validate_path(arguments["path"], must_be_dir=True)
            min_conn = arguments.get("min_connections", 2)
            result = await _run_sync(_tool_get_core_classes, str(path), min_conn)
            return _json_response(result)

        elif name == "find_entry_points":
            path = _validate_path(arguments["path"], must_be_dir=True)
            result = await _run_sync(_tool_find_entry_points, str(path))
            return _json_response(result)

        elif name == "list_modules":
            path = _validate_path(arguments["path"], must_be_dir=True)
            pattern = arguments.get("pattern", "**/*.py")
            exclude_tests = arguments.get("exclude_tests", True)
            exclude_private = arguments.get("exclude_private", True)
            result = await _run_sync(_tool_list_modules, str(path), pattern, exclude_tests, exclude_private)
            return _json_response(result)

        elif name == "get_file_metadata":
            path = _validate_path(arguments["file_path"], must_be_file=True)
            include_imports = arguments.get("include_imports", True)
            result = await _run_sync(_tool_get_file_metadata, path, include_imports)
            return _json_response(result)

        else:
            return _error_response(f"Unknown tool: {name}")

    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return _error_response(str(e))

    except Exception as e:
        logger.exception(f"Tool execution failed: {name}")
        return _error_response(f"Internal error: {str(e)}")


# =============================================================================
# OPTIONAL: RESOURCES AND PROMPTS
# =============================================================================


@server.list_resources()
async def list_resources() -> list[types.Resource]:
    """List available resources."""
    return []


@server.list_prompts()
async def list_prompts() -> list[types.Prompt]:
    """List available prompts."""
    return []


# =============================================================================
# ENTRY POINT
# =============================================================================


async def main():
    """Run the MCP server."""
    logger.info("Starting Code Analysis MCP Server...")
    async with stdio_server() as (read_stream, write_stream):
        init_options = InitializationOptions(
            server_name="code-analysis-mcp",
            server_version="1.0.0",
            capabilities=types.ServerCapabilities(
                tools=types.ToolsCapability(listChanged=False),
                prompts=types.PromptsCapability(listChanged=False),
                resources=types.ResourcesCapability(subscribe=False, listChanged=False),
                experimental={},
            ),
        )
        await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    asyncio.run(main())
