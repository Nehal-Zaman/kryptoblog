import sqlite3
import glob
import json
import os
import re
import markdown
from flask import Flask, render_template, request, redirect, url_for, session, abort
from flask import send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

from dotenv import load_dotenv
load_dotenv()

BASE_DIR = 'contents'
IMAGE_DIR = os.path.join(BASE_DIR, 'images')
os.makedirs(IMAGE_DIR, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET_KEY", "")
app.config['ADMIN_PASSWORD'] = os.environ.get("ADMIN_PASSWORD", "")

def get_db_connection():
    conn = sqlite3.connect('kryptoblog.db')
    conn.row_factory = sqlite3.Row
    return conn

def get_markdown_content(slug):
    filepath = os.path.join(BASE_DIR, f'{slug}.md')
    if not os.path.exists(filepath):
        abort(404)
    with open(filepath, 'r') as f:
        return markdown.markdown(f.read(), extensions=['fenced_code', 'codehilite'])
    
@app.context_processor
def inject_config():
    try:
        with open('config.json', 'r') as f:
            config_data = json.load(f)
    except FileNotFoundError:
        config_data = {"site_name": "Hacker Blog", "site_version": "v1.0"}
    return dict(site_config=config_data)

@app.route('/')
def index():
    conn = get_db_connection()

    posts = conn.execute('SELECT slug, title, is_encrypted FROM posts ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('index.html', posts=posts)

@app.route('/post/<slug>', methods=['GET', 'POST'])
def view_post(slug):
    conn = get_db_connection()
    post = conn.execute('SELECT * FROM posts WHERE slug = ?', (slug,)).fetchone()
    conn.close()

    if post is None:
        abort(404)

    if not post['is_encrypted']:
        content = get_markdown_content(slug)
        return render_template('post.html', content=content, title=post['title'])

    if request.method == 'POST':
        passphrase = request.form.get('passphrase')
        if check_password_hash(post['passphrase_hash'], passphrase):
            content = get_markdown_content(slug)
            return render_template('post.html', content=content, title=post['title'])
        else:
            return render_template('auth.html', slug=slug, error="Invalid flag. Try harder!")

    return render_template('auth.html', slug=slug, error=None)

@app.route('/contents/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(os.path.join('contents', 'images'), filename)

@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if not session.get('is_admin'):
        if request.method == 'POST':
            password_attempt = request.form.get('admin_pass')
            if password_attempt == app.config['ADMIN_PASSWORD']:
                session['is_admin'] = True
                return redirect(url_for('admin'))
            else:
                return render_template('admin.html', error="Invalid admin password.")
        return render_template('admin.html')

    if request.method == 'POST' and 'logout' in request.form:
        session.pop('is_admin', None)
        return redirect(url_for('index'))

    message = None

    if request.method == 'POST' and 'delete_post' in request.form:
        slug_to_delete = request.form.get('slug_to_delete')
        if slug_to_delete:
            conn = get_db_connection()
            conn.execute('DELETE FROM posts WHERE slug = ?', (slug_to_delete,))
            conn.commit()
            conn.close()

            md_path = os.path.join(BASE_DIR, f'{slug_to_delete}.md')
            if os.path.exists(md_path):
                os.remove(md_path)

            image_pattern = os.path.join(IMAGE_DIR, f'{slug_to_delete}-img-*.*')
            for img_file in glob.glob(image_pattern):
                os.remove(img_file)

            message = f"[*] Purged: '{slug_to_delete}' and all associated files."

    elif request.method == 'POST' and 'add_post' in request.form:
        slug = request.form.get('slug')
        title = request.form.get('title')
        flag = request.form.get('flag')
        
        is_encrypted = 1 if request.form.get('is_encrypted') else 0
        
        markdown_content = ""
        uploaded_md = request.files.get('markdown_file')
        if uploaded_md and uploaded_md.filename != '':
            markdown_content = uploaded_md.read().decode('utf-8')
        else:
            markdown_content = request.form.get('markdown_text', '')

        if slug and title and markdown_content.strip():
            if is_encrypted and not flag:
                message = "[-] Error: Encrypted posts require a root flag."
            else:
                images = request.files.getlist('images')
                img_id = 1
                
                for img in images:
                    if img and img.filename:
                        original_filename = secure_filename(img.filename)
                        ext = os.path.splitext(original_filename)[1].lower()
                        
                        if ext in ['.png', '.jpg', '.jpeg', '.gif']:
                            new_filename = f"{slug}-img-{img_id}{ext}"
                            img_path = os.path.join(IMAGE_DIR, new_filename)
                            img.save(img_path)
                            
                            pattern = r'(!\[.*?\])\([^)]*' + re.escape(original_filename) + r'\)'
                            replacement = r'\1(/' + IMAGE_DIR.replace('\\', '/') + '/' + new_filename + ')'
                            markdown_content = re.sub(pattern, replacement, markdown_content)
                            
                            img_id += 1

                hashed_flag = generate_password_hash(flag, method='pbkdf2:sha256') if is_encrypted else ""
                
                conn = get_db_connection()
                try:
                    conn.execute('''
                        INSERT INTO posts (slug, title, passphrase_hash, is_encrypted)
                        VALUES (?, ?, ?, ?)
                    ''', (slug, title, hashed_flag, is_encrypted))
                    conn.commit()
                    
                    file_path = os.path.join(BASE_DIR, f'{slug}.md')
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                        
                    message = f"[*] Success: '{title}' added. Processed {img_id - 1} images."
                except sqlite3.IntegrityError:
                    message = "[-] Error: A writeup with that slug already exists."
                finally:
                    conn.close()
        else:
            message = "[-] Error: Slug, Title, and Markdown content are required."

    conn = get_db_connection()
    posts = conn.execute('SELECT slug, title, is_encrypted FROM posts ORDER BY id DESC').fetchall()
    conn.close()

    return render_template('admin.html', message=message, posts=posts)

@app.route('/admin/edit/<slug>', methods=['GET', 'POST'])
def edit_post(slug):
    if not session.get('is_admin'):
        return redirect(url_for('admin'))

    conn = get_db_connection()
    post = conn.execute('SELECT * FROM posts WHERE slug = ?', (slug,)).fetchone()
    
    if post is None:
        conn.close()
        abort(404)

    message = None

    if request.method == 'POST':
        title = request.form.get('title')
        flag = request.form.get('flag')
        is_encrypted = 1 if request.form.get('is_encrypted') else 0
        
        markdown_content = ""
        uploaded_md = request.files.get('markdown_file')
        if uploaded_md and uploaded_md.filename != '':
            markdown_content = uploaded_md.read().decode('utf-8')
        else:
            markdown_content = request.form.get('markdown_text', '')

        if title and markdown_content.strip():
            images = request.files.getlist('images')
            existing_images = glob.glob(os.path.join(IMAGE_DIR, f'{slug}-img-*.*'))
            img_id = len(existing_images) + 1
            
            for img in images:
                if img and img.filename:
                    original_filename = secure_filename(img.filename)
                    ext = os.path.splitext(original_filename)[1].lower()
                    if ext in ['.png', '.jpg', '.jpeg', '.gif']:
                        new_filename = f"{slug}-img-{img_id}{ext}"
                        img_path = os.path.join(IMAGE_DIR, new_filename)
                        img.save(img_path)
                        
                        pattern = r'(!\[.*?\])\([^)]*' + re.escape(original_filename) + r'\)'
                        replacement = r'\1(/' + IMAGE_DIR.replace('\\', '/') + '/' + new_filename + ')'
                        markdown_content = re.sub(pattern, replacement, markdown_content)
                        img_id += 1

            hashed_flag = post['passphrase_hash']
            if is_encrypted and flag:
                hashed_flag = generate_password_hash(flag, method='pbkdf2:sha256')
            elif not is_encrypted:
                hashed_flag = ""

            conn.execute('''
                UPDATE posts 
                SET title = ?, passphrase_hash = ?, is_encrypted = ?
                WHERE slug = ?
            ''', (title, hashed_flag, is_encrypted, slug))
            conn.commit()

            file_path = os.path.join(BASE_DIR, f'{slug}.md')
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(markdown_content)

            message = f"[*] Success: '{title}' updated successfully."
            post = conn.execute('SELECT * FROM posts WHERE slug = ?', (slug,)).fetchone()
        else:
            message = "[-] Error: Title and Markdown content are required."

    conn.close()

    md_path = os.path.join(BASE_DIR, f'{slug}.md')
    existing_md = ""
    if os.path.exists(md_path):
        with open(md_path, 'r', encoding='utf-8') as f:
            existing_md = f.read()

    return render_template('edit.html', post=post, existing_md=existing_md, message=message)

if __name__ == '__main__':
    app.run(debug=True)