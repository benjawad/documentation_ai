# Quick Start

## Development
```bash
# 1. Copy environment file
cp .env.example .env

# 2. Build and start (installs dev dependencies)
docker-compose up --build -d

# 3. Run migrations
docker-compose exec web python manage.py migrate

# 4. Create admin user
docker-compose exec web python manage.py createsuperuser

# 5. Open http://localhost:8000/admin/
```

## Common Commands
```bash
# View logs
docker-compose logs -f web

# Django shell (IPython)
docker-compose exec web python manage.py shell_plus

# Run tests
docker-compose exec web pytest

# Format code
docker-compose exec web black .

# Stop everything
docker-compose down
```

## What's Included

**Essential Dev Tools:**
- ✅ pytest - Testing
- ✅ black - Auto-formatting
- ✅ Django Debug Toolbar - SQL/performance debugging
- ✅ IPython - Better shell
- ✅ django-extensions - Useful commands

**Production Ready:**
- ✅ Security headers (HTTPS, HSTS, etc.)
- ✅ Database connection pooling
- ✅ Redis authentication
- ✅ Health check endpoint
- ✅ Gunicorn for production
- ✅ Resource limits

## No Bullshit
- No over-engineering
- No unnecessary tools
- No pre-commit hooks (add if you want)
- No type checking (add mypy if you want)
- Just what you need to code and deploy

## When You're Ready for Production
```bash
# Use production compose file
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```
