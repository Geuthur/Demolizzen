# Standard Library
import logging

# Django
from django.db.backends.mysql.base import DatabaseWrapper as MySQLDatabaseWrapper

logger = logging.getLogger(__name__)


class DatabaseWrapper(MySQLDatabaseWrapper):
    # Should fix "MySQL server has gone away" errors
    def ensure_connection(self):
        if self.connection:
            if not self.is_usable():
                self.close()
        super().ensure_connection()
