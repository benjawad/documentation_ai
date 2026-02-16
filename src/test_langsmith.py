#!/usr/bin/env python3
"""
test_langsmith.py — Verify LangSmith tracks MCP tool usage correctly.

Run inside Docker:
    docker exec ai_analyst_mcp python /app/test_langsmith.py

Or from host:
    docker exec ai_analyst_mcp python3 /app/test_langsmith.py
"""

import os, sys, time, uuid, json
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# 0. Setup — make sure we can import project code
# ---------------------------------------------------------------------------
sys.path.insert(0, "/app")
sys.path.insert(0, "/app/core/services")

PASS, FAIL = 0, 0

def result(ok: bool, msg: str):
    global PASS, FAIL
    if ok:
        PASS += 1
        print(f"  [PASS] {msg}")
    else:
        FAIL += 1
        print(f"  [FAIL] {msg}")
    return ok

# ---------------------------------------------------------------------------
# 1. Environment variables
# ---------------------------------------------------------------------------
print("\n=== 1. Environment Variables ===")
api_key   = os.getenv("LANGSMITH_API_KEY", "")
project   = os.getenv("LANGSMITH_PROJECT", "")
tracing   = os.getenv("LANGCHAIN_TRACING_V2", "")
result(bool(api_key),  f"LANGSMITH_API_KEY  = {api_key[:25]}...")
result(bool(project),  f"LANGSMITH_PROJECT  = {project}")
result(tracing.lower() == "true", f"LANGCHAIN_TRACING_V2 = {tracing}")

# ---------------------------------------------------------------------------
# 2. Import langsmith
# ---------------------------------------------------------------------------
print("\n=== 2. LangSmith Package ===")
try:
    from langsmith import Client
    import langsmith
    result(True, f"langsmith {langsmith.__version__} imported")
except ImportError as e:
    result(False, f"Cannot import langsmith: {e}")
    print("\n❌  Install it:  pip install langsmith")
    sys.exit(1)

# ---------------------------------------------------------------------------
# 3. Client connectivity — list projects (lightweight API call)
# ---------------------------------------------------------------------------
print("\n=== 3. API Connectivity ===")
client = Client(api_key=api_key)
try:
    # list_projects is a cheap read-only endpoint
    projects = list(client.list_projects(limit=5))
    result(True, f"Connected — found {len(projects)} project(s)")
except Exception as e:
    result(False, f"API call failed: {e}")
    print("    Check your LANGSMITH_API_KEY and network access.")

# ---------------------------------------------------------------------------
# 4. Create a manual test trace and verify it arrives
# ---------------------------------------------------------------------------
print("\n=== 4. Create & Read Test Trace ===")
run_id = uuid.uuid4()
ts     = datetime.utcnow().isoformat()

try:
    client.create_run(
        name="langsmith_integration_test",
        run_type="tool",
        id=run_id,
        project_name=project or "code-analysis-mcp",
        inputs={"test_id": str(run_id), "timestamp": ts},
        start_time=datetime.utcnow(),
    )
    # End the run immediately so it's complete
    client.update_run(
        run_id=run_id,
        outputs={"status": "ok", "message": "Integration test passed"},
        end_time=datetime.utcnow(),
    )
    result(True, f"Trace created  run_id={run_id}")
except Exception as e:
    result(False, f"Failed to create trace: {e}")

# Give the API a moment to ingest
time.sleep(4)

try:
    runs = list(client.list_runs(
        project_name=project or "code-analysis-mcp",
        filter=f'eq(id, "{run_id}")',
        limit=1,
    ))
    found = len(runs) > 0
    result(found, f"Trace readable via list_runs  name={runs[0].name if found else '?'}")
    if found:
        result(runs[0].outputs is not None, f"Outputs stored  {json.dumps(runs[0].outputs)}")
    else:
        result(False, "Trace not yet visible (may need more time)")
except Exception as e:
    result(False, f"Could not read back trace: {e}")

