# Chatbot API Documentation

## Overview

This chatbot uses **LangChain** and **LlamaIndex** to provide intelligent responses based on your codebase context. It supports both PostgreSQL (pgvector) and Redis as vector stores.

## Features

- 🤖 **Conversational AI** - Context-aware chatbot using LangChain
- 📚 **Codebase Indexing** - Index your entire project using LlamaIndex
- 💾 **Vector Stores** - Support for PostgreSQL (pgvector) and Redis
- 📝 **Chat History** - Persistent conversation sessions
- 🔍 **Semantic Search** - Find relevant code snippets
- 🎯 **Source References** - Get file paths and context for answers

## API Endpoints

### Chat Endpoints

#### POST `/api/chat/`
Send a message to the chatbot.

**Request:**
```json
{
  "message": "How does the authentication work?",
  "session_id": "uuid-optional"
}
```

**Response:**
```json
{
  "session_id": "uuid",
  "message": "Authentication is handled by...",
  "sources": [
    {
      "file_path": "/path/to/file.py",
      "file_name": "file.py",
      "content_preview": "Code snippet..."
    }
  ],
  "message_id": "uuid"
}
```

#### GET `/api/sessions/`
List all chat sessions.

**Response:**
```json
[
  {
    "id": "uuid",
    "title": "Session title",
    "created_at": "2026-02-04T...",
    "updated_at": "2026-02-04T...",
    "message_count": 5
  }
]
```

#### POST `/api/sessions/`
Create a new chat session.

**Request:**
```json
{
  "title": "My conversation"
}
```

#### GET `/api/sessions/{id}/`
Get session details with all messages.

#### DELETE `/api/sessions/{id}/clear_history/`
Clear all messages in a session.

### Indexing Endpoints

#### POST `/api/index/`
Start indexing the codebase.

**Request:**
```json
{
  "root_path": "/path/to/project",
  "use_postgres": true
}
```

**Response:**
```json
{
  "job": {
    "id": "uuid",
    "status": "running",
    "total_files": 100,
    "processed_files": 45,
    "progress_percentage": 45.0
  },
  "result": {
    "status": "success",
    "total_files": 100,
    "processed_files": 100,
    "total_chunks": 350
  }
}
```

#### GET `/api/index/?job_id=uuid`
Get indexing job status.

### Search Endpoint

#### POST `/api/search/`
Search for similar code snippets.

**Request:**
```json
{
  "query": "user authentication",
  "top_k": 5
}
```

**Response:**
```json
[
  {
    "text": "Code content...",
    "metadata": {
      "file_path": "/path/to/file.py",
      "file_name": "file.py"
    },
    "score": 0.95
  }
]
```

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` and configure:

```bash
cp .env.example .env
```

Update the following variables:
- `OPENAI_API_KEY` - Your OpenAI API key
- `DB_*` - PostgreSQL connection details
- `REDIS_*` - Redis connection details

### 3. Run Migrations

```bash
python src/manage.py makemigrations
python src/manage.py migrate
```

### 4. Enable pgvector Extension (PostgreSQL)

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 5. Index Your Codebase

```bash
# Using PostgreSQL (default)
python src/manage.py index_codebase

# Using Redis
python src/manage.py index_codebase --use-redis

# Custom path
python src/manage.py index_codebase --path /path/to/your/project
```

### 6. Start the Server

```bash
python src/manage.py runserver
```

## Usage Examples

### Python Example

```python
import requests

# Create a new session
response = requests.post('http://localhost:8000/api/sessions/', json={
    'title': 'My Codebase Questions'
})
session_id = response.json()['id']

# Chat with the bot
response = requests.post('http://localhost:8000/api/chat/', json={
    'message': 'Explain the database models',
    'session_id': session_id
})

print(response.json()['message'])
print('Sources:', response.json()['sources'])
```

### JavaScript Example

```javascript
// Create session
const session = await fetch('http://localhost:8000/api/sessions/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: 'Code Questions' })
}).then(r => r.json());

// Chat
const response = await fetch('http://localhost:8000/api/chat/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
        message: 'How does the chat service work?',
        session_id: session.id
    })
}).then(r => r.json());

console.log(response.message);
```

## Architecture

### Components

1. **LLM Factory** (`core/llm_factory/factory.py`)
   - Creates LangChain and LlamaIndex LLM instances
   - Manages OpenAI embeddings
   - Configurable model parameters

2. **Vector Store Providers** (`core/llm_factory/providers.py`)
   - PostgreSQL (pgvector) integration
   - Redis vector store integration
   - LangChain and LlamaIndex compatible

3. **Indexing Service** (`core/services/indexing_service.py`)
   - Scans codebase using FileSystemVisitor
   - Creates embeddings with LlamaIndex
   - Stores in vector database
   - Tracks indexing jobs

4. **Chat Service** (`core/services/chat_service.py`)
   - Conversational AI with LangChain
   - RAG (Retrieval Augmented Generation)
   - Persistent chat history
   - Source attribution

5. **Django Models** (`core/models.py`)
   - ChatSession - Conversation sessions
   - ChatMessage - Individual messages
   - Document - Indexed code chunks
   - IndexingJob - Track indexing progress

## Configuration

### LLM Settings

Edit in `core/llm_factory/factory.py`:

```python
class LLMConfig:
    DEFAULT_LLM_MODEL = "gpt-4"
    DEFAULT_CHAT_MODEL = "gpt-3.5-turbo"
    DEFAULT_EMBEDDING_MODEL = "text-embedding-3-small"
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_CHUNK_SIZE = 1024
    DEFAULT_TOP_K = 5
```

### Vector Store Selection

Choose in API requests or use environment variable:

```python
# PostgreSQL (recommended for production)
indexer = CodebaseIndexer(use_postgres=True)

# Redis (faster for development)
indexer = CodebaseIndexer(use_postgres=False)
```

## Troubleshooting

### pgvector not enabled
```sql
-- Connect to your database and run:
CREATE EXTENSION vector;
```

### OpenAI API errors
- Verify `OPENAI_API_KEY` in `.env`
- Check API quota and billing
- Ensure internet connectivity

### Redis connection issues
- Verify Redis is running: `redis-cli ping`
- Check `REDIS_HOST` and `REDIS_PORT` in `.env`

### Indexing takes too long
- Reduce `DEFAULT_CHUNK_SIZE` in LLMConfig
- Index specific directories instead of entire project
- Use faster embedding model

## Performance Tips

1. **Use PostgreSQL for production** - Better for large codebases
2. **Adjust chunk size** - Larger chunks = fewer API calls but less precise
3. **Filter files** - Modify `FileSystemVisitor.IGNORED_DIRS` to skip unnecessary directories
4. **Use caching** - Enable Redis caching for frequently accessed data
5. **Batch indexing** - Index during off-peak hours

## Next Steps

- Add authentication to API endpoints
- Implement streaming responses for real-time chat
- Add support for multiple projects
- Create a web UI for the chatbot
- Add file upload for indexing specific files
- Implement fine-tuning for domain-specific knowledge
