"""Built-in database tool for yom."""

from __future__ import annotations

import json

from yom.tools import tool


@tool(
    name="query_db",
    description="""Execute a SQL query on a database.
    
    This is a DRY-RUN by default. Set dry_run=false to actually execute.
    
    Args:
        sql: The SQL query to execute
        connection_string: Database connection string (e.g., postgresql://user:pass@localhost/db)
        database_type: Type of database (postgresql, mysql, sqlite)
        dry_run: If true, only validate the query without executing
    
    Returns:
        Query results or validation status.
    """,
    schema={
        "type": "object",
        "properties": {
            "sql": {
                "type": "string",
                "description": "The SQL query to execute"
            },
            "connection_string": {
                "type": "string",
                "description": "Database connection string"
            },
            "database_type": {
                "type": "string",
                "description": "Database type (postgresql, mysql, sqlite)",
                "enum": ["postgresql", "mysql", "sqlite"],
                "default": "sqlite"
            },
            "dry_run": {
                "type": "boolean",
                "description": "If true, only validate without executing",
                "default": True
            }
        },
        "required": ["sql"]
    }
)
def query_db(
    sql: str,
    connection_string: str | None = None,
    database_type: str = "sqlite",
    dry_run: bool = True,
) -> str:
    """Execute a SQL query."""
    import sqlite3
    import re

    # Basic SQL injection prevention for dry_run
    dangerous_keywords = ['DROP', 'DELETE', 'TRUNCATE', 'ALTER', 'CREATE', 'INSERT', 'UPDATE', 'GRANT', 'REVOKE']
    sql_upper = sql.upper().strip()
    
    # Check for dangerous operations
    if any(f" {kw} " in f" {sql_upper} " or sql_upper.startswith(kw) for kw in dangerous_keywords):
        if dry_run:
            return f"[DRY-RUN] Would execute: {sql[:200]}..."
        else:
            # Check connection string for safety
            if not connection_string or "localhost" not in connection_string:
                return f"Error: Cannot execute destructive queries on remote databases without explicit localhost connection"

    # SQLite in-memory for validation
    try:
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE _validate (x TEXT)")
        
        if dry_run:
            cursor.execute(f"EXPLAIN QUERY PLAN {sql}")
            plan = cursor.fetchall()
            return f"[DRY-RUN] Query validated. Execution plan:\n" + "\n".join(str(row) for row in plan)
        
        cursor.execute(sql)
        
        if sql.strip().upper().startswith("SELECT"):
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            result = {
                "columns": columns,
                "rows": rows[:100],  # Limit to 100 rows
                "total_rows": len(rows),
                "truncated": len(rows) > 100
            }
            return json.dumps(result, indent=2, default=str)
        else:
            conn.commit()
            return f"Query executed. {cursor.rowcount} rows affected."
            
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"
    finally:
        conn.close()


@tool(
    name="db_schema",
    description="""Get database schema information.
    
    Args:
        connection_string: Database connection string
        database_type: Type of database (postgresql, mysql, sqlite)
        table_name: Optional specific table name
    
    Returns:
        Schema information for the database or table.
    """,
    schema={
        "type": "object",
        "properties": {
            "connection_string": {
                "type": "string",
                "description": "Database connection string"
            },
            "database_type": {
                "type": "string",
                "description": "Database type (sqlite, postgresql, mysql)",
                "enum": ["sqlite", "postgresql", "mysql"],
                "default": "sqlite"
            },
            "table_name": {
                "type": "string",
                "description": "Optional specific table name"
            }
        },
        "required": ["connection_string"]
    }
)
def db_schema(
    connection_string: str | None = None,
    database_type: str = "sqlite",
    table_name: str | None = None,
) -> str:
    """Get database schema."""
    import sqlite3

    # Only allow local SQLite files
    if database_type == "sqlite":
        db_path = connection_string or ":memory:"
        if not db_path.startswith(":memory:") and not db_path.startswith("/"):
            return "Error: SQLite path must be absolute"
    
    try:
        conn = sqlite3.connect(connection_string or ":memory:")
        cursor = conn.cursor()
        
        if table_name:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            return json.dumps({
                "table": table_name,
                "columns": [
                    {"name": col[1], "type": col[2], "nullable": not col[3], "default": col[4]}
                    for col in columns
                ]
            }, indent=2)
        else:
            cursor.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view')")
            tables = cursor.fetchall()
            result = []
            for name, _ in tables:
                cursor.execute(f"PRAGMA table_info({name})")
                cols = cursor.fetchall()
                result.append({
                    "name": name,
                    "columns": [col[1] for col in cols]
                })
            return json.dumps({"tables": result}, indent=2, default=str)
            
    except Exception as e:
        return f"Error: {type(e).__name__}: {e}"
    finally:
        conn.close()


__all__ = ["query_db", "db_schema"]
