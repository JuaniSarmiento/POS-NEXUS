# Nexus POS - Makefile para Desarrollo y Producción

.PHONY: help install dev prod migrate test lint clean

help: ## Mostrar este mensaje de ayuda
	@echo "Comandos disponibles:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ==================== DESARROLLO ====================

install: ## Instalar dependencias con uv
	uv pip install -e ".[dev]"

dev: ## Levantar servidor de desarrollo
	uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ==================== DOCKER ====================

build: ## Construir imagen Docker
	docker-compose build

up: ## Levantar todos los servicios
	docker-compose up -d

up-celery: ## Levantar con Celery (tareas de fondo)
	docker-compose --profile celery up -d

down: ## Detener todos los servicios
	docker-compose down

logs: ## Ver logs de todos los servicios
	docker-compose logs -f

logs-backend: ## Ver logs solo del backend
	docker-compose logs -f backend

restart: ## Reiniciar todos los servicios
	docker-compose restart

# ==================== BASE DE DATOS ====================

migrate: ## Ejecutar migraciones (auto-crear tablas)
	uv run python -c "from app.core.db import init_db; import asyncio; asyncio.run(init_db())"

db-shell: ## Conectar al shell de PostgreSQL
	docker-compose exec db psql -U nexuspos -d nexus_pos

# ==================== TESTING ====================

test: ## Ejecutar tests
	uv run pytest -v

test-cov: ## Ejecutar tests con coverage
	uv run pytest --cov=app --cov-report=html --cov-report=term-missing

test-all: ## Ejecutar suite completa con script maestro (Linux/Mac)
	bash run_all_tests.sh

test-all-win: ## Ejecutar suite completa con script maestro (Windows)
	run_all_tests.bat

# ==================== CALIDAD DE CÓDIGO ====================

lint: ## Verificar código con Ruff
	uv run ruff check .

lint-fix: ## Corregir errores automáticamente
	uv run ruff check --fix .

format: ## Formatear código
	uv run ruff format .

# ==================== LIMPIEZA ====================

clean: ## Limpiar archivos generados
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf .pytest_cache
	rm -rf htmlcov
	rm -rf dist

clean-docker: ## Limpiar volúmenes de Docker
	docker-compose down -v

# ==================== PRODUCCIÓN ====================

prod: ## Levantar en modo producción
	docker-compose up -d --build

prod-celery: ## Levantar producción con Celery
	docker-compose --profile celery up -d --build

health: ## Verificar salud de los servicios
	@curl -f http://localhost:8000/health || echo "Backend no disponible"
	@curl -f http://localhost:8080 || echo "Adminer no disponible"

# ==================== UTILIDADES ====================

shell: ## Abrir shell Python en el contenedor
	docker-compose exec backend uv run python

backend-shell: ## Abrir bash en el contenedor backend
	docker-compose exec backend bash

generate-key: ## Generar SECRET_KEY para producción
	@python -c "import secrets; print(secrets.token_hex(32))"
