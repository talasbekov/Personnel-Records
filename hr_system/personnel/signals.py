from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import Position, Division

@receiver([post_save, post_delete], sender=Position)
def clear_cache_on_position_change(sender, instance, **kwargs):
    cache.clear()

@receiver([post_save, post_delete], sender=Division)
def clear_cache_on_division_change(sender, instance, **kwargs):
    cache.clear()
