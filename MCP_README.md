# Model Context Protocol (MCP) Server Documentation

## Overview

This MCP server exposes AI-powered documentation and code analysis services through the Model Context Protocol. It provides tools for indexing codebases, chatting with code using RAG, and analyzing project architecture.

## Available Tools

### 1. `index_codebase`
Index a codebase directory for semantic search and retrieval-augmented generation (RAG).

**Parameters:**
- `path` (string, required): Absolute path to the codebase directory to index
- `use_postgres` (boolean, optional): Use PostgreSQL vector store (true) or Redis (false). Default: true

**Returns:**
- Indexing statistics including number of files processed, documents created, and tokens processed

**Example:**
```json
{
  "path": "/path/to/your/project",
  "use_postgres": true
}
```

### 2. `chat_with_codebase`
Ask questions about the indexed codebase using RAG. Creates or continues a chat session.

**Parameters:**
- `question` (string, required): The question to ask about the codebase
- `session_id` (string, optional): Chat session ID to continue a conversation. If not provided, creates a new session
- `use_postgres` (boolean, optional): Use PostgreSQL vector store (true) or Redis (false). Default: true

**Returns:**
- Answer to the question with relevant source code snippets and references

**Example:**
```json
{
  "question": "How does the authentication system work?",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "use_postgres": true
}
```

### 3. `analyze_project`
Analyze project architecture including file structure, classes, functions, and relationships.

**Parameters:**
- `path` (string, required): Absolute path to the project directory to analyze
- `max_depth` (integer, optional): Maximum directory depth to traverse. Default: 10

**Returns:**
- Detailed project structure with AST analysis for Python files

**Example:**
```json
{
  "path": "/path/to/your/project",
  "max_depth": 10
}
```

### 4. `get_file_content`
Read the content of a specific file from the codebase.

**Parameters:**
- `path` (string, required): Absolute path to the file to read

**Returns:**
- File content with metadata (size, path)

**Example:**
```json
{
  "path": "/path/to/your/file.py"
}
```

### 5. `search_codebase`
Search for files matching a pattern in the codebase directory tree.

**Parameters:**
- `root_path` (string, required): Root directory path to search in
- `pattern` (string, required): File name pattern to search for (e.g., '*.py', 'test_*.py')
- `max_depth` (integer, optional): Maximum directory depth. Default: 10

**Returns:**
- List of matching files with their paths and metadata

**Example:**
```json
{
  "root_path": "/path/to/your/project",
  "pattern": "*.py",
  "max_depth": 10
}
```

## Docker Setup

### Starting the MCP Server

The MCP server runs as a Docker container alongside your other services:

```bash
# Build and start all services including MCP
docker-compose up -d

# View MCP server logs
docker logs -f ai_analyst_mcp

# Restart MCP server only
docker-compose restart mcp
```

### Connecting to the MCP Server

The MCP server uses stdio for communication. To interact with it:

```bash
# Attach to the MCP container
docker exec -it ai_analyst_mcp python /app/core/services/small_mcp.py
```

Or use the MCP client library to connect programmatically.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      MCP Server                              │
│  (Model Context Protocol - stdio communication)              │
└─────────────────────────────────────────────────────────────┘
                            │
                            ├── Tool: index_codebase
                            │   └── CodebaseIndexer
                            │       ├── LlamaIndex
                            │       └── Vector Store (PgVector/Redis)
                            │
                            ├── Tool: chat_with_codebase
                            │   └── ChatbotService
                            │       ├── LangChain
                            │       └── RAG Pipeline
                            │
                            ├── Tool: analyze_project
                            │   └── ProjectAnalyzer
                            │       ├── FileSystemVisitor
                            │       └── ArchitectureVisitor (AST)
                            │
                            ├── Tool: get_file_content
                            │   └── File I/O
                            │
                            └── Tool: search_codebase
                                └── FileSystemVisitor
```

## Configuration

The MCP server uses the same environment variables as the main Django application:

- `OPENAI_API_KEY`: OpenAI API key for LLM operations
- `DATABASE_URL`: PostgreSQL connection string (for pgvector)
- `REDIS_URL`: Redis connection string (for Redis vector store)

See `.env` file for full configuration.

## Dependencies

The MCP server requires the following Python packages:
- `mcp>=0.9.0`: Model Context Protocol SDK
- `langchain`: For chat and RAG
- `llama-index-core`: For indexing
- `pgvector`: For PostgreSQL vector storage
- `redis`: For Redis vector storage

All dependencies are installed in the Docker image.

## Usage Examples

See [mcp_client_example.py](mcp_client_example.py) for a complete Python client example.

## LangSmith Integration for Token Tracking

The MCP server includes built-in LangSmith integration for comprehensive observability and token usage tracking.

### Features

- **Tool Call Tracking**: Monitor every MCP tool invocation
- **Performance Metrics**: Track execution time for each tool
- **Token Usage**: Automatic token counting for AI operations
- **Error Monitoring**: Capture and log errors with full context
- **Cost Analysis**: Track API costs over time

### Setup

1. **Get a LangSmith API Key**
   - Sign up at [LangSmith](https://smith.langchain.com/)
   - Create an API key in Settings

2. **Configure Environment Variables**
   
   Add to your `.env` file:
   ```bash
   # LangSmith Configuration
   LANGSMITH_API_KEY=your-api-key-here
   LANGSMITH_PROJECT=code-analysis-mcp
   LANGCHAIN_TRACING_V2=true
   LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
   ```

3. **Restart the MCP Server**
   ```bash
   docker-compose restart mcp
   ```

### Viewing Traces

1. Visit [LangSmith Dashboard](https://smith.langchain.com/)
2. Navigate to your project (`code-analysis-mcp` by default)
3. View traces, metrics, and analytics

### Tracked Metrics

Each tool call records:
- **Tool name** and arguments
- **Execution time** (in seconds)
- **Input/Output data** (truncated for large responses)
- **Success/error status**
- **Timestamp** for temporal analysis

### Optional Usage

LangSmith tracking is **optional**. If not configured:
- MCP server works normally without tracking
- Only local logging is performed
- No external API calls are made

### Cost Considerations

- LangSmith free tier includes 5,000 traces/month
- Tool calls are lightweight (minimal data transfer)
- Token usage tracking is most valuable for LLM-heavy operations

## Troubleshooting

### MCP Server Not Starting

Check the logs:
```bash
docker logs ai_analyst_mcp
```

Common issues:
- Database not ready: The server waits for PostgreSQL and Redis
- Missing environment variables: Check `.env` file
- Import errors: Rebuild the Docker image with `docker-compose build mcp`

### Tools Not Working

1. **index_codebase fails**: Ensure the path is accessible from within the Docker container
2. **chat_with_codebase returns no results**: Index the codebase first
3. **Database connection errors**: Check PostgreSQL is running and migrations are applied

### Debugging

Enable debug logging:
```bash
# In docker-compose.yml, add to mcp service:
environment:
  - LOG_LEVEL=DEBUG
```

## Development

To modify the MCP server:

1. Edit [small_mcp.py](../src/core/services/small_mcp.py)
2. Rebuild the Docker image: `docker-compose build mcp`
3. Restart the service: `docker-compose restart mcp`

## Security Considerations

- The MCP server has full access to the codebase
- Ensure proper access controls on the Docker socket
- Use environment variables for sensitive credentials
- Consider network isolation for production deployments

## License

Same as the main project.
