from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mainApp", "0023_bookphoto"),
    ]

    operations = [
        migrations.AddField(
            model_name="book",
            name="cover_text",
            field=models.TextField(
                blank=True,
                help_text="Повний текст, розпізнаний з фото обкладинки.",
                verbose_name="Текст з обкладинки (AI/OCR)",
            ),
        ),
    ]
