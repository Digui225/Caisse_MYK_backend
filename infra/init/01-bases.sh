#!/bin/bash
set -e

# Ce script est exécuté automatiquement au 1er démarrage du conteneur postgres

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
  -- 1. Base et rôle pour le PMS Hôtel
  CREATE ROLE hotel_paix WITH LOGIN PASSWORD '${HOTEL_DB_PASSWORD:-hotel_secret}';
  CREATE DATABASE hotel_paix OWNER hotel_paix;

  -- 2. Base et rôle pour la Caisse Restaurant
  CREATE ROLE caisse WITH LOGIN PASSWORD '${CAISSE_DB_PASSWORD:-caisse_secret}';
  CREATE DATABASE caisse OWNER caisse;

  -- 3. Cloisonnement strict : révocation de tous les droits croisés
  REVOKE CONNECT ON DATABASE caisse     FROM PUBLIC, hotel_paix;
  REVOKE CONNECT ON DATABASE hotel_paix FROM PUBLIC, caisse;

  GRANT CONNECT ON DATABASE caisse     TO caisse;
  GRANT CONNECT ON DATABASE hotel_paix TO hotel_paix;
EOSQL

echo "✅ Bases 'hotel_paix' et 'caisse' initialisées avec succès et hermétiquement cloisonnées."
