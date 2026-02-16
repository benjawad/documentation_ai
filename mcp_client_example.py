#!/usr/bin/env python3
"""
Example MCP Client for AI Documentation Services

This script demonstrates how to connect to and use the MCP server
to index codebases, chat with code, and analyze projects.

Usage:
    python mcp_client_example.py
"""

import asyncio
import json
from typing import Any, Dict
from pathlib import Path

try:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
except ImportError:
    print("ERROR: MCP client library not installed.")
    print("Install with: pip install 'mcp[cli]'")
    exit(1)


class MCPClient:
    """Client for interacting with the AI Documentation MCP server"""
    
    def __init__(self, server_script_path: str):
        """
        Initialize MCP client
        
        Args:
            server_script_path: Path to the MCP server script
        """
        self.server_script_path = server_script_path
        self.session = None
    
    async def connect(self):
        """Connect to the MCP server"""
        server_params = StdioServerParameters(
            command="python",
            args=[self.server_script_path],
            env=None,
        )
        
        # For Docker, use docker exec instead:
        # server_params = StdioServerParameters(
        #     command="docker",
        #     args=["exec", "-i", "ai_analyst_mcp", "python", "/app/core/services/small_mcp.py"],
        #     env=None,
        # )
        
        self.stdio_transport = await stdio_client(server_params)
        self.session = ClientSession(*self.stdio_transport)
        await self.session.__aenter__()
        
        # Initialize the connection
        await self.session.initialize()
        
        print("✅ Connected to MCP server")
    
    async def disconnect(self):
        """Disconnect from the MCP server"""
        if self.session:
            await self.session.__aexit__(None, None, None)
        print("👋 Disconnected from MCP server")
    
    async def list_tools(self):
        """List available tools"""
        tools = await self.session.list_tools()
        print(f"\n📋 Available tools ({len(tools.tools)}):")
        for tool in tools.tools:
            print(f"  • {tool.name}: {tool.description}")
        return tools.tools
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call a tool on the MCP server
        
        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments as a dictionary
        
        Returns:
            Tool response
        """
        print(f"\n🔧 Calling tool: {tool_name}")
        print(f"   Arguments: {json.dumps(arguments, indent=2)}")
        
        result = await self.session.call_tool(tool_name, arguments)
        
        # Parse and display result
        if result.content:
            for content in result.content:
                if hasattr(content, 'text'):
                    try:
                        parsed = json.loads(content.text)
                        print(f"\n✨ Result:")
                        print(json.dumps(parsed, indent=2))
                        return parsed
                    except json.JSONDecodeError:
                        print(f"\n✨ Result:\n{content.text}")
                        return content.text
        
        return None


async def example_workflow():
    """Example workflow demonstrating MCP capabilities"""
    
    # For local development (running the server directly):
    # client = MCPClient("src/core/services/small_mcp.py")
    
    # For Docker (requires docker-py or subprocess):
    print("=" * 60)
    print("AI Documentation MCP Client Example")
    print("=" * 60)
    
    # Note: For Docker, you'll need to use docker exec
    # This example assumes local development
    script_path = "src/core/services/small_mcp.py"
    
    if not Path(script_path).exists():
        print(f"❌ Error: MCP server script not found at {script_path}")
        print("Please update the path or run from the correct directory.")
        return
    
    client = MCPClient(script_path)
    
    try:
        # Connect to server
        await client.connect()
        
        # List available tools
        await client.list_tools()
        
        # Example 1: Index a codebase
        print("\n" + "=" * 60)
        print("Example 1: Index Codebase")
        print("=" * 60)
        
        index_result = await client.call_tool(
            "index_codebase",
            {
                "path": "/path/to/your/project",  # Update this path
                "use_postgres": True
            }
        )
        
        # Example 2: Chat with the codebase
        print("\n" + "=" * 60)
        print("Example 2: Chat with Codebase")
        print("=" * 60)
        
        chat_result = await client.call_tool(
            "chat_with_codebase",
            {
                "question": "What are the main components of this project?",
                "use_postgres": True
            }
        )
        
        # Save session ID for follow-up questions
        session_id = chat_result.get("session_id") if chat_result else None
        
        if session_id:
            # Follow-up question in the same session
            print("\n📝 Asking follow-up question...")
            followup_result = await client.call_tool(
                "chat_with_codebase",
                {
                    "question": "How do they interact with each other?",
                    "session_id": session_id,
                    "use_postgres": True
                }
            )
        
        # Example 3: Analyze project structure
        print("\n" + "=" * 60)
        print("Example 3: Analyze Project")
        print("=" * 60)
        
        analysis_result = await client.call_tool(
            "analyze_project",
            {
                "path": "/path/to/your/project",  # Update this path
                "max_depth": 5
            }
        )
        
        # Example 4: Search for files
        print("\n" + "=" * 60)
        print("Example 4: Search Codebase")
        print("=" * 60)
        
        search_result = await client.call_tool(
            "search_codebase",
            {
                "root_path": "/path/to/your/project",  # Update this path
                "pattern": "*.py",
                "max_depth": 5
            }
        )
        
        # Example 5: Get file content
        if search_result and search_result.get("matches"):
            first_file = search_result["matches"][0]["path"]
            
            print("\n" + "=" * 60)
            print("Example 5: Get File Content")
            print("=" * 60)
            
            file_result = await client.call_tool(
                "get_file_content",
                {
                    "path": first_file
                }
            )
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Disconnect
        await client.disconnect()


async def docker_example():
    """Example for Docker deployment"""
    
    print("=" * 60)
    print("Docker MCP Client Example")
    print("=" * 60)
    print("\nTo use MCP with Docker, you can:")
    print("\n1. Use docker exec to connect to the running container:")
    print("   docker exec -i ai_analyst_mcp python /app/core/services/small_mcp.py")
    
    print("\n2. Or configure the client to use docker exec:")
    print("""
    from mcp.client.stdio import stdio_client
    from mcp import StdioServerParameters
    
    server_params = StdioServerParameters(
        command="docker",
        args=["exec", "-i", "ai_analyst_mcp", "python", "/app/core/services/small_mcp.py"],
        env=None,
    )
    
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            # Use session...
    """)


if __name__ == "__main__":
    print("Choose example:")
    print("1. Local workflow example")
    print("2. Docker usage information")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    if choice == "1":
        asyncio.run(example_workflow())
    elif choice == "2":
        asyncio.run(docker_example())
    else:
        print("Invalid choice")
