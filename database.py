"""SQLite connection, initialization, and query helpers."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
DATABASE_PATH = PROJECT_DIR / "complaints.db"
SCHEMA_PATH = PROJECT_DIR / "schema.sql"
DEFAULT_CATEGORIES = (
    ("Electricity", "Electrical Maintenance Team"),
    ("Plumbing", "Plumbing Team"),
    ("Internet", "IT Support Team"),
    ("Cleaning", "Housekeeping Team"),
    ("Maintenance", "Maintenance Team"),
)


def resolve_database_path(database_path=None):
    return Path(database_path) if database_path is not None else DATABASE_PATH


@contextmanager
def get_connection(database_path=None):
    """Yield a row-aware connection, commit successful work, and always close it."""
    connection = sqlite3.connect(resolve_database_path(database_path), timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def initialize_database(database_path=None):
    """Create tables and seed the sample categories only when none exist."""
    schema = SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection(database_path) as connection:
        connection.executescript(schema)
        total = connection.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if total == 0:
            connection.executemany(
                "INSERT INTO categories (name, handler) VALUES (?, ?)",
                DEFAULT_CATEGORIES,
            )


def add_category(name, handler, database_path=None):
    try:
        with get_connection(database_path) as connection:
            cursor = connection.execute(
                "INSERT INTO categories (name, handler) VALUES (?, ?)",
                (name, handler),
            )
            return cursor.lastrowid
    except sqlite3.IntegrityError as exc:
        if "categories.name" in str(exc) or "UNIQUE constraint failed" in str(exc):
            raise ValueError("Duplicate category") from exc
        raise


def list_categories(database_path=None):
    with get_connection(database_path) as connection:
        rows = connection.execute(
            "SELECT cat_id, name, handler FROM categories ORDER BY cat_id"
        ).fetchall()
    return [dict(row) for row in rows]


def get_category(category_id, database_path=None):
    with get_connection(database_path) as connection:
        row = connection.execute(
            "SELECT cat_id, name, handler FROM categories WHERE cat_id = ?",
            (category_id,),
        ).fetchone()
    return dict(row) if row else None


def add_ticket(category_id, student_name, room_no, description, database_path=None):
    with get_connection(database_path) as connection:
        category = connection.execute(
            "SELECT 1 FROM categories WHERE cat_id = ?", (category_id,)
        ).fetchone()
        if category is None:
            raise ValueError("Category not found")
        cursor = connection.execute(
            "INSERT INTO tickets (cat_id, student_name, room_no, description) "
            "VALUES (?, ?, ?, ?)",
            (category_id, student_name, room_no, description),
        )
        return cursor.lastrowid


def get_ticket(ticket_id, database_path=None):
    sql = """SELECT t.ticket_id, t.student_name, t.room_no, c.name AS category,
                    t.description, c.handler, t.status, t.raised_at
             FROM tickets AS t JOIN categories AS c ON c.cat_id = t.cat_id
             WHERE t.ticket_id = ?"""
    with get_connection(database_path) as connection:
        row = connection.execute(sql, (ticket_id,)).fetchone()
    return dict(row) if row else None


def get_tickets(status=None, category_id=None, database_path=None):
    sql = """SELECT t.ticket_id, t.student_name, t.room_no, c.name AS category,
                    t.description, c.handler, t.status, t.raised_at
             FROM tickets AS t JOIN categories AS c ON c.cat_id = t.cat_id"""
    clauses, parameters = [], []
    if status is not None:
        clauses.append("t.status = ?")
        parameters.append(status)
    if category_id is not None:
        clauses.append("t.cat_id = ?")
        parameters.append(category_id)
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY t.ticket_id"
    with get_connection(database_path) as connection:
        rows = connection.execute(sql, parameters).fetchall()
    return [dict(row) for row in rows]


def update_ticket_status(ticket_id, new_status, database_path=None):
    """Advance exactly one step using a transaction and an old-status condition."""
    with get_connection(database_path) as connection:
        # Obtain the write lock before reading so competing wardens serialize here.
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT status FROM tickets WHERE ticket_id = ?", (ticket_id,)
        ).fetchone()
        if row is None:
            raise LookupError("Ticket not found")
        current = row["status"]
        transitions = {"Open": "In progress", "In progress": "Closed"}
        if transitions.get(current) != new_status:
            raise ValueError(f"Cannot change status from {current} to {new_status}")
        cursor = connection.execute(
            "UPDATE tickets SET status = ? WHERE ticket_id = ? AND status = ?",
            (new_status, ticket_id, current),
        )
        if cursor.rowcount != 1:
            raise ValueError("Ticket status changed by another warden; reload and retry")
    return new_status


def get_table_counts(database_path=None):
    with get_connection(database_path) as connection:
        categories = connection.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        tickets = connection.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
    return {"categories": categories, "tickets": tickets}


def get_status_report(database_path=None):
    with get_connection(database_path) as connection:
        rows = connection.execute(
            "SELECT status, COUNT(*) AS total FROM tickets GROUP BY status"
        ).fetchall()
    totals = {row["status"]: row["total"] for row in rows}
    return {status: totals.get(status, 0) for status in ("Open", "In progress", "Closed")}


def get_category_report(database_path=None):
    sql = """SELECT c.name AS category, COUNT(t.ticket_id) AS total_tickets
             FROM categories AS c
             LEFT JOIN tickets AS t ON t.cat_id = c.cat_id
             GROUP BY c.cat_id, c.name
             ORDER BY c.cat_id"""
    with get_connection(database_path) as connection:
        rows = connection.execute(sql).fetchall()
    return [dict(row) for row in rows]