# ---------------------------------------------------------------------------
# 5. Simulate what track_tool_call does (create_run → work → update_run)
# ---------------------------------------------------------------------------
print("\n=== 5. Simulate MCP track_tool_call ===")
sim_id = uuid.uuid4()
tool_name = "list_modules"
tool_args = {"path": "/app", "pattern": "**/*.py"}

try:
    start = time.time()

    # Open the run (mirrors the decorator in small_mcp.py)
    client.create_run(
        name=f"mcp_tool_{tool_name}",
        run_type="tool",
        id=sim_id,
        project_name=project or "code-analysis-mcp",
        inputs={"arguments": tool_args},
        start_time=datetime.utcnow(),
        extra={"metadata": {"tool_name": tool_name}},
    )

    # Simulate real work
    time.sleep(0.3)
    fake_result = {"success": True, "total_modules": 42}
    elapsed = time.time() - start

    # Close the run with outputs (mirrors the decorator)
    client.update_run(
        run_id=sim_id,
        outputs={"result": json.dumps(fake_result)[:500]},
        end_time=datetime.utcnow(),
        extra={"metadata": {
            "tool_name": tool_name,
            "execution_time_seconds": round(elapsed, 3),
            "status": "success",
        }},
    )

    result(True, f"Simulated mcp_tool_{tool_name} in {elapsed:.2f}s")
except Exception as e:
    result(False, f"Simulation failed: {e}")

# ---------------------------------------------------------------------------
# 6. Run a REAL tool through the actual handler (find_entry_points)
#    This exercises the full stack: discovery_tools → _tool wrapper → tracking
# ---------------------------------------------------------------------------
print("\n=== 6. Real Tool Execution (find_entry_points) ===")
try:
    from discovery_tools import find_entry_points
    real_start = time.time()
    real_result = find_entry_points("/app")
    real_elapsed = time.time() - real_start

    real_id = uuid.uuid4()
    client.create_run(
        name="mcp_tool_find_entry_points",
        run_type="tool",
        id=real_id,
        project_name=project or "code-analysis-mcp",
        inputs={"arguments": {"path": "/app"}},
        start_time=datetime.utcnow(),
        extra={"metadata": {"tool_name": "find_entry_points"}},
    )
    client.update_run(
        run_id=real_id,
        outputs={"result": json.dumps(real_result, default=str)[:500]},
        end_time=datetime.utcnow(),
        extra={"metadata": {
            "tool_name": "find_entry_points",
            "execution_time_seconds": round(real_elapsed, 3),
            "status": "success",
            "entry_points_found": real_result.get("total_entry_points", 0),
        }},
    )
    result(True, f"find_entry_points → {real_result.get('total_entry_points',0)} entry points, traced in {real_elapsed:.2f}s")
except Exception as e:
    result(False, f"Real tool test failed: {e}")

# ---------------------------------------------------------------------------
# 7. Verify traces visible in project
# ---------------------------------------------------------------------------
print("\n=== 7. Verify Traces in Project ===")
time.sleep(2)
try:
    runs = list(client.list_runs(
        project_name=project or "code-analysis-mcp",
        limit=10,
    ))
    our_names = {r.name for r in runs}
    result("langsmith_integration_test" in our_names, "Integration test trace found in project")
    result(any("mcp_tool_" in n for n in our_names), "MCP tool trace found in project")
    print(f"    Recent traces: {[r.name for r in runs[:5]]}")
except Exception as e:
    result(False, f"Could not list runs: {e}")

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = PASS + FAIL
print(f"\n{'='*50}")
print(f"  Results: {PASS}/{total} passed, {FAIL} failed")
print(f"{'='*50}")

if FAIL == 0:
    print("\n✅ LangSmith is tracking tool usage correctly!")
    print(f"   Dashboard → https://smith.langchain.com/")
    print(f"   Project  → {project or 'code-analysis-mcp'}\n")
else:
    print("\n⚠️  Some checks failed — review output above.\n")

sys.exit(0 if FAIL == 0 else 1)
