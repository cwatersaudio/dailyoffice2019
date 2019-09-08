# Generated by Django 2.2.4 on 2019-08-28 01:53

from django.db import migrations, models
import django.db.models.deletion
import djrichtextfield.models
import uuid


class Migration(migrations.Migration):

    dependencies = [("sermons", "0006_sermondatetime_primary")]

    operations = [
        migrations.AlterField(
            model_name="sermondatetime",
            name="primary",
            field=models.BooleanField(
                default=False,
                help_text="Should this date be the primary date used for sorting?",
                verbose_name="Primary Service",
            ),
        ),
        migrations.CreateModel(
            name="SermonBiblePassage",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("created", models.DateTimeField(auto_now_add=True)),
                ("updated", models.DateTimeField(auto_now=True)),
                (
                    "type",
                    models.IntegerField(
                        choices=[
                            (2, "Psalm"),
                            (4, "GOSPEL"),
                            (1, "Prophecy (Old Testament)"),
                            (5, "OTHER"),
                            (3, "EPISTLE (or Acts / Revelation)"),
                        ],
                        default=0,
                    ),
                ),
                ("passage", models.CharField(max_length=256)),
                ("text", models.TextField()),
                ("html", djrichtextfield.models.RichTextField()),
                (
                    "version",
                    models.CharField(
                        blank=True,
                        choices=[
                            ("nrsv", "nrsv"),
                            ("esv", "esv"),
                            ("rsv", "rsv"),
                            ("kjv", "kjv"),
                            ("nabre", "nabre"),
                            ("niv", "niv"),
                        ],
                        max_length=256,
                        null=True,
                    ),
                ),
                (
                    "sermon",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="sermons.Sermon", verbose_name="Sermon"
                    ),
                ),
            ],
            options={"abstract": False},
        ),
    ]