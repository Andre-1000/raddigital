from django.db import migrations, models

# 30/07/2026: Operador CCM deixa de ser um unico campo texto e passa a
# ser dois pares Nome+Hora -- Abertura e Entrega. O valor antigo (texto
# livre, ate 25 caracteres) nao tem como ser dividido automaticamente
# em nome/hora, entao migramos o conteudo existente para
# operador_ccm_abertura_nome (mantendo o dado visivel em algum lugar,
# em vez de descarta-lo) e deixamos operador_ccm_entrega_nome vazio
# para edicao manual nos RADs antigos que tinham esse campo preenchido.


def migrar_dados_antigos(apps, schema_editor):
    Rad = apps.get_model('rad', 'Rad')
    Rad.objects.exclude(operador_ccm__isnull=True).exclude(operador_ccm='').update(
        operador_ccm_abertura_nome=models.F('operador_ccm')
    )


def reverter_dados(apps, schema_editor):
    Rad = apps.get_model('rad', 'Rad')
    Rad.objects.exclude(operador_ccm_abertura_nome__isnull=True).update(
        operador_ccm=models.F('operador_ccm_abertura_nome')
    )


class Migration(migrations.Migration):

    dependencies = [
        ('rad', '0012_rad_desc_fotos_vpm001'),
    ]

    operations = [
        migrations.AddField(
            model_name='rad',
            name='operador_ccm_abertura_nome',
            field=models.CharField(max_length=50, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='rad',
            name='operador_ccm_abertura_hora',
            field=models.TimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='rad',
            name='operador_ccm_entrega_nome',
            field=models.CharField(max_length=50, null=True, blank=True),
        ),
        migrations.AddField(
            model_name='rad',
            name='operador_ccm_entrega_hora',
            field=models.TimeField(null=True, blank=True),
        ),
        migrations.RunPython(migrar_dados_antigos, reverter_dados),
        migrations.RemoveField(
            model_name='rad',
            name='operador_ccm',
        ),
    ]
