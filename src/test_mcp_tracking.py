#!/usr/bin/env python3
"""Test the actual MCP call_tool function with LangSmith tracking"""
import asyncio, sys, os, json

sys.path.insert(0, "/app")
sys.path.insert(0, "/app/core/services")

# Set Django-like environment so imports don't fail
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

async def main():
    # Import the actual MCP module
    import small_mcp
    
    print(f"LANGSMITH_AVAILABLE = {small_mcp.LANGSMITH_AVAILABLE}")
    print(f"langsmith_client = {small_mcp.langsmith_client}")
    print()
    
    # Call a real tool through the dispatcher
    print("Calling find_entry_points via call_tool...")
    result = await small_mcp.call_tool("find_entry_points", {"path": "/app"})
    
    # Parse and display result
    for item in result:
        data = json.loads(item.text)
        print(f"Result: {data.get('total_entry_points', '?')} entry points found")
    
    print()
    print("Calling list_modules via call_tool...")
    result = await small_mcp.call_tool("list_modules", {"path": "/app"})
    for item in result:
        data = json.loads(item.text)
        print(f"Result: {data.get('total_modules', '?')} modules found")
    
    print()
    print("DONE. Check LangSmith dashboard for:")
    print("  - mcp_tool_find_entry_points")
    print("  - mcp_tool_list_modules")
    print("  - mcp_server_startup")
    print("https://smith.langchain.com/")

asyncio.run(main())
