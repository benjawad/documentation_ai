#!/usr/bin/env python3
"""Quick LangSmith connectivity check from inside Docker"""
import os, sys, uuid
from datetime import datetime, timezone

sys.path.insert(0, "/app/core/services")

# 1. Env vars
api_key = os.getenv("LANGSMITH_API_KEY", "")
project = os.getenv("LANGSMITH_PROJECT", "code-analysis-mcp")
tracing = os.getenv("LANGCHAIN_TRACING_V2", "")

print("ENV CHECK:")
print(f"  LANGSMITH_API_KEY = {api_key[:30]}...")
print(f"  LANGSMITH_PROJECT = {project}")
print(f"  LANGCHAIN_TRACING_V2 = {tracing}")
print()

if not api_key:
    print("ERROR: LANGSMITH_API_KEY not set")
    sys.exit(1)

# 2. Import
from langsmith import Client
import langsmith
print(f"langsmith {langsmith.__version__} imported OK")

# 3. Create test run
client = Client(api_key=api_key)
rid = uuid.uuid4()
now = datetime.now(timezone.utc)

print(f"\nCreating test run {rid}...")
client.create_run(
    name="mcp_tool_test_from_container",
    run_type="tool",
    id=rid,
    project_name=project,
    inputs={"tool": "test", "arguments": {"path": "/app"}},
    start_time=now,
)
client.update_run(
    run_id=rid,
    outputs={"result": "test OK"},
    end_time=now,
)
print(f"DONE. Check LangSmith dashboard -> project: {project}")
print("https://smith.langchain.com/")
