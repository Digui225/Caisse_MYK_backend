#!/bin/sh
set -e

# Appliquer automatiquement les migrations Alembic avant de démarrer l'application
echo "Application des migrations Alembic..."
alembic upgrade head

echo "Démarrage du serveur Uvicorn..."
exec "$@"
