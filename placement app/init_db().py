import sqlite3
import os

DB_NAME = "database.db"

def column_exists(cursor, table_name, column_name):
    """Check if a column exists in a given table."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def add_column_if_missing(cursor, table_name, column_name, column_type):
    """Add a new column if it does not already exist."""
    if not column_exists(cursor, table_name, column_name):
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
        print(f"✅ Added column '{column_name}' to table '{table_name}'")
    else:
        print(f"ℹ️ Column '{column_name}' already exists in '{table_name}'")

def init_or_migrate_db():
    """Initialize a new database or migrate an existing one by adding missing columns."""
    new_db = not os.path.exists(DB_NAME)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    if new_db:
        print("📦 Creating new database...")

        # Users table
        cursor.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL
        )
        """)

        # Students table
        cursor.execute("""
        CREATE TABLE students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)

        # Recruiters table
        cursor.execute("""
        CREATE TABLE recruiters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            company_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """)

        # Jobs table
        cursor.execute("""
        CREATE TABLE jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recruiter_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            location TEXT,
            salary TEXT,
            interview_date TEXT,
            interview_time TEXT,
            interview_place TEXT,
            FOREIGN KEY (recruiter_id) REFERENCES recruiters(id)
        )
        """)

        # Applications table
        cursor.execute("""
        CREATE TABLE applications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id INTEGER NOT NULL,
            student_id INTEGER NOT NULL,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (job_id) REFERENCES jobs(id),
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
        """)

        conn.commit()
        print("✅ New database created successfully.")

    else:
        print("🔄 Existing database found. Running migrations...")

        # --- Students table updates ---
        add_column_if_missing(cursor, "students", "university", "TEXT")
        add_column_if_missing(cursor, "students", "degree", "TEXT")
        add_column_if_missing(cursor, "students", "department", "TEXT")
        add_column_if_missing(cursor, "students", "graduation_year", "INTEGER")
        add_column_if_missing(cursor, "students", "resume", "TEXT")

        # --- Users table updates ---
           
        add_column_if_missing(cursor, "users", "city", "TEXT")
        add_column_if_missing(cursor, "users", "state", "TEXT")
        add_column_if_missing(cursor, "users", "country", "TEXT")
        add_column_if_missing(cursor, "users", "job_preference", "TEXT")
        add_column_if_missing(cursor, "users", "bio", "TEXT")
        add_column_if_missing(cursor, "users", "company", "TEXT")
        add_column_if_missing(cursor, "users", "linkedin", "TEXT")
        add_column_if_missing(cursor, "users", "phone", "TEXT")
        add_column_if_missing(cursor, "users", "website", "TEXT")


        # --- Recruiters table updates ---
        add_column_if_missing(cursor, "recruiters", "website", "TEXT")
        add_column_if_missing(cursor, "recruiters", "phone", "TEXT")
        add_column_if_missing(cursor, "recruiters", "linkedin", "TEXT")

        conn.commit()
        print("✅ Migrations completed.")

    conn.close()

if __name__ == "__main__":
    init_or_migrate_db()
