from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0043_cover_url_relative_media"),
    ]

    operations = [
        migrations.AddField(
            model_name="customuser",
            name="age",
            field=models.PositiveSmallIntegerField(
                blank=True,
                help_text="Вік користувача (років). Для стрічки зіставляється з рекомендованим віком книги.",
                null=True,
                validators=[MinValueValidator(0), MaxValueValidator(120)],
                verbose_name="Вік",
            ),
        ),
        migrations.AddField(
            model_name="customuser",
            name="place",
            field=models.CharField(
                blank=True,
                max_length=255,
                verbose_name="Місце проживання",
            ),
        ),
        migrations.AddField(
            model_name="customuser",
            name="preferred_subjects",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Підмножина тем з каталогу Book.subjects.",
                verbose_name="Улюблені теми / жанри",
            ),
        ),
        migrations.CreateModel(
            name="UserSubProfile",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=100, verbose_name="Назва")),
                (
                    "age",
                    models.PositiveSmallIntegerField(
                        blank=True,
                        null=True,
                        validators=[MinValueValidator(0), MaxValueValidator(120)],
                        verbose_name="Вік",
                    ),
                ),
                (
                    "place",
                    models.CharField(
                        blank=True,
                        max_length=255,
                        verbose_name="Місце проживання",
                    ),
                ),
                (
                    "preferred_subjects",
                    models.JSONField(
                        blank=True,
                        default=list,
                        verbose_name="Улюблені теми / жанри",
                    ),
                ),
                (
                    "sort_order",
                    models.PositiveSmallIntegerField(default=0, verbose_name="Порядок"),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="subprofiles",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Користувач",
                    ),
                ),
            ],
            options={
                "verbose_name": "підпрофіль",
                "verbose_name_plural": "підпрофілі",
                "ordering": ["sort_order", "id"],
            },
        ),
    ]
