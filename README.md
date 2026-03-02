# KryptoBlog

A minimal, terminal-styled blog engine built with Flask and SQLite, designed specifically for offensive security professionals and HackTheBox (HTB) players. 

KryptoBlog allows you to write your machine walkthroughs in pure Markdown and protect them using the machine's root flag as the decryption passphrase. It ensures your writeups remain private until a reader has genuinely rooted the box themselves.

## Features

* **Flag-Protected Posts:** Lock specific posts behind a passphrase (e.g., an HTB root flag). Passwords are hashed using `pbkdf2:sha256` so plaintext flags are never stored in the database.
* **Public/Private Toggling:** Publish general thoughts or tutorials publicly while keeping your machine writeups encrypted.
* **Sessionless Security:** Refreshing the page immediately re-locks an encrypted post. No session cookies are stored for viewing writeups, ensuring maximum OPSEC.
* **Markdown Native:** Write in standard Markdown. Code blocks and syntax highlighting are fully supported.
* **Automated Image Handling:** Upload bulk screenshots via the admin panel. The engine automatically renames them (`slug-img-id.ext`) and rewrites the image links inside your Markdown file on the fly.
* **White-Label Configuration:** Site title, author, and versioning are driven by a simple `config.json` file.
* **Terminal Aesthetic:** Clean, minimal, dark-mode CSS designed for readability and a hacker aesthetic.

---

## Architecture & Directory Structure

* **Backend:** Python 3 + Flask + Werkzeug
* **Database:** SQLite3 (`kryptoblog.db`)
* **Content:** Raw `.md` files stored on disk in the `contents/` directory.

```text
kryptoblog/
├── app.py                  # Main Flask application and routing
├── init_db.py              # Database initialization script
├── config.json             # Site metadata (name, author, etc.)
├── .env                    # Environment variables (secrets, admin pass)
├── requirements.txt        # Python dependencies
├── contents/               # Markdown files are saved here
│   └── images/             # Uploaded screenshots are stored here
├── static/
│   └── style.css           # Terminal aesthetic stylesheet
└── templates/              # HTML Jinja2 templates (base, index, admin, etc.)```