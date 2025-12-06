# Generated manually
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='merchant',
            name='is_connected',
            field=models.BooleanField(default=True, help_text='Whether the merchant is connected to Salla'),
        ),
    ]

