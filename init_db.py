import sqlite3
from werkzeug.security import generate_password_hash

def init_db():
    connection = sqlite3.connect('kryptoblog.db')
    cursor = connection.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            title TEXT NOT NULL,
            passphrase_hash TEXT NOT NULL,
            is_encrypted INTEGER DEFAULT 1
        )
    ''')

    test_slug = 'compiled-htb'
    test_title = 'Compiled HTB Writeup'
    test_hash = generate_password_hash('root_flag_here', method='pbkdf2:sha256')

    cursor.execute('''
        INSERT OR IGNORE INTO posts (slug, title, passphrase_hash, is_encrypted)
        VALUES (?, ?, ?, ?)
    ''', (test_slug, test_title, test_hash, 1))

    connection.commit()
    connection.close()
    print("[*] Database initialized successfully with 'is_encrypted' support.")

if __name__ == '__main__':
    init_db()