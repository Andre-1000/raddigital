from django.db import migrations


def criar_vpm001(apps, schema_editor):
    CatTipoManutencao = apps.get_model('catalogos', 'CatTipoManutencao')
    CatTipoManutencao.objects.get_or_create(nome='VPM001')


def remover_vpm001(apps, schema_editor):
    CatTipoManutencao = apps.get_model('catalogos', 'CatTipoManutencao')
    CatTipoManutencao.objects.filter(nome='VPM001').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0006_amv_outros'),
    ]

    operations = [
        migrations.RunPython(criar_vpm001, remover_vpm001),
    ]
