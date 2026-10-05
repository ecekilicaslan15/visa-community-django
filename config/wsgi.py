"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.0/howto/deployment/wsgi/
"""

import logging
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = get_wsgi_application()

logger = logging.getLogger(__name__)


def _bootstrap_render():
    """Free Render instances have no shell, so prepare the database on boot."""
    if os.environ.get("RENDER") != "true":
        return
    from django.contrib.auth import get_user_model
    from django.core.management import call_command

    call_command("migrate", interactive=False)
    call_command("seed_countries")
    call_command("load_visa_stats")

    username = os.environ.get("DJANGO_SUPERUSER_USERNAME", "").strip()
    email = os.environ.get("DJANGO_SUPERUSER_EMAIL", "").strip()
    password = os.environ.get("DJANGO_SUPERUSER_PASSWORD", "").strip()
    if not (username and email and password):
        return
    User = get_user_model()
    if User.objects.filter(username=username).exists():
        return
    User.objects.create_superuser(username=username, email=email, password=password)


try:
    _bootstrap_render()
except Exception:
    logger.exception("Could not prepare the Render database.")
