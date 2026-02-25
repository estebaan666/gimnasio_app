import os
import psycopg2
from psycopg2.extras import RealDictCursor

def obtener_conexion():
    db_url = os.environ.get("DATABASE_URL")
    if db_url:
        return psycopg2.connect(
            db_url,
            sslmode='require',
            cursor_factory=RealDictCursor
        )
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', '127.0.0.1'),
        database=os.environ.get('DB_NAME', 'ginnasio'),
        user=os.environ.get('DB_USER', 'postgres'),
        password=os.environ.get('DB_PASSWORD', ''),
        port=os.environ.get('DB_PORT', '5432'),
        cursor_factory=RealDictCursor
    )
