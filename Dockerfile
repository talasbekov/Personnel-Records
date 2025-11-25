# Dockerfile
FROM python:3.12-bookworm

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements/ /app/requirements/
RUN pip install --no-cache-dir -r requirements/base.txt
RUN pip install --no-cache-dir -r requirements/development.txt

# Copy project
COPY . /app/
COPY docker/entrypoint.sh /app/docker/entrypoint.sh

RUN chmod +x /app/docker/entrypoint.sh
# Collect static files
RUN python manage.py collectstatic --noinput

CMD ["gunicorn", "organization_management.config.wsgi:application", "--bind", "0.0.0.0:8000"]
ENTRYPOINT ["/app/docker/entrypoint.sh"]
