"""Snowflake connection pool — reuses connections instead of creating new ones per request."""

import snowflake.connector
from contextlib import contextmanager
from threading import Lock
from api.config import settings

_connection_params = {
    "account": settings.snowflake_account,
    "user": settings.snowflake_user,
    "private_key_file": settings.snowflake_private_key_path,
    "role": settings.snowflake_role,
    "warehouse": settings.snowflake_warehouse,
    "database": settings.snowflake_database,
    "client_session_keep_alive": True,
}

_pool: list[snowflake.connector.SnowflakeConnection] = []
_pool_lock = Lock()
_MAX_POOL_SIZE = 4


def _create_connection() -> snowflake.connector.SnowflakeConnection:
    return snowflake.connector.connect(**_connection_params)


def get_connection() -> snowflake.connector.SnowflakeConnection:
    """Get a connection from the pool, or create a new one."""
    with _pool_lock:
        while _pool:
            conn = _pool.pop()
            try:
                conn.cursor().execute("SELECT 1")
                return conn
            except Exception:
                # Stale connection, discard
                try:
                    conn.close()
                except Exception:
                    pass
    return _create_connection()


def return_connection(conn: snowflake.connector.SnowflakeConnection):
    """Return a connection to the pool for reuse."""
    with _pool_lock:
        if len(_pool) < _MAX_POOL_SIZE:
            _pool.append(conn)
        else:
            try:
                conn.close()
            except Exception:
                pass


@contextmanager
def get_cursor():
    conn = get_connection()
    try:
        cur = conn.cursor()
        yield cur
    finally:
        return_connection(conn)
