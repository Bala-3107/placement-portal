# app.py
import os
import threading
import webbrowser
from datetime import datetime
from functools import wraps
import sqlite3
import pytz
import shutil

from flask import (
    Flask, render_template, request, redirect, url_for,
    session, flash, send_from_directory
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_dance.contrib.github import make_github_blueprint, github
from flask_dance.contrib.google import make_google_blueprint, google
from fpdf import FPDF
from flask_mail import Mail, Message

# Basic paths
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'database.db')
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'resumes')
PDF_FOLDER = os.path.join(BASE_DIR, 'static', 'profile_pdfs')
BACKUP_DB = DB_PATH + '.bak'

# App Configuration
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "supersecretkey")

# Mail Configuration
app.config.update(
    MAIL_SERVER='smtp.gmail.com',
    MAIL_PORT=587,
    MAIL_USE_TLS=True,
    MAIL_USERNAME=os.getenv('EMAIL_USER'),
    MAIL_PASSWORD=os.getenv('EMAIL_PASS')
)
# set default sender (prevents AssertionError when sending)
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('EMAIL_USER', 'no-reply@example.com')
mail = Mail(app)

# Ensure folders exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PDF_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# OAuth Blueprints (optional)
github_bp = make_github_blueprint(
    client_id=os.getenv("GITHUB_CLIENT_ID", ""),
    client_secret=os.getenv("GITHUB_CLIENT_SECRET", "")
)
google_bp = make_google_blueprint(
    client_id=os.getenv("GOOGLE_CLIENT_ID", ""),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET", ""),
    redirect_url="/login/google/authorized"
)
app.register_blueprint(github_bp, url_prefix="/login/github")
app.register_blueprint(google_bp, url_prefix="/login/google")

# Database helper
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# Helper: check if column exists
def column_exists(conn, table_name, column_name):
    cur = conn.execute(f"PRAGMA table_info({table_name})")
    cols = [r[1] for r in cur.fetchall()]
    return column_name in cols

