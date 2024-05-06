# Generated by Django 4.2 on 2024-05-06 11:08

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="ForbiddenWord",
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
                (
                    "forbidden_word",
                    models.CharField(
                        max_length=100, unique=True, verbose_name="Запрещенное слово"
                    ),
                ),
            ],
            options={
                "verbose_name": "Запрещенное слово",
                "verbose_name_plural": "Запрещенные слова",
            },
        ),
    ]
