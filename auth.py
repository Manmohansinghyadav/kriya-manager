import sqlite3
import streamlit as st

DB_FILE = 'kriya_database.db'

def init_auth_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    # Users table banayenge jisme login details save hongi
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    ''')
    
    # Agar database mein koi user nahi hai, toh ek default Admin bana denge
    c.execute('SELECT COUNT(*) FROM users')
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', ('admin', 'admin@1234321', 'Admin'))
    
    conn.commit()
    conn.close()

def authenticate(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT role FROM users WHERE username=? AND password=?', (username, password))
    result = c.fetchone()
    conn.close()
    if result:
        return True, result[0] # Returns (True, Role)
    return False, None

def register_user(username, password, role):
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # Naya user insert karenge
        c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)', (username, password, role))
        conn.commit()
        conn.close()
        return True, f"User '{username}' successfully registered!"
    except sqlite3.IntegrityError:
        # Agar username pehle se exist karta hai
        return False, f"Username '{username}' already exists. Kripya doosra naam chunein."

def reset_password(username, new_password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE users SET password=? WHERE username=?', (new_password, username))
    rowcount = c.rowcount
    conn.commit()
    conn.close()
    if rowcount > 0:
        return True, f"Password for '{username}' successfully reset!"
    return False, f"User '{username}' nahi mila!"

def get_all_usernames():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE role='Customer'")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users