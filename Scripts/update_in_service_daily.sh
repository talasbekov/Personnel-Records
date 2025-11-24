#!/bin/bash
# Скрипт для ежедневного обновления статусов "В строю"
# Добавить в crontab: 0 0 * * * /path/to/update_in_service_daily.sh

cd "/home/erda/Документы/Personnel Records/Personnel-Records"

# Если используется Docker
if command -v docker-compose &> /dev/null; then
    docker-compose exec -T web python manage.py update_in_service_dates
else
    # Если без Docker
    python manage.py update_in_service_dates
fi
