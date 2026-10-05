from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("mainApp", "0028_shared_libraries"),
    ]

    operations = [
        migrations.CreateModel(
            name="LibraryAdminElection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Триває"),
                            ("completed", "Завершено"),
                            ("cancelled", "Скасовано"),
                        ],
                        db_index=True,
                        default="open",
                        max_length=16,
                    ),
                ),
                (
                    "reason",
                    models.CharField(
                        blank=True,
                        help_text="Напр. після об'єднання бібліотек / зміна адміна.",
                        max_length=200,
                        verbose_name="Причина",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "library",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="elections",
                        to="mainApp.library",
                        verbose_name="Бібліотека",
                    ),
                ),
                (
                    "started_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="library_elections_started",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Ініціатор",
                    ),
                ),
                (
                    "winner",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="library_elections_won",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Обраний адмін",
                    ),
                ),
            ],
            options={
                "verbose_name": "вибори адміна бібліотеки",
                "verbose_name_plural": "вибори адміна бібліотеки",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="LibraryAdminVote",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "candidate",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="library_admin_votes_received",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Кандидат",
                    ),
                ),
                (
                    "election",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="votes",
                        to="mainApp.libraryadminelection",
                        verbose_name="Вибори",
                    ),
                ),
                (
                    "voter",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="library_admin_votes",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Голосуючий",
                    ),
                ),
            ],
            options={
                "verbose_name": "голос за адміна",
                "verbose_name_plural": "голоси за адміна",
            },
        ),
        migrations.AddConstraint(
            model_name="libraryadminvote",
            constraint=models.UniqueConstraint(
                fields=("election", "voter"),
                name="uniq_library_election_voter",
            ),
        ),
    ]
