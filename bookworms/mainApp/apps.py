from django.apps import AppConfig


class MainappConfig(AppConfig):
    name = "mainApp"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        # gunicorn: bookworms/gunicorn.conf.py post_worker_init
        # runserver: only the reloader child (RUN_MAIN=true)
        import os

        if os.environ.get("RUN_MAIN") == "true":
            from .registration_service import start_purge_thread

            start_purge_thread()
