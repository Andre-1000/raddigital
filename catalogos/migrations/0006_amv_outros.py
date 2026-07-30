from django.db import migrations, models


def criar_opcao_outros(apps, schema_editor):
    CatTipoDefeitoAmv = apps.get_model('catalogos', 'CatTipoDefeitoAmv')
    CatAcaoAmv = apps.get_model('catalogos', 'CatAcaoAmv')

    CatTipoDefeitoAmv.objects.update_or_create(
        nome='Outros', defaults={'ativo': True, 'requer_descricao': True}
    )
    CatAcaoAmv.objects.update_or_create(
        nome='Outros', defaults={'ativo': True, 'requer_descricao': True}
    )


def reverter(apps, schema_editor):
    CatTipoDefeitoAmv = apps.get_model('catalogos', 'CatTipoDefeitoAmv')
    CatAcaoAmv = apps.get_model('catalogos', 'CatAcaoAmv')
    CatTipoDefeitoAmv.objects.filter(nome='Outros').delete()
    CatAcaoAmv.objects.filter(nome='Outros').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0005_remove_limpeza'),
    ]

    operations = [
        migrations.AddField(
            model_name='cattipodefeitoamv',
            name='requer_descricao',
            field=models.BooleanField(
                default=False, help_text='TRUE somente para Outros (22/07/2026).'
            ),
        ),
        migrations.AddField(
            model_name='catacaoamv',
            name='requer_descricao',
            field=models.BooleanField(
                default=False, help_text='TRUE somente para Outros (22/07/2026).'
            ),
        ),
        migrations.RunPython(criar_opcao_outros, reverter),
    ]
