# Simple commands to avoid Docker hell
# Windows: Use `make <command>` in Git Bash or WSL
# Or just copy the commands directly

.PHONY: help up down restart logs shell test migrate createsuperuser clean

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
