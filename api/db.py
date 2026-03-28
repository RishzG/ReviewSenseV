"""Snowflake connection pool."""

import snowflake.connector
from contextlib import contextmanager
from api.config import settings

_connection_params = {
    "account": settings.snowflake_account,
    "user": settings.snowflake_user,
    "private_key_file": settings.snowflake_private_key_path,
    "role": settings.snowflake_role,
    "warehouse": settings.snowflake_warehouse,
    "database": settings.snowflake_database,
}


def get_connection() -> snowflake.connector.SnowflakeConnection:
    return snowflake.connector.connect(**_connection_params)


@contextmanager
def get_cursor():
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
    finally:
        conn.close()
