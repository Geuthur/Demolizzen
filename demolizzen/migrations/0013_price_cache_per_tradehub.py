# Django
from django.db import migrations, models


class Migration(migrations.Migration):
    """Cache prices per item and trade hub.

    The table is only a cache with the item name as its sole key, so it is
    created anew; prices are fetched again on demand.
    """

    dependencies = [
        ("demolizzen", "0012_delete_eveentitytask"),
    ]

    operations = [
        migrations.DeleteModel(
            name="EvePricecache",
        ),
        migrations.CreateModel(
            name="EvePricecache",
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
                ("item_name", models.CharField(max_length=255)),
                ("tradehub", models.CharField(max_length=32)),
                ("price", models.BigIntegerField()),
                ("buy", models.BigIntegerField()),
                ("expiration", models.DateTimeField()),
            ],
            options={
                "db_table": "eve_price_cache",
                "default_permissions": (),
                "constraints": [
                    models.UniqueConstraint(
                        fields=("item_name", "tradehub"),
                        name="eve_price_cache_item_hub",
                    )
                ],
            },
        ),
    ]
