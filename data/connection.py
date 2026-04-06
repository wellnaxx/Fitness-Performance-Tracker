import psycopg
from psycopg import Connection

from core.config import get_db_config


def get_connection() -> Connection:
    config = get_db_config()

    return psycopg.connect(
        dbname=config.name,
        user=config.user,
        password=config.password,
        host=config.host,
        port=config.port,
    )
