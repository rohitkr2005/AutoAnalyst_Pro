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
from engine.security_utils import validate_safe_db_url

if PSYCOPG2_AVAILABLE:
    import psycopg2
    from psycopg2.extras import RealDictCursor


def is_safe_read_query(query: str) -> Tuple[bool, str]:
    """Ensures SQL statements are strictly single read-only queries."""
    if not query or not isinstance(query, str):
        return False, "Query cannot be empty."

    # Strip SQL comments
    cleaned = re.sub(r'--.*$', '', query, flags=re.MULTILINE)
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL).strip()
    
    if not (cleaned.upper().startswith("SELECT") or cleaned.upper().startswith("WITH")):
        return False, "Query must start with SELECT or WITH."

    # Remove string literals to prevent bypasses or false matches
    without_strings = re.sub(r"'(''|[^'])*'", "''", cleaned)
    
    # Check for multiple stacked queries separated by semicolon
    if ";" in without_strings.rstrip(";"):
        return False, "Multiple or stacked SQL statements are not permitted."

    dangerous_keywords = [
        "DROP", "DELETE", "TRUNCATE", "UPDATE", "INSERT", "ALTER", "GRANT", "REVOKE",
        "CREATE", "EXECUTE", "COPY", "CALL", "VACUUM", "REINDEX", "COMMENT", "SECURITY",
        "LOCK", "SET", "RESET", "DO", "DISCARD"
    ]
    q_upper = without_strings.upper()
    for kw in dangerous_keywords:
        if re.search(r'\b' + kw + r'\b', q_upper):
            return False, f"Prohibited modification statement: '{kw}' is not allowed in analyst query mode."

    return True, ""


def get_default_connection_url() -> str:
    """Returns the primary database connection URL from environment."""
    return get_database_url() or os.environ.get("DATABASE_URL", "")


def test_db_connection(db_url: Optional[str] = None) -> Dict[str, Any]:
    """Tests connectivity to PostgreSQL / Supabase database with SSRF protection."""
    if db_url:
        is_safe, err = validate_safe_db_url(db_url)
        if not is_safe:
            return {"status": "error", "message": f"Connection rejected: {err}"}

    url = (db_url or get_default_connection_url()).strip()
    if not url:
        return {"status": "error", "message": "No database connection URL configured."}
    if not PSYCOPG2_AVAILABLE:
        return {"status": "error", "message": "psycopg2 driver is not installed."}

    try:
        conn = psycopg2.connect(url, connect_timeout=6)
        conn.set_session(readonly=True)
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        conn.close()
        return {"status": "success", "message": "Connection established successfully!", "version": version}
    except Exception as e:
        return {"status": "error", "message": f"Connection failed: {str(e)}"}


def list_db_tables(db_url: Optional[str] = None) -> Dict[str, Any]:
    """Retrieves all user tables in the public schema with row estimates."""
    if db_url:
        is_safe, err = validate_safe_db_url(db_url)
        if not is_safe:
            return {"status": "error", "message": f"Connection rejected: {err}"}

    url = (db_url or get_default_connection_url()).strip()
    if not url:
        return {"status": "error", "message": "No database connection URL configured."}
    if not PSYCOPG2_AVAILABLE:
        return {"status": "error", "message": "psycopg2 driver is not installed."}

    try:
        conn = psycopg2.connect(url, connect_timeout=6)
        conn.set_session(readonly=True)
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
    if db_url:
        is_safe, err = validate_safe_db_url(db_url)
        if not is_safe:
            return None, f"Connection rejected: {err}"

    url = (db_url or get_default_connection_url()).strip()
    if not url:
        return None, "No database connection URL configured."
    if not PSYCOPG2_AVAILABLE:
        return None, "psycopg2 driver is not installed."

    # Validate table name to prevent SQL injection
    if not re.match(r'^[a-zA-Z0-9_]+$', table_name):
        return None, "Invalid table name format."

    try:
        conn = psycopg2.connect(url, connect_timeout=8)
        conn.set_session(readonly=True)
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

    if db_url:
        is_safe, url_err = validate_safe_db_url(db_url)
        if not is_safe:
            return {"status": "error", "message": f"Connection rejected: {url_err}"}

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
        conn.set_session(readonly=True)
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
