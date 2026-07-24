from django.db import migrations


def desativar_limpeza(apps, schema_editor):
    CatServico = apps.get_model('catalogos', 'CatServico')
    CatServico.objects.filter(nome='Limpeza').update(ativo=False)


def reverter(apps, schema_editor):
    CatServico = apps.get_model('catalogos', 'CatServico')
    CatServico.objects.filter(nome='Limpeza').update(ativo=True)


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0004_locais_ativo'),
    ]

    operations = [
        migrations.RunPython(desativar_limpeza, reverter),
    ]
