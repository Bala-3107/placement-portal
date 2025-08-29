import os
from models import init_db  # Import your init_db function

DB_NAME = 'database.db'

if os.path.exists(DB_NAME):
    os.remove(DB_NAME)
    print(f"{DB_NAME} removed.")

init_db()
print("Database initialized.")
