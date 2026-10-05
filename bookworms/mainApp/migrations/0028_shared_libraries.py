from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


def provision_libraries(apps, schema_editor):
    User = apps.get_model("mainApp", "CustomUser")
    Library = apps.get_model("mainApp", "Library")
    LibraryMembership = apps.get_model("mainApp", "LibraryMembership")
    BookCopy = apps.get_model("mainApp", "BookCopy")

    for user in User.objects.all().iterator():
        lib = Library.objects.create(
            name=f"Бібліотека {user.username}",
            admin_id=user.id,
        )
        LibraryMembership.objects.create(
            library=lib,
            user_id=user.id,
            role="admin",
        )
        BookCopy.objects.filter(owner_id=user.id).update(
            library_id=lib.id,
            added_by_id=user.id,
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("mainApp", "0027_bookcopy_listing_flags"),
    ]

    operations = [
        migrations.CreateModel(
            name="Library",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, max_length=200, verbose_name="Назва")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "admin",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="administered_libraries",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Адміністратор",
                    ),
                ),
            ],
            options={
                "verbose_name": "бібліотека",
                "verbose_name_plural": "бібліотеки",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="LibraryMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "role",
                    models.CharField(
                        choices=[("admin", "Адміністратор"), ("member", "Учасник")],
                        default="member",
                        max_length=16,
                        verbose_name="Роль",
                    ),
                ),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                (
                    "library",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="mainApp.library",
                        verbose_name="Бібліотека",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="library_membership",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Користувач",
                    ),
                ),
            ],
            options={
                "verbose_name": "членство в бібліотеці",
                "verbose_name_plural": "членства в бібліотеках",
            },
        ),
        migrations.CreateModel(
            name="LibraryInvite",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Очікує"),
                            ("accepted", "Прийнято"),
                            ("rejected", "Відхилено"),
                            ("cancelled", "Скасовано"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("message", models.CharField(blank=True, max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                (
                    "from_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="library_invites_sent",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Від кого",
                    ),
                ),
                (
                    "library",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="invites",
                        to="mainApp.library",
                        verbose_name="Цільова бібліотека",
                    ),
                ),
                (
                    "to_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="library_invites_received",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Кому",
                    ),
                ),
            ],
            options={
                "verbose_name": "запрошення до бібліотеки",
                "verbose_name_plural": "запрошення до бібліотек",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="LibraryAction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "action_type",
                    models.CharField(
                        choices=[
                            ("add_copy", "Додати примірник"),
                            ("remove_copy", "Прибрати примірник"),
                            ("listing", "Змінити статус оголошення"),
                            ("split_leave", "Вийти з поділом примірників"),
                        ],
                        max_length=32,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Очікує"),
                            ("approved", "Схвалено"),
                            ("rejected", "Відхилено"),
                            ("cancelled", "Скасовано"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("result_note", models.CharField(blank=True, max_length=300)),
                (
                    "initiator",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="library_actions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "library",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="actions",
                        to="mainApp.library",
                    ),
                ),
                (
                    "resolved_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="library_actions_resolved",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "дія бібліотеки",
                "verbose_name_plural": "дії бібліотеки",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddField(
            model_name="bookcopy",
            name="library",
            field=models.ForeignKey(
                blank=True,
                help_text="Порожньо лише до міграції; далі кожен примірник належить бібліотеці.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="copies",
                to="mainApp.library",
                verbose_name="Спільна бібліотека",
            ),
        ),
        migrations.AddField(
            model_name="bookcopy",
            name="added_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="copies_added",
                to=settings.AUTH_USER_MODEL,
                verbose_name="Хто додав",
            ),
        ),
        migrations.AddConstraint(
            model_name="librarymembership",
            constraint=models.UniqueConstraint(
                fields=("library", "user"),
                name="uniq_library_membership_user",
            ),
        ),
        migrations.RunPython(provision_libraries, noop_reverse),
    ]
