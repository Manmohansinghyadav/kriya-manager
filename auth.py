import psycopg2
import streamlit as st

# YAHAN APNA SUPABASE URI PASTE KAREIN (Password ke sath)
DB_URL = "postgresql://postgres.xxxxxxxxxx:w6kZMpAgoI9Wc3JD@aws-0-ap-south-1.pooler.supabase.com:6543/postgres"

def get_conn():
    return psycopg2.connect(DB_URL)

def init_auth_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    ''')
    c.execute('SELECT COUNT(*) FROM users')
    if c.fetchone()[0] == 0:
        c.execute("INSERT INTO users (username, password, role) VALUES (%s, %s, %s)", ('admin', 'admin123', 'Admin'))
    conn.commit()
    conn.close()

def authenticate(username, password):
    conn = get_conn()
    c = conn.cursor()
    c.execute('SELECT role FROM users WHERE username=%s AND password=%s', (username, password))
    result = c.fetchone()
    conn.close()
    if result:
        return True, result[0]
    return False, None

def register_user(username, password, role):
    try:
        conn = get_conn()
        c = conn.cursor()
        c.execute('INSERT INTO users (username, password, role) VALUES (%s, %s, %s)', (username, password, role))
        conn.commit()
        conn.close()
        return True, f"User '{username}' successfully registered!"
    except psycopg2.IntegrityError:
        return False, f"Username '{username}' already exists. Kripya doosra naam chunein."

def reset_password(username, new_password):
    conn = get_conn()
    c = conn.cursor()
    c.execute('UPDATE users SET password=%s WHERE username=%s', (new_password, username))
    rowcount = c.rowcount
    conn.commit()
    conn.close()
    if rowcount > 0:
        return True, f"Password for '{username}' successfully reset!"
    return False, f"User '{username}' nahi mila!"

def get_all_usernames():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT username FROM users WHERE role='Customer'")
    users = [row[0] for row in c.fetchall()]
    conn.close()
    return users