# VisaCommunity

A Django site where people from Türkiye share Schengen visa experiences and questions, country by country. The interface is in English.

Official charts use the European Commission’s 2025 short-stay figures. Community charts are counted from posts on this site. Neither one is a prediction for a single application.

## Features

- Sign up with email, confirm the address before posting, sign in with a username or email, reset a password, edit a profile, and delete an account
- Country pages for questions and experiences, with replies and helpful marks
- Reports of appointment openings, and a community outlook for the next window
- 2025 refusal rates by country and consulate, the cascade-rule helper, and community appointment gaps
- Motivation-letter and sponsorship-letter guides, with examples in English and Turkish and a draft that stays in the browser
- Reporting a post, staff removal, and a limit of 10 new posts per user per hour
- Guidelines, a privacy notice, a JSON download of your own data, and a contact page

## Tech stack

Python, Django 6.1, SQLite locally and PostgreSQL in production, WhiteNoise, and Gunicorn. Pages are server-rendered HTML and CSS.

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

Open http://127.0.0.1:8000/. Confirmation and password-reset messages are printed in the terminal unless you set a real email backend.

You do not need a `.env` file for this. `DEBUG` stays on, and a local secret key is used only in that mode.

## Environment variables

Copy `.env.example` to `.env` when you want to override something. Values already set in the process are kept, so a host’s environment wins over the file. Do not commit `.env`.

| Variable | Local default | Production |
| --- | --- | --- |
| `DEBUG` | `True` | `False` |
| `SECRET_KEY` | a local fallback while `DEBUG` is on | required, long and random |
| `ALLOWED_HOSTS` | empty (localhost is allowed) | your domain, comma-separated |
| `CSRF_TRUSTED_ORIGINS` | empty | `https://` origins, comma-separated |
| `DATABASE_URL` | unset (SQLite file `db.sqlite3`) | Postgres URL from the host |
| `EMAIL_BACKEND` | console | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS` | unused while mail is printed to the console | your SMTP account |
| `DEFAULT_FROM_EMAIL` | `VisaCommunity <noreply@localhost>` | an address the provider lets you send from |

With `DEBUG=False` the site redirects to HTTPS, marks session and CSRF cookies secure, sends HSTS, and trusts `X-Forwarded-Proto` from the proxy. Static files are collected into `staticfiles/` and served by WhiteNoise.

Generate a secret key with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(50))"
```

Starting with `DEBUG=False` and no `SECRET_KEY` stops immediately instead of using the local key.

## Email

Leave `EMAIL_BACKEND` on the console backend while you develop. The message, including the confirmation or reset link, is printed in the `runserver` terminal.

For a real inbox, set `EMAIL_BACKEND` to `django.core.mail.backends.smtp.EmailBackend`, `EMAIL_USE_TLS` to `True`, and `EMAIL_PORT` to `587`. Each message is sent as plain text and as HTML in the site’s colours.

**Brevo (free SMTP).** Create an account, verify a sender, and open SMTP & API. Use host `smtp-relay.brevo.com`, the SMTP login as `EMAIL_HOST_USER`, and the SMTP key as `EMAIL_HOST_PASSWORD`. Set `DEFAULT_FROM_EMAIL` to that verified sender.

**Resend (free SMTP).** Create an API key. Use host `smtp.resend.com`, `EMAIL_HOST_USER` `resend`, and the API key as `EMAIL_HOST_PASSWORD`. `DEFAULT_FROM_EMAIL` has to be on a domain you verified in Resend, or their onboarding address while you are testing.

**Gmail.** Turn on 2-Step Verification, then create an app password (Google Account → Security → App passwords). Use host `smtp.gmail.com`, your full Gmail address as `EMAIL_HOST_USER`, and the 16-character app password as `EMAIL_HOST_PASSWORD`. Do not use your normal Gmail password. Google’s free sending limit is low, so this is fine for a small site and a poor fit for a busy one.

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

Locally the database is SQLite (`db.sqlite3`). In production set `DATABASE_URL` to a PostgreSQL URL. Collect static files before the app serves traffic:

```bash
python manage.py collectstatic --noinput
python manage.py migrate
python manage.py seed_countries
python manage.py load_visa_stats
python manage.py createsuperuser
```

Set `DEBUG=False`, `SECRET_KEY`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and `DATABASE_URL` in the host’s environment. Add the SMTP variables from the email section so confirmation and password reset leave the server.

### Render

1. Push the repository and create a Web Service from it. Choose the Python runtime.
2. In the Render dashboard, create a free PostgreSQL database. Copy its **internal** connection URL.
3. Build command:

   ```bash
   pip install -r requirements.txt && python manage.py collectstatic --noinput
   ```

4. Start command:

   ```bash
   gunicorn config.wsgi:application --bind 0.0.0.0:$PORT
   ```

5. Set the environment variables on the web service. `DATABASE_URL` is that internal Postgres URL. `ALLOWED_HOSTS` is the service hostname. `CSRF_TRUSTED_ORIGINS` is `https://` plus that hostname.
6. Open the web service shell and run `migrate`, `seed_countries`, `load_visa_stats`, and `createsuperuser`.

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
   # Optional. Without DATABASE_URL the app uses SQLite in the project directory.
   # os.environ.setdefault("DATABASE_URL", "postgres://USER:PASSWORD@HOST:5432/DATABASE")

   from config.wsgi import application  # noqa: E402
   ```

4. Reload the web app. WhiteNoise serves `/static/` from `staticfiles/`.
