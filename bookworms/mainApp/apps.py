from django.apps import AppConfig


class MainappConfig(AppConfig):
    name = "mainApp"
    default_auto_field = "django.db.models.BigAutoField"

    def ready(self):
        from .registration_service import start_purge_thread

        start_purge_thread()
