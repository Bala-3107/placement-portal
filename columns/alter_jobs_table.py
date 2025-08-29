import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# Drop the existing table
cursor.execute("DROP TABLE IF EXISTS jobs")

# Create a new table with all required columns
cursor.execute("""
CREATE TABLE jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    company_description TEXT,
    location TEXT,
    company TEXT,
    job_type TEXT,
    salary TEXT,
    posted_by TEXT,
    post_date TEXT DEFAULT CURRENT_TIMESTAMP,
    interview_date TEXT,
    interview_time TEXT,
    interview_place TEXT,
    application_date TEXT,
    job_status TEXT DEFAULT 'Open'
)
""")

conn.commit()
conn.close()

print("✅ Dropped and recreated 'jobs' table with all necessary columns.")
