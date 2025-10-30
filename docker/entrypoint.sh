#!/bin/sh

# Wait for the database to be ready
until PGPASSWORD=$POSTGRES_PASSWORD psql -h "$POSTGRES_HOST" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c '\q'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

>&2 echo "Postgres is up - executing command"

# Set Django settings to production
export DJANGO_SETTINGS_MODULE=organization_management.config.settings.production

# Apply database migrations
python manage.py migrate

# Start server
exec "$@"
