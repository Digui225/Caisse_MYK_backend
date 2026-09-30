FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

FROM base AS build
COPY pyproject.toml ./
COPY src ./src
RUN pip install --prefix=/install .

FROM base AS runtime
RUN useradd --create-home --uid 1000 caisse
COPY --from=build /install /usr/local
COPY alembic.ini ./
COPY alembic ./alembic
COPY src ./src
USER caisse
EXPOSE 8000
CMD ["gunicorn", "caisse.main:app", "-k", "uvicorn.workers.UvicornWorker", \
     "-w", "2", "-b", "0.0.0.0:8000", "--access-logfile", "-"]

# Image de développement / CI : dépendances de test en plus, code monté en volume
FROM base AS dev
COPY pyproject.toml ./
COPY src ./src
RUN pip install -e ".[dev]"
COPY . .
CMD ["uvicorn", "caisse.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--app-dir", "src"]
