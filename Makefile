# Simple commands to avoid Docker hell
# Windows: Use `make <command>` in Git Bash or WSL
# Or just copy the commands directly

.PHONY: help up down restart logs shell test migrate createsuperuser clean index chat-test setup-pgvector

help:
	@echo "Available commands:"
	@echo "  make up              - Start all services"
	@echo "  make down            - Stop all services"
	@echo "  make restart         - Restart services"
	@echo "  make logs            - View logs"
	@echo "  make shell           - Django shell"
	@echo "  make test            - Run tests"
	@echo "  make migrate         - Run migrations"
	@echo "  make createsuperuser - Create admin user"
	@echo "  make clean           - Remove containers and volumes"
	@echo ""
	@echo "Chatbot commands:"
	@echo "  make setup-pgvector  - Enable pgvector extension"
	@echo "  make index           - Index codebase for chatbot"
	@echo "  make index-redis     - Index codebase using Redis"
	@echo "  make chat-test       - Test chatbot client"
	@echo ""
	@echo "MCP Server commands:"
	@echo "  make mcp-logs        - View MCP server logs"
	@echo "  make mcp-restart     - Restart MCP server"
	@echo "  make mcp-shell       - Connect to MCP server container"
	@echo "  make mcp-test        - Test MCP server with example client"

up:
	docker-compose up -d

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

shell:
	docker-compose exec web python manage.py shell_plus

test:
	docker-compose exec web pytest

migrate:
	docker-compose exec web python manage.py migrate

createsuperuser:
	docker-compose exec web python manage.py createsuperuser

clean:
	docker-compose down -v

# Chatbot commands
setup-pgvector:
	docker-compose exec db psql -U postgres -d ai_analyst -c "CREATE EXTENSION IF NOT EXISTS vector;"
	@echo "pgvector extension enabled"

index:
	docker-compose exec web python manage.py index_codebase
	@echo "Codebase indexed successfully"

index-redis:
	docker-compose exec web python manage.py index_codebase --use-redis
	@echo "Codebase indexed with Redis"

chat-test:
	python chatbot_client.py
# MCP Server commands
mcp-logs:
	docker logs -f ai_analyst_mcp

mcp-restart:
	docker-compose restart mcp
	@echo "MCP server restarted"

mcp-shell:
	docker exec -it ai_analyst_mcp /bin/bash

mcp-test:
	python mcp_client_example.py