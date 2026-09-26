"""
AutoAnalyst Pro - Live Database & Cloud Connector Engine
Connects directly to PostgreSQL / Supabase databases, lists schemas and tables,
executes read-only SQL queries, and loads live database tables directly into the analysis pipeline.
"""

import os
import re
import pandas as pd
from typing import Dict, Any, List, Optional, Tuple
from engine.auth import get_database_url, PSYCOPG2_AVAILABLE

if PSYCOPG2_AVAILABLE:
    import psycopg2
    from psycopg2.extras import RealDictCursor


def is_safe_read_query(query: str) -> Tuple[bool, str]:
    """Ensures SQL statements are strictly read-only queries."""
    q = query.strip().upper()
    dangerous_keywords = ["DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT", "ALTER", "GRANT", "REVOKE"]
    for kw in dangerous_keywords:
        if re.search(r'\b' + kw + r'\b', q):
            return False, f"Prohibited modification statement: '{kw}' is not allowed in analyst query mode."
    if not (q.startswith("SELECT") or q.startswith("WITH")):
        return False, "Query must start with SELECT or WITH."
    return True, ""


def get_default_connection_url() -> str:
    """Returns the primary database connection URL from environment."""
    return get_database_url() or os.environ.get("DATABASE_URL", "")


def test_db_connection(db_url: Optional[str] = None) -> Dict[str, Any]:
    """Tests connectivity to PostgreSQL / Supabase database."""
    url = (db_url or get_default_connection_url()).strip()
    if not url:
        return {"status": "error", "message": "No database connection URL configured."}
    if not PSYCOPG2_AVAILABLE:
        return {"status": "error", "message": "psycopg2 driver is not installed."}

    try:
        conn = psycopg2.connect(url, connect_timeout=6)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        conn.close()
        return {"status": "success", "message": "Connection established successfully!", "version": version}
    except Exception as e:
        return {"status": "error", "message": f"Connection failed: {str(e)}"}


def list_db_tables(db_url: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves all user tables in the public schema with row estimates."""
    url = (db_url or get_default_connection_url()).strip()
    if not url:
        return {"status": "error", "message": "No database connection URL configured."}
    if not PSYCOPG2_AVAILABLE:
        return {"status": "error", "message": "psycopg2 driver is not installed."}

    try:
        conn = psycopg2.connect(url, connect_timeout=6)
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("""
            SELECT 
                t.table_name,
                COALESCE(s.n_live_tup, 0) AS estimated_rows
            FROM information_schema.tables t
            LEFT JOIN pg_stat_user_tables s ON s.relname = t.table_name
            WHERE t.table_schema = 'public' 
              AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_name ASC;
        """)
        tables = cur.fetchall()
        conn.close()
        return {
            "status": "success",
            "tables": [{"name": t["table_name"], "rows": int(t["estimated_rows"])} for t in tables]
        }
    except Exception as e:
        return {"status": "error", "message": f"Could not list database tables: {str(e)}"}


def load_db_table_data(table_name: str, db_url: Optional[str] = None, limit: int = 10000) -> Tuple[Optional[pd.DataFrame], Optional[str]]:
    """Loads a full table into a pandas DataFrame."""
    url = (db_url or get_default_connection_url()).strip()
    if not url:
        return None, "No database connection URL configured."
    if not PSYCOPG2_AVAILABLE:
        return None, "psycopg2 driver is not installed."

    # Validate table name to prevent SQL injection
    if not re.match(r'^[a-zA-Z0-9_]+$', table_name):
        return None, "Invalid table name."

    try:
        conn = psycopg2.connect(url, connect_timeout=8)
        sql = f'SELECT * FROM "{table_name}" LIMIT {int(limit)};'
        df = pd.read_sql(sql, conn)
        conn.close()
        return df, None
    except Exception as e:
        return None, f"Failed to load table '{table_name}': {str(e)}"


def execute_custom_db_query(sql_query: str, db_url: Optional[str] = None, limit: int = 5000) -> Dict[str, Any]:
    """Executes a custom read-only SQL query and returns rows and metadata."""
    safe, err = is_safe_read_query(sql_query)
    if not safe:
        return {"status": "error", "message": err}

    url = (db_url or get_default_connection_url()).strip()
    if not url:
        return {"status": "error", "message": "No database connection URL configured."}
    if not PSYCOPG2_AVAILABLE:
        return {"status": "error", "message": "psycopg2 driver is not installed."}

    # Ensure query ends with LIMIT if not present
    q_clean = sql_query.strip().rstrip(";")
    if "LIMIT" not in q_clean.upper():
        q_clean += f" LIMIT {int(limit)}"

    try:
        conn = psycopg2.connect(url, connect_timeout=8)
        df = pd.read_sql(q_clean, conn)
        conn.close()

        # Sanitize for JSON
        preview = df.head(100).fillna("").to_dict(orient="records")
        return {
            "status": "success",
            "total_rows": len(df),
            "columns": list(df.columns),
            "rows": preview
        }
    except Exception as e:
        return {"status": "error", "message": f"Query execution error: {str(e)}"}
