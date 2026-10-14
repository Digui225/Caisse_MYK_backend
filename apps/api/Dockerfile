FROM python:3.12-slim

WORKDIR /app

# Installation des dépendances système nécessaires
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copie des fichiers de configuration de dépendances
COPY pyproject.toml ./

# Installation des dépendances Python
RUN pip install --no-cache-dir --upgrade pip setuptools && \
    pip install --no-cache-dir .

# Copie du code source et d'Alembic
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini ./

COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

ENV PYTHONPATH=/app/src

EXPOSE 8001

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "caisse.main:app", "--host", "0.0.0.0", "--port", "8001"]
