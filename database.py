# database.py
import sqlite3
import bcrypt

DB_NAME = "SQLOpt_prod.db"

def init_db():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        password TEXT NOT NULL,
        admin BOOLEAN DEFAULT 0
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS query_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT NOT NULL,
        task_type TEXT NOT NULL,
        query_length INTEGER NOT NULL,
        tokens_used INTEGER,
        success BOOLEAN NOT NULL,
        error_message TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_email) REFERENCES users(email)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS query_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_email TEXT NOT NULL,
        query_text TEXT NOT NULL,
        task_type TEXT NOT NULL,
        result_text TEXT,
        is_favorite BOOLEAN DEFAULT 0,
        query_name TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_email) REFERENCES users(email)
    )
    ''')

    conn.commit()
    return conn, cursor


def add_user(cursor, conn, email, name, password, is_admin=False):
    hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    cursor.execute('INSERT INTO users (email, name, password, admin) VALUES (?, ?, ?, ?)',
                   (email, name, hashed_password, is_admin))
    conn.commit()


def get_user(cursor, email):
    cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
    return cursor.fetchone()


def verify_password(stored_password, provided_password):
    return bcrypt.checkpw(provided_password.encode(), stored_password.encode())


def log_query(cursor, conn, user_email, task_type, query_length, tokens_used=None, success=True, error_message=None):
    cursor.execute('''
        INSERT INTO query_logs (user_email, task_type, query_length, tokens_used, success, error_message)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_email, task_type, query_length, tokens_used, success, error_message))
    conn.commit()


def save_query_to_history(cursor, conn, user_email, query_text, task_type, result_text=None, query_name=None):
    cursor.execute('''
        INSERT INTO query_history (user_email, query_text, task_type, result_text, query_name)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_email, query_text, task_type, result_text, query_name))
    conn.commit()
    return cursor.lastrowid


def get_user_query_history(cursor, user_email, limit=50):
    cursor.execute('''
        SELECT id, query_text, task_type, result_text, is_favorite, query_name, timestamp
        FROM query_history WHERE user_email = ?
        ORDER BY timestamp DESC LIMIT ?
    ''', (user_email, limit))
    return cursor.fetchall()


def get_user_favorites(cursor, user_email):
    cursor.execute('''
        SELECT id, query_text, task_type, result_text, query_name, timestamp
        FROM query_history WHERE user_email = ? AND is_favorite = 1
        ORDER BY timestamp DESC
    ''', (user_email,))
    return cursor.fetchall()


def toggle_favorite(cursor, conn, query_id):
    cursor.execute('SELECT is_favorite FROM query_history WHERE id = ?', (query_id,))
    current_status = cursor.fetchone()[0]
    new_status = 0 if current_status else 1
    cursor.execute('UPDATE query_history SET is_favorite = ? WHERE id = ?', (new_status, query_id))
    conn.commit()
    return new_status


def delete_query_from_history(cursor, conn, query_id, user_email):
    cursor.execute('DELETE FROM query_history WHERE id = ? AND user_email = ?', (query_id, user_email))
    conn.commit()
    return cursor.rowcount > 0


def update_query_name(cursor, conn, query_id, user_email, new_name):
    cursor.execute('UPDATE query_history SET query_name = ? WHERE id = ? AND user_email = ?',
                   (new_name, query_id, user_email))
    conn.commit()
    return cursor.rowcount > 0
