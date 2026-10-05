import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase

# Long enough for Django's deploy check, and not the django-insecure prefix.
PRODUCTION_SECRET = "visa-community-deploy-check-9f3c7a1e5b8d2c6f4a0e" + "Km$7"


def _manage(*args, extra_env):
    env = os.environ.copy()
    # A local .env must not turn this production check back into development.
    env["DEBUG"] = extra_env.pop("DEBUG")
    env.update(extra_env)
    return subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=settings.BASE_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


class ProductionSettingsTests(SimpleTestCase):
    def test_deploy_check_is_clean_with_production_env(self):
        result = _manage(
            "check",
            "--deploy",
            extra_env={
                "DEBUG": "False",
                "SECRET_KEY": PRODUCTION_SECRET,
                "ALLOWED_HOSTS": "visacommunity.example",
                "CSRF_TRUSTED_ORIGINS": "https://visacommunity.example",
            },
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertNotIn("security.W", output)
        self.assertNotIn("security.E", output)

    def test_production_refuses_to_start_without_a_secret_key(self):
        env = os.environ.copy()
        env["DEBUG"] = "False"
        env["SECRET_KEY"] = ""
        env["ALLOWED_HOSTS"] = "visacommunity.example"
        result = subprocess.run(
            [sys.executable, "manage.py", "check"],
            cwd=settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn("SECRET_KEY", output)

    def test_collectstatic_works_when_debug_is_off(self):
        result = _manage(
            "collectstatic",
            "--noinput",
            extra_env={
                "DEBUG": "False",
                "SECRET_KEY": PRODUCTION_SECRET,
                "ALLOWED_HOSTS": "visacommunity.example",
            },
        )
        output = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, output)
        self.assertTrue((settings.BASE_DIR / "staticfiles" / "staticfiles.json").is_file())
