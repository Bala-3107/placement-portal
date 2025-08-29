# migrate_db.py
import sqlite3
import os
import shutil

DB_NAME = "database.db"
BACKUP_NAME = DB_NAME + ".bak"

def column_exists(cursor, table_name, column_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cursor.fetchall()]
    return column_name in columns

def add_column(cursor, table_name, column_name, column_type, default=None):
    if not column_exists(cursor, table_name, column_name):
        sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        if default is not None:
            sql += f" DEFAULT {default!r}"
        cursor.execute(sql)
        print(f"✅ Added column '{column_name}' to '{table_name}'")
    else:
        print(f"ℹ️ Column '{column_name}' already exists in '{table_name}'")

def ensure_table(cursor, create_sql, table_name):
    cursor.execute(create_sql)
    print(f"✅ Ensured table '{table_name}' exists (or was created)")

def main():
    # Backup DB
    if os.path.exists(DB_NAME):
        print(f"Backing up existing DB to {BACKUP_NAME} ...")
        shutil.copyfile(DB_NAME, BACKUP_NAME)
    else:
        print("No existing DB found - new DB will be created.")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Ensure users table (with many commonly used columns)
    ensure_table(cursor, """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        email TEXT,
        password TEXT,
        role TEXT,
        resume TEXT,
        city TEXT,
        state TEXT,
        country TEXT,
        job_preference TEXT,
        bio TEXT,
        company TEXT,
        phone TEXT,
        website TEXT,
        linkedin TEXT,
        university TEXT,
        degree TEXT,
        graduation_year TEXT
    )
    """, "users")

    # Ensure jobs table (full schema used by your app)
    ensure_table(cursor, """
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        recruiter_id INTEGER,
        title TEXT,
        company TEXT,
        company_description TEXT,
        location TEXT,
        job_type TEXT,
        salary TEXT,
        description TEXT,
        post_date TEXT DEFAULT CURRENT_TIMESTAMP,
        interview_date TEXT,
        interview_time TEXT,
        interview_place TEXT,
        posted_by TEXT,
        application_date TEXT,
        job_status TEXT DEFAULT 'Open'
    )
    """, "jobs")

    # Ensure applications table (full schema)
    ensure_table(cursor, """
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER,
        student_id INTEGER,
        student_name TEXT,
        email TEXT,
        city TEXT,
        job_preference TEXT,
        application_date TEXT,
        resume TEXT,
        company TEXT,
        job_title TEXT,
        FOREIGN KEY(job_id) REFERENCES jobs(id),
        FOREIGN KEY(student_id) REFERENCES users(id)
    )
    """, "applications")

    # If tables existed but missing columns, add them (guards so ALTER runs only when needed)
    # users columns
    user_cols = [
        ("resume", "TEXT"),
        ("city", "TEXT"),
        ("state", "TEXT"),
        ("country", "TEXT"),
        ("job_preference", "TEXT"),
        ("bio", "TEXT"),
        ("company", "TEXT"),
        ("phone", "TEXT"),
        ("website", "TEXT"),
        ("linkedin", "TEXT"),
        ("university", "TEXT"),
        ("degree", "TEXT"),
        ("graduation_year", "TEXT"),
    ]
    for col, typ in user_cols:
        add_column(cursor, "users", col, typ)

    # jobs columns
    job_cols = [
        ("company_description", "TEXT"),
        ("job_type", "TEXT"),
        ("salary", "TEXT"),
        ("post_date", "TEXT"),
        ("interview_date", "TEXT"),
        ("interview_time", "TEXT"),
        ("interview_place", "TEXT"),
        ("posted_by", "TEXT"),
        ("application_date", "TEXT"),
        ("job_status", "TEXT"),
        ("company", "TEXT"),
    ]
    for col, typ in job_cols:
        add_column(cursor, "jobs", col, typ)

    # applications columns
    app_cols = [
        ("student_id", "INTEGER"),
        ("email", "TEXT"),
        ("city", "TEXT"),
        ("job_preference", "TEXT"),
        ("application_date", "TEXT"),
        ("resume", "TEXT"),
        ("company", "TEXT"),
        ("job_title", "TEXT"),
    ]
    for col, typ in app_cols:
        add_column(cursor, "applications", col, typ)

    conn.commit()
    conn.close()

    print("\n✅ Migration completed. Please restart your Flask app.")
    print(f"Backup of previous DB is at: {BACKUP_NAME}")

if __name__ == "__main__":
    main()
