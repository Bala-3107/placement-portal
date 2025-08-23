import sqlite3
from datetime import datetime

DB_NAME = 'database.db'
import sqlite3

conn = sqlite3.connect('database.db')
conn.execute("ALTER TABLE jobs ADD COLUMN location TEXT")
conn.commit()
conn.close()

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------------------
# Initialize DB Schema
# ---------------------------
def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL,
        password TEXT NOT NULL,
        role TEXT CHECK(role IN ('student', 'recruiter')) NOT NULL,
        city TEXT,
        job_preference TEXT,
        resume TEXT
    )
    ''')

    # Jobs table (updated with location, job_type, salary)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        company TEXT NOT NULL,
        description TEXT NOT NULL,
        location TEXT,
        job_type TEXT,
        salary INTEGER,
        posted_by TEXT NOT NULL,
        FOREIGN KEY(posted_by) REFERENCES users(username)
    )
    ''')

    # Applications table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS applications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        student_name TEXT NOT NULL,
        application_date TEXT NOT NULL,
        FOREIGN KEY(job_id) REFERENCES jobs(id),
        FOREIGN KEY(student_name) REFERENCES users(username)
    )
    ''')

    conn.commit()
    conn.close()

# ---------------------------
# User Functions
# ---------------------------
def create_user(username, email, password, role, city, job_preference=None, resume=None):
    conn = get_connection()
    conn.execute('''
        INSERT INTO users (username, email, password, role, city, job_preference, resume)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (username, email, password, role, city, job_preference, resume))
    conn.commit()
    conn.close()

def get_user_by_username(username):
    conn = get_connection()
    user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
    conn.close()
    return user

# ---------------------------
# Job Functions
# ---------------------------
def create_job(title, company, description, location, job_type, salary, posted_by):
    conn = get_connection()
    conn.execute('''
        INSERT INTO jobs (title, company, description, location, job_type, salary, posted_by)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (title, company, description, location, job_type, salary, posted_by))
    conn.commit()
    conn.close()

def get_all_jobs():
    conn = get_connection()
    jobs = conn.execute('SELECT * FROM jobs').fetchall()
    conn.close()
    return jobs

def get_job_by_id(job_id):
    conn = get_connection()
    job = conn.execute('SELECT * FROM jobs WHERE id = ?', (job_id,)).fetchone()
    conn.close()
    return job

def get_jobs_by_recruiter(username):
    conn = get_connection()
    jobs = conn.execute('SELECT * FROM jobs WHERE posted_by = ?', (username,)).fetchall()
    conn.close()
    return jobs

# ---------------------------
# Application Functions
# ---------------------------
def apply_to_job(job_id, student_name):
    if has_already_applied(job_id, student_name):
        return False  # prevent duplicate application

    conn = get_connection()
    date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    conn.execute('''
        INSERT INTO applications (job_id, student_name, application_date)
        VALUES (?, ?, ?)
    ''', (job_id, student_name, date))
    conn.commit()
    conn.close()
    return True

def has_already_applied(job_id, student_name):
    conn = get_connection()
    result = conn.execute('''
        SELECT * FROM applications
        WHERE job_id = ? AND student_name = ?
    ''', (job_id, student_name)).fetchone()
    conn.close()
    return result is not None

def get_applications_for_job(job_id):
    conn = get_connection()
    apps = conn.execute('''
        SELECT a.*, u.email, u.resume
        FROM applications a
        JOIN users u ON a.student_name = u.username
        WHERE job_id = ?
    ''', (job_id,)).fetchall()
    conn.close()
    return apps

def get_applications_by_student(student_name):
    conn = get_connection()
    apps = conn.execute('''
        SELECT a.*, j.title, j.company
        FROM applications a
        JOIN jobs j ON a.job_id = j.id
        WHERE a.student_name = ?
    ''', (student_name,)).fetchall()
    conn.close()
    return apps

def get_applicants_for_recruiter(username):
    conn = get_connection()
    applicants = conn.execute('''
        SELECT a.*, u.email, u.city, u.resume, j.title
        FROM applications a
        JOIN users u ON a.student_name = u.username
        JOIN jobs j ON a.job_id = j.id
        WHERE j.posted_by = ?
    ''', (username,)).fetchall()
    conn.close()
    return applicants