# Initialize / migrate DB
def init_db():
    # backup existing DB first (safe)
    if os.path.exists(DB_PATH):
        try:
            shutil.copyfile(DB_PATH, BACKUP_DB)
            print(f"Backup created at {BACKUP_DB}")
        except Exception as e:
            print("Backup failed:", e)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Create users table with many columns used by app
    c.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT,
        city TEXT,
        state TEXT,
        country TEXT,
        password TEXT,
        role TEXT,
        resume TEXT,
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
    """)

    # Create jobs table: include recruiter_id and posted_by and company_description
    c.execute("""
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
    """)

    # Create applications table
    c.execute("""
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
    """)

    conn.commit()

    # For older DBs that predate these columns - attempt to add missing columns
    # (SQLite will error if column exists; we check first)
    jobs_extra = {
        "recruiter_id": "INTEGER",
        "company_description": "TEXT",
        "job_type": "TEXT",
        "salary": "TEXT",
        "post_date": "TEXT",
        "interview_date": "TEXT",
        "interview_time": "TEXT",
        "interview_place": "TEXT",
        "posted_by": "TEXT",
        "application_date": "TEXT",
        "job_status": "TEXT",
        "company": "TEXT"
    }
    users_extra = {
        "resume": "TEXT",
        "city": "TEXT",
        "state": "TEXT",
        "country": "TEXT",
        "job_preference": "TEXT",
        "bio": "TEXT",
        "company": "TEXT",
        "phone": "TEXT",
        "website": "TEXT",
        "linkedin": "TEXT",
        "university": "TEXT",
        "degree": "TEXT",
        "graduation_year": "TEXT"
    }
    apps_extra = {
        "student_id": "INTEGER",
        "student_name": "TEXT",
        "email": "TEXT",
        "city": "TEXT",
        "job_preference": "TEXT",
        "application_date": "TEXT",
        "resume": "TEXT",
        "company": "TEXT",
        "job_title": "TEXT"
    }

    # function to add column if missing
    def ensure_columns(table, cols):
        for col, coltype in cols.items():
            if not column_exists(conn, table, col):
                try:
                    c.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype}")
                    print(f"Added column {col} to {table}")
                except Exception as e:
                    print(f"Failed to add {col} to {table}: {e}")

    ensure_columns("jobs", jobs_extra)
    ensure_columns("users", users_extra)
    ensure_columns("applications", apps_extra)

    conn.commit()
    conn.close()
    print("Database ready.")

# Inject Time (for templates)
@app.context_processor
def inject_now():
    india_time = datetime.now(pytz.timezone("Asia/Kolkata"))
    return {'now': india_time.strftime("%d-%m-%Y %I:%M %p")}

# Authentication / Authorization helpers
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'username' not in session:
            flash("Please log in first.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def role_required(role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if session.get('role') != role:
                flash("Access denied.", "danger")
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return wrapper
    return decorator

# Routes -------------------------------------------------------------------

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/register/student', methods=['GET', 'POST'])
def register_student():
    if request.method == 'GET':
        return render_template('register_student.html')

    username = request.form['username'].strip()
    email = request.form.get('email', '').strip()
    city = request.form.get('city', '').strip()
    password = request.form['password']
    job_preference = request.form.get('job_preference', '')
    resume = request.files.get('resume')

    resume_filename = None
    if resume and resume.filename:
        resume_filename = secure_filename(f"{username}_{resume.filename}")
        resume.save(os.path.join(app.config['UPLOAD_FOLDER'], resume_filename))

    conn = get_db_connection()
    if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        flash("Username already exists.", "danger")
        conn.close()
        return redirect(url_for('register_student'))

    hashed_pw = generate_password_hash(password)
    conn.execute('''
        INSERT INTO users (username, email, city, password, role, resume, job_preference)
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (username, email, city, hashed_pw, 'student', resume_filename, job_preference)
    )
    conn.commit()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    session['username'] = username
    session['role'] = 'student'
    session['user_id'] = user['id']
    flash("Registered successfully!", "success")
    return redirect(url_for('dashboard'))

@app.route('/register/recruiter', methods=['GET', 'POST'])
def register_recruiter():
    if request.method == 'GET':
        return render_template('register_recruiter.html')

    username = request.form['username'].strip()
    email = request.form.get('email', '').strip()
    city = request.form.get('city', '').strip()
    password = request.form['password']
    resume = request.files.get('resume')

    resume_filename = None
    if resume and resume.filename:
        resume_filename = secure_filename(f"{username}_{resume.filename}")
        resume.save(os.path.join(app.config['UPLOAD_FOLDER'], resume_filename))

    conn = get_db_connection()
    if conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone():
        flash("Username already exists.", "danger")
        conn.close()
        return redirect(url_for('register_recruiter'))

    hashed_pw = generate_password_hash(password)
    conn.execute('''
        INSERT INTO users (username, email, city, password, role, resume)
        VALUES (?, ?, ?, ?, ?, ?)''',
        (username, email, city, hashed_pw, 'recruiter', resume_filename)
    )
    conn.commit()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    conn.close()

    session['username'] = username
    session['role'] = 'recruiter'
    session['user_id'] = user['id']
    flash("Registered successfully!", "success")
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['username'] = user['username']
            session['role'] = user['role']
            session['user_id'] = user['id']
            flash("Login successful!", "success")
            return redirect(url_for('dashboard'))
        flash("Invalid credentials.", "danger")
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    session.clear()
    flash("Logged out.", "info")
    return redirect(url_for('home'))

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (session['username'],)).fetchone()

    if session['role'] == 'student':
        jobs = conn.execute("SELECT * FROM jobs ORDER BY id DESC").fetchall()
        conn.close()
        return render_template('student_dashboard.html', user=user, jobs=jobs)

    if session['role'] == 'recruiter':
        # fetch jobs posted by this recruiter (by recruiter_id)
        jobs = conn.execute("SELECT * FROM jobs WHERE recruiter_id = ? ORDER BY id DESC", (user['id'],)).fetchall()
        applicants = conn.execute('''
            SELECT a.*, j.title AS job_title, u.username as recruiter_username
            FROM applications a
            JOIN jobs j ON a.job_id = j.id
            JOIN users u ON j.recruiter_id = u.id
            WHERE j.recruiter_id = ?
            ORDER BY a.application_date DESC
        ''', (user['id'],)).fetchall()
        conn.close()
        return render_template('recruiter_dashboard.html', user=user, jobs=jobs, applicants=applicants)

@app.route('/post_job', methods=['GET', 'POST'])
@login_required
@role_required('recruiter')
def post_job():
    if request.method == 'POST':
        title = request.form.get('job_title', '').strip()
        description = request.form.get('description', '').strip()
        company = request.form.get('company_name', '').strip()
        company_description = request.form.get('company_description', '').strip()
        location = request.form.get('location', '').strip()
        job_type = request.form.get('job_type', '').strip()
        salary = request.form.get('salary', '').strip()
        interview_date = request.form.get('interview_date', '').strip()
        interview_time = request.form.get('interview_time', '').strip()
        interview_place = request.form.get('interview_place', '').strip()

        recruiter_id = session.get('user_id')
        posted_by = session.get('username')

        if recruiter_id is None:
            flash("Recruiter not recognized — please log in again.", "danger")
            return redirect(url_for('login'))

        if not title or not description or not location:
            flash("❌ Please fill all required fields.", "warning")
            return redirect(url_for('post_job'))

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            INSERT INTO jobs (
                recruiter_id, title, company, company_description, location, job_type,
                salary, description, interview_date, interview_time, interview_place, posted_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            recruiter_id, title, company, company_description, location, job_type,
            salary, description, interview_date, interview_time, interview_place, posted_by
        ))
        conn.commit()
        job_id = cur.lastrowid
        job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        conn.close()

        # show confirmation/preview
        return render_template('job_posted.html', job=job)

    return render_template('post_job.html')

@app.route('/job_posted/<int:job_id>')
@login_required
@role_required('recruiter')
def job_posted(job_id):
    conn = get_db_connection()
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    conn.close()

    if not job:
        flash("Job not found.", "danger")
        return redirect(url_for('dashboard'))

    return render_template('job_posted.html', job=job)

@app.route('/apply_job/<int:job_id>', methods=['GET', 'POST'])
@login_required
@role_required('student')
def apply_job(job_id):
    conn = get_db_connection()
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()

    if not job:
        flash("Job not found.", "danger")
        conn.close()
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        already = conn.execute(
            "SELECT 1 FROM applications WHERE job_id = ? AND student_name = ?",
            (job_id, session['username'])
        ).fetchone()
        if already:
            flash("You've already applied to this job.", "info")
            conn.close()
            return redirect(url_for('dashboard'))

        # fetch user details safely
        user_row = conn.execute(
            "SELECT resume, email, city FROM users WHERE username = ?",
            (session['username'],)
        ).fetchone()

        resume = user_row['resume'] if user_row and 'resume' in user_row.keys() else None
        email = user_row['email'] if user_row and 'email' in user_row.keys() else None
        city = user_row['city'] if user_row and 'city' in user_row.keys() else None

        conn.execute('''
            INSERT INTO applications (
                job_id, student_id, student_name, job_preference, application_date, resume, email, city, company, job_title
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job_id,
            session.get('user_id'),
            session.get('username'),
            request.form.get('job_preference'),
            datetime.now(pytz.timezone("Asia/Kolkata")).strftime("%Y-%m-%d %H:%M"),
            resume,
            email,
            city,
            job['company'],
            job['title']
        ))

        conn.commit()
        conn.close()

        # send confirmation email
        if email:
            try:
                msg = Message(
                    subject="Application Submitted",
                    recipients=[email]
                )
                msg.body = (
                    f"You've successfully applied for '{job['title']}' at {job['company']}.\n"
                    f"Interview: {job['interview_date']} {job['interview_time']}\n"
                    f"Venue: {job['interview_place']}\n\nGood luck!"
                )
                mail.send(msg)
            except Exception as e:
                print("Email send failed:", e)

        return render_template('apply_confirmation.html', job=job)

    # recruiter lookup
    recruiter = None
    if job['recruiter_id']:
        recruiter = conn.execute("SELECT * FROM users WHERE id = ?", (job['recruiter_id'],)).fetchone()
    elif job['posted_by']:
        recruiter = conn.execute("SELECT * FROM users WHERE username = ?", (job['posted_by'],)).fetchone()

    conn.close()
    return render_template('apply_job.html', job=job, recruiter=recruiter)

@app.route('/profile')
@login_required
def profile():
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (session['username'],)).fetchone()
    conn.close()

    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('dashboard'))

    if user['role'] == 'student':
        return render_template('profile_student.html', user=user)
    elif user['role'] == 'recruiter':
        return render_template('profile_recruiter.html', user=user)
    else:
        flash("Unknown role.", "danger")
        return redirect(url_for('dashboard'))

@app.route('/student/profile')
@login_required
@role_required('student')
def student_profile():
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    conn.close()

    if not user:
        flash("User not found.", "danger")
        return redirect(url_for('dashboard'))

    return render_template('profile_student.html', user=user)

@app.route('/profile/recruiter')
@login_required
@role_required('recruiter')
def profile_recruiter():
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (session['username'],)).fetchone()
    conn.close()
    return render_template('profile_recruiter.html', user=user)

@app.route('/edit_student_profile', methods=['GET', 'POST'])
@login_required
@role_required('student')
def edit_student_profile():
    user_id = session['user_id']
    conn = get_db_connection()
    cursor = conn.cursor()

    user = cursor.execute("SELECT * FROM users WHERE id = ? AND role = 'student'", (user_id,)).fetchone()
    if not user:
        conn.close()
        flash("User not found.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        # collect fields (use .get with defaults so missing form fields won't crash)
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        country = request.form.get('country', '').strip()
        university = request.form.get('university', '').strip()
        degree = request.form.get('degree', '').strip()
        graduation_year = request.form.get('graduation_year', '').strip()
        job_preference = request.form.get('job_preference', '').strip()
        bio = request.form.get('bio', '').strip()

        resume_file = request.files.get('resume')
        resume_filename = user['resume'] if user and 'resume' in user.keys() else None

        if resume_file and resume_file.filename:
            filename = secure_filename(resume_file.filename)
            resume_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            resume_file.save(resume_path)
            resume_filename = filename

        cursor.execute('''
            UPDATE users SET
                email = ?, phone = ?, city = ?, state = ?, country = ?,
                university = ?, degree = ?, graduation_year = ?,
                job_preference = ?, bio = ?, resume = ?
            WHERE id = ? AND role = 'student'
        ''', (
            email, phone, city, state, country,
            university, degree, graduation_year,
            job_preference, bio, resume_filename, user_id
        ))

        conn.commit()
        conn.close()
        flash('Profile updated successfully!', 'success')
        return redirect(url_for('student_profile'))

    conn.close()
    return render_template('edit_student_profile.html', user=user)

@app.route('/edit_recruiter_profile', methods=['GET', 'POST'])
@login_required
@role_required('recruiter')
def edit_recruiter_profile():
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (session['username'],)).fetchone()
    if not user:
        conn.close()
        flash("User not found.", "danger")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        city = request.form.get('city', '').strip()
        state = request.form.get('state', '').strip()
        country = request.form.get('country', '').strip()
        company = request.form.get('company', '').strip()
        website = request.form.get('website', '').strip()
        linkedin = request.form.get('linkedin', '').strip()
        bio = request.form.get('bio', '').strip()

        resume_file = request.files.get('resume')
        resume_filename = user['resume'] if 'resume' in user.keys() else None
        if resume_file and resume_file.filename:
            resume_filename = secure_filename(f"{user['username']}_{resume_file.filename}")
            resume_file.save(os.path.join(app.config['UPLOAD_FOLDER'], resume_filename))

        conn.execute('''
            UPDATE users SET
                email = ?, phone = ?, city = ?, state = ?, country = ?,
                company = ?, website = ?, linkedin = ?, bio = ?, resume = ?
            WHERE id = ? AND role = 'recruiter'
        ''', (
            email, phone, city, state, country,
            company, website, linkedin, bio, resume_filename, user['id']
        ))

        conn.commit()
        conn.close()
        flash('Recruiter profile updated successfully!', 'success')
        return redirect(url_for('profile'))

    conn.close()
    return render_template('edit_recruiter_profile.html', user=user)

@app.route('/generate_pdf')
@login_required
def generate_pdf():
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE username = ?", (session['username'],)).fetchone()
    conn.close()

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=16)
    pdf.cell(200, 10, txt="User Profile", ln=True, align="C")
    pdf.set_font("Arial", size=12)
    pdf.ln(10)

    for key in ['username', 'email', 'city', 'role', 'job_preference']:
        if key in user.keys() and user[key]:
            pdf.cell(200, 10, txt=f"{key.title()}: {user[key]}", ln=True)

    pdf_filename = f"{user['username']}_profile.pdf"
    pdf_path = os.path.join(PDF_FOLDER, pdf_filename)
    pdf.output(pdf_path)

    if not os.path.exists(pdf_path):
        flash("PDF could not be generated.", "danger")
        return redirect(url_for('profile'))

    return send_from_directory(PDF_FOLDER, pdf_filename, as_attachment=True)

@app.route('/download_resume/<filename>')
@login_required
def download_resume(filename):
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    if not os.path.exists(file_path):
        flash("Resume file not found.", "danger")
        return redirect(url_for('profile'))
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename, as_attachment=True)

@app.route('/view_applicant_profile/<int:application_id>')
@login_required
@role_required('recruiter')
def view_applicant_profile(application_id):
    conn = get_db_connection()
    application = conn.execute("SELECT * FROM applications WHERE id = ?", (application_id,)).fetchone()
    if not application:
        conn.close()
        flash("Application not found.", "danger")
        return redirect(url_for('dashboard'))

    student = conn.execute("SELECT * FROM users WHERE username = ?", (application['student_name'],)).fetchone()
    job = conn.execute("SELECT title FROM jobs WHERE id = ?", (application['job_id'],)).fetchone()
    conn.close()

    resume_exists = bool(student and student['resume'] and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], student['resume'])))

    return render_template('view_applicant_profile.html', application=application, student=student, student_job=(job['title'] if job else ''), resume_exists=resume_exists)

@app.route('/remove_job/<int:job_id>', methods=['POST'])
@login_required
@role_required('recruiter')
def remove_job(job_id):
    conn = get_db_connection()
    job = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not job:
        conn.close()
        flash("Job not found.", "danger")
        return redirect(url_for('dashboard'))

    # allow removal by recruiter_id matching session user_id
    if job['recruiter_id'] != session.get('user_id'):
        conn.close()
        flash("You do not have permission to remove this job.", "danger")
        return redirect(url_for('dashboard'))

    conn.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()
    flash("Job removed successfully!", "success")
    return redirect(url_for('dashboard'))

# Auto-run / start
def open_browser():
    webbrowser.open_new("http://127.0.0.1:5000/")

if __name__ == '__main__':
    init_db()
    threading.Timer(1, open_browser).start()
    app.run(debug=True)
