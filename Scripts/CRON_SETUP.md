# Настройка автоматического обновления статусов "В строю"

## Описание
Каждый день система автоматически обновляет дату начала для всех активных статусов "В строю" на текущую дату.

## Быстрая установка (рекомендуется)

### Автоматическая установка cron задачи

Запустите скрипт автоматической установки:
```bash
cd "/home/erda/Документы/Personnel Records/Personnel-Records/Scripts"
./install_cron.sh
```

Скрипт автоматически:
- Проверит наличие существующей cron задачи
- Добавит новую задачу с запуском каждый день в 01:00
- Настроит логирование в `/var/log/update_in_service.log`
- Работает как с Docker, так и без него (автоопределение)

**Для серверов без интернета:** Скрипт не требует подключения к интернету и работает полностью offline.

---

## Ручная настройка

### 1. Ручной запуск (для теста)

**Для Docker:**
```bash
cd "/home/erda/Документы/Personnel Records/Personnel-Records"
docker-compose exec -T web python manage.py update_in_service_dates
```

**Без Docker:**
```bash
cd "/home/erda/Документы/Personnel Records/Personnel-Records"
python manage.py update_in_service_dates
```

### 2. Автоматический запуск через cron

Открыть crontab:
```bash
crontab -e
```

**Для Docker (рекомендуется):**
Добавить строку (запуск каждый день в 00:00):
```
0 0 * * * cd "/home/erda/Документы/Personnel Records/Personnel-Records" && docker-compose exec -T web python manage.py update_in_service_dates >> /tmp/in_service_update.log 2>&1
```

**Или использовать готовый скрипт (автоматически определяет Docker/без Docker):**
```
0 0 * * * /home/erda/Документы/Personnel\ Records/Personnel-Records/Scripts/update_in_service_daily.sh >> /tmp/in_service_update.log 2>&1
```

### 3. Проверка работы cron
```bash
tail -f /tmp/in_service_update.log
```

## Что делает команда
- Находит все активные статусы со типом "В строю"
- Обновляет их дату начала на текущую дату (одним SQL UPDATE запросом)
- Выводит количество обновленных записей
- Обходит валидацию модели для предотвращения конфликтов
