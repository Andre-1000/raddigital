from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rad', '0010_rad_solicitante_sa'),
    ]

    operations = [
        migrations.AddField(
            model_name='radamv',
            name='desc_outros_tipo_defeito',
            field=models.TextField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='radamv',
            name='desc_outros_acao',
            field=models.TextField(null=True, blank=True),
        ),
    ]
