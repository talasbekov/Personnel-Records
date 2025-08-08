from django.test import TestCase
from django.core.cache import cache

class CachingTest(TestCase):
    def test_cache_set_and_get(self):
        """
        Test that we can set and get a value from the cache.
        """
        cache.set('my_key', 'my_value', 30)
        value = cache.get('my_key')
        self.assertEqual(value, 'my_value')
