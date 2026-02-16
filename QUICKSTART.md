# Quick Start Guide - AI Chatbot

This guide will help you get the chatbot up and running in minutes.

## Prerequisites

- Python 3.9+
- PostgreSQL with pgvector extension
- Redis
- OpenAI API key

## Step-by-Step Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and set your OpenAI API key
# OPENAI_API_KEY=sk-your-actual-key-here
```

### 3. Setup Database

```bash
# Run Django migrations
python src/manage.py makemigrations
python src/manage.py migrate

# Enable pgvector in PostgreSQL
# Connect to your database and run:
# CREATE EXTENSION IF NOT EXISTS vector;
```

You can do this via Docker:

```bash
docker-compose exec db psql -U postgres -d ai_analyst -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### 4. Index Your Codebase

```bash
# Index using PostgreSQL (recommended)
python src/manage.py index_codebase

# Or use Redis
python src/manage.py index_codebase --use-redis
```

This will:
- Scan your entire project
- Create embeddings for all Python and documentation files
- Store them in the vector database
- Take 2-10 minutes depending on codebase size

### 5. Start the Server

```bash
python src/manage.py runserver
```

## Test the Chatbot

### Using cURL

```bash
# Create a chat session
curl -X POST http://localhost:8000/api/sessions/ \
  -H "Content-Type: application/json" \
  -d '{"title": "My First Chat"}'

# Chat (replace SESSION_ID with the ID from above)
curl -X POST http://localhost:8000/api/chat/ \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What does this project do?",
    "session_id": "SESSION_ID"
  }'
```

### Using Python

```python
import requests

# Create session
session_response = requests.post(
    'http://localhost:8000/api/sessions/',
    json={'title': 'Code Questions'}
)
session_id = session_response.json()['id']

# Ask a question
chat_response = requests.post(
    'http://localhost:8000/api/chat/',
    json={
        'message': 'Explain the architecture of this application',
        'session_id': session_id
    }
)

answer = chat_response.json()
print(f"Answer: {answer['message']}")
print(f"\nSources:")
for source in answer['sources']:
    print(f"  - {source['file_path']}")
```

### Using Postman

1. **Create Session**
   - Method: POST
   - URL: `http://localhost:8000/api/sessions/`
   - Body (JSON):
     ```json
     {"title": "My Chat"}
     ```

2. **Send Message**
   - Method: POST
   - URL: `http://localhost:8000/api/chat/`
   - Body (JSON):
     ```json
     {
       "message": "How does the chat service work?",
       "session_id": "paste-session-id-here"
     }
     ```

## Common Commands

### Re-index Codebase
```bash
python src/manage.py index_codebase
```

### Check Indexing Status
```bash
curl http://localhost:8000/api/index/
```

### List All Sessions
```bash
curl http://localhost:8000/api/sessions/
```

### Search Codebase
```bash
curl -X POST http://localhost:8000/api/search/ \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication", "top_k": 5}'
```

## Troubleshooting

### "OpenAI API key not found"
- Make sure `.env` file exists in project root
- Set `OPENAI_API_KEY=sk-your-actual-key`
- Restart the server

### "pgvector extension not found"
```sql
-- Connect to database and run:
CREATE EXTENSION IF NOT EXISTS vector;
```

### "No index found"
```bash
# Run indexing command:
python src/manage.py index_codebase
```

### Indexing is slow
- This is normal for large codebases
- First run takes longest (creating embeddings)
- Subsequent updates are faster

## What to Ask the Chatbot

Good questions to try:

- "What is the overall architecture of this application?"
- "How does the authentication system work?"
- "Explain the database models"
- "Show me how to add a new API endpoint"
- "What services are available in this project?"
- "How is the chat service implemented?"
- "What are the main dependencies?"

## Next Steps

- Check out [CHATBOT_README.md](CHATBOT_README.md) for full API documentation
- Customize prompts in `core/services/chat_service.py`
- Adjust chunking in `core/llm_factory/factory.py`
- Add authentication to API endpoints
- Build a web UI

## Need Help?

- Check logs: Docker logs or console output
- Verify all environment variables are set
- Ensure PostgreSQL and Redis are running
- Test API with simple curl commands first
