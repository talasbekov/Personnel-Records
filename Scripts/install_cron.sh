#!/bin/bash
# Скрипт для автоматической установки cron задачи
# Использование: ./install_cron.sh

set -e

# Определяем абсолютный путь к проекту
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SCRIPT_PATH="$SCRIPT_DIR/update_in_service_daily.sh"
LOG_PATH="/var/log/update_in_service.log"

echo "=========================================="
echo "Установка cron задачи для обновления статусов 'В строю'"
echo "=========================================="
echo ""
echo "Путь к проекту: $PROJECT_DIR"
echo "Путь к скрипту: $SCRIPT_PATH"
echo "Путь к логам: $LOG_PATH"
echo ""

# Проверяем, существует ли скрипт
if [ ! -f "$SCRIPT_PATH" ]; then
    echo "ОШИБКА: Скрипт $SCRIPT_PATH не найден!"
    exit 1
fi

# Делаем скрипт исполняемым
chmod +x "$SCRIPT_PATH"
echo "✓ Скрипт $SCRIPT_PATH сделан исполняемым"

# Формируем cron строку
# Запуск каждый день в 01:00 (можно изменить время)
CRON_TIME="0 1 * * *"
CRON_COMMAND="$SCRIPT_PATH >> $LOG_PATH 2>&1"
CRON_ENTRY="$CRON_TIME $CRON_COMMAND"

# Проверяем, существует ли уже такая запись в crontab
if crontab -l 2>/dev/null | grep -F "$SCRIPT_PATH" > /dev/null; then
    echo ""
    echo "⚠ Cron задача уже установлена:"
    crontab -l | grep -F "$SCRIPT_PATH"
    echo ""
    read -p "Хотите переустановить задачу? (y/n): " -n 1 -r
    echo ""

    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Установка отменена."
        exit 0
    fi

    # Удаляем старую запись
    (crontab -l 2>/dev/null | grep -vF "$SCRIPT_PATH") | crontab -
    echo "✓ Старая cron задача удалена"
fi

# Добавляем новую запись
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -
echo "✓ Cron задача успешно добавлена"

echo ""
echo "=========================================="
echo "Установка завершена!"
echo "=========================================="
echo ""
echo "Cron задача:"
echo "  $CRON_ENTRY"
echo ""
echo "Скрипт будет запускаться каждый день в 01:00"
echo ""
echo "Для проверки текущих cron задач:"
echo "  crontab -l"
echo ""
echo "Для просмотра логов выполнения:"
echo "  tail -f $LOG_PATH"
echo ""
echo "Для ручного тестирования скрипта:"
echo "  $SCRIPT_PATH"
echo ""
