import logging

logger = logging.getLogger('django.server')


class LogIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Получаем IP адрес
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')

        # Логируем метод, путь и IP
        # Вывод будет в терминале благодаря настройкам logging в settings.py
        print(f"Incoming Request: {request.method} {request.path} from IP: {ip}")

        response = self.get_response(request)
        return response