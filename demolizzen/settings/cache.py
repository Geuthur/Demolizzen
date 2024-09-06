import os

import diskcache
from settings.config import CACHE_DIR


class CacheManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.init_cache()
        return cls._instance

    def init_cache(self):
        # Erstelle den Cache-Ordner, wenn er nicht existiert
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)

        # Erstelle einen Cache auf der Festplatte
        self.cache = diskcache.Cache(CACHE_DIR, default_timeout=15)

    def get_cache(self):
        return self.cache
