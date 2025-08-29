import sqlite3

def update_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    try:
        # Add 'resume' column to users table if not exists
        cursor.execute("ALTER TABLE users ADD COLUMN resume TEXT")
        print("✅ Column 'resume' added successfully.")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print("⚠️ Column 'resume' already exists.")
        else:
            print("❌ Error during schema update:", e)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    update_db()
