# ==================== Dockerfile para Nexus POS ====================
# Build simplificado sin uv para evitar problemas de editable install

FROM python:3.11-slim

# Instalar dependencias del sistema
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root
RUN useradd -m -u 1000 nexuspos && \
    mkdir -p /app/logs && \
    chown -R nexuspos:nexuspos /app

# Configurar directorio de trabajo
WORKDIR /app

# Copiar archivos de requisitos primero (mejor cache de Docker)
COPY requirements.txt ./

# Instalar dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código de la aplicación
COPY --chown=nexuspos:nexuspos . .

# Cambiar a usuario no-root
USER nexuspos

# Exponer puerto
EXPOSE 8000

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Comando por defecto
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
