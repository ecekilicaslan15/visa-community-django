# VisaCommunity

A Django site where people from Türkiye share Schengen visa experiences and questions, country by country. The interface is in English.

Official charts use the European Commission’s 2025 short-stay figures. Community charts are counted from posts on this site. Neither one is a prediction for a single application.

## Features

- Sign up with email, sign in with a username or email, reset a password, edit a profile, and delete an account
- Country pages for questions and experiences, with replies and helpful marks
- Reports of appointment openings, and a community outlook for the next window
- 2025 refusal rates by country and consulate, the cascade-rule helper, and community appointment gaps
- Motivation-letter and sponsorship-letter guides, with examples in English and Turkish and a draft that stays in the browser
- Reporting a post, staff removal, and a limit of 10 new posts per user per hour
- Guidelines, privacy, and contact pages

## Tech stack

Python, Django 6.1, SQLite, WhiteNoise, and Gunicorn. Pages are server-rendered HTML and CSS.

## Run it locally

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_countries   # all 27 Schengen countries; safe to re-run
python manage.py load_visa_stats  # official 2025 figures; safe to re-run
python manage.py createsuperuser  # optional, for /admin
python manage.py runserver
```

Open http://127.0.0.1:8000/. Password-reset messages are printed in the terminal unless you set a real email backend.

You do not need a `.env` file for this. `DEBUG` stays on, and a local secret key is used only in that mode.

## Environment variables

Copy `.env.example` to `.env` when you want to override something. Values already set in the process are kept, so a host’s environment wins over the file. Do not commit `.env`.

| Variable | Local default | Production |
| --- | --- | --- |
| `DEBUG` | `True` | `False` |
| `SECRET_KEY` | a local fallback while `DEBUG` is on | required, long and random |
| `ALLOWED_HOSTS` | empty (localhost is allowed) | your domain, comma-separated |
| `CSRF_TRUSTED_ORIGINS` | empty | `https://` origins, comma-separated |
| `EMAIL_BACKEND` | console | your provider’s SMTP backend |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | unused while mail is printed to the console | your SMTP account |
| `DEFAULT_FROM_EMAIL` | `VisaCommunity <noreply@localhost>` | an address you control |

With `DEBUG=False` the site redirects to HTTPS, marks session and CSRF cookies secure, sends HSTS, and trusts `X-Forwarded-Proto` from the proxy. Static files are collected into `staticfiles/` and served by WhiteNoise.

Generate a secret key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Starting with `DEBUG=False` and no `SECRET_KEY` stops immediately instead of using the local key.

## Tests

```bash
python manage.py check
python manage.py makemigrations --check
python manage.py test
```

The deploy check needs production values. It should print no security warnings:

```bash
DEBUG=False \
SECRET_KEY="$(python -c "import secrets; print(secrets.token_urlsafe(50))")" \
ALLOWED_HOSTS=visacommunity.example \
CSRF_TRUSTED_ORIGINS=https://visacommunity.example \
python manage.py check --deploy
```

## Deploy

SQLite is the database (`db.sqlite3`). It has to live on a disk that survives a restart. Collect static files before the app serves traffic:

```bash
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py seed_countries
python manage.py load_visa_stats
```

Set `DEBUG=False`, `SECRET_KEY`, `ALLOWED_HOSTS`, and `CSRF_TRUSTED_ORIGINS` in the host’s environment. Add SMTP variables if password reset should send real email.

### Render

1. Push the repository and create a Web Service from it. Choose the Python runtime.
2. Build command:

   ```bash
   pip install -r requirements.txt && python manage.py collectstatic --noinput
   ```

3. Start command:

   ```bash
   gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
   ```

4. Add a persistent disk and keep `db.sqlite3` on that disk. Render’s default filesystem is replaced on deploy, and a database stored only there is wiped.
5. Set the environment variables. `ALLOWED_HOSTS` is the service hostname. `CSRF_TRUSTED_ORIGINS` is `https://` plus that hostname.
6. Open the shell and run `migrate`, `seed_countries`, and `load_visa_stats` once the disk is mounted. Create an admin user with `createsuperuser` if you want `/admin`.

### PythonAnywhere

1. Open a Bash console, clone the repository, and create a virtualenv with Python 3.12 or newer.
2. `pip install -r requirements.txt`, then `migrate`, `seed_countries`, `load_visa_stats`, and `collectstatic --noinput`.
3. Add a new web app. Point it at the virtualenv. In the WSGI file, set the environment before Django loads, then expose `application` from `config.wsgi`:

   ```python
   import os
   import sys

   path = "/home/USERNAME/visa-community-django"
   if path not in sys.path:
       sys.path.insert(0, path)

   os.environ.setdefault("DEBUG", "False")
   os.environ.setdefault("SECRET_KEY", "paste-a-long-random-key")
   os.environ.setdefault("ALLOWED_HOSTS", "USERNAME.pythonanywhere.com")
   os.environ.setdefault("CSRF_TRUSTED_ORIGINS", "https://USERNAME.pythonanywhere.com")

   from config.wsgi import application  # noqa: E402
   ```

4. Reload the web app. WhiteNoise serves `/static/` from `staticfiles/`. The SQLite file stays in the project directory, which PythonAnywhere keeps.
