from django.db import migrations, models

# Lista nova (22/07/2026): mantem so estacoes e patios. Cabines,
# subestacoes, terminais, VSE e ALMOX saem de circulacao -- mas ficam
# no banco (ativo=False), nao sao apagadas, porque RadLinha/Rad tem FK
# PROTECT contra CatLocal e RADs antigos podem ja referencia-las.
SIGLAS_QUE_PERMANECEM_ATIVAS = [
    'BFU', 'LUZ', 'BAS', 'CCO', 'TAT', 'ITQ', 'DBO', 'JBO', 'GUA', 'AGN',
    'FVC', 'POÁ', 'CVN', 'SUZ', 'JPB', 'BCB', 'MDC', 'EST', 'USL', 'ERM',
    'SMP', 'JHE', 'ITI', 'JRO', 'EMF', 'IQC', 'ARC', 'EGO', 'GCE', 'AGU',
    'PAT 001', 'PAT 003', 'PAT 005', 'PAT 006', 'PAT 007', 'PAT 008',
    'PAT 009', 'PAT 011', 'PAT 013', 'PAT 014',
]


def desativar_locais_removidos(apps, schema_editor):
    CatLocal = apps.get_model('catalogos', 'CatLocal')
    CatLocal.objects.exclude(sigla__in=SIGLAS_QUE_PERMANECEM_ATIVAS).update(ativo=False)


def reverter(apps, schema_editor):
    CatLocal = apps.get_model('catalogos', 'CatLocal')
    CatLocal.objects.all().update(ativo=True)


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0003_servicos_terceiros'),
    ]

    operations = [
        migrations.AddField(
            model_name='catlocal',
            name='ativo',
            field=models.BooleanField(
                default=True,
                help_text='Locais inativos somem da selecao mas continuam existindo para RADs antigos.',
            ),
        ),
        migrations.RunPython(desativar_locais_removidos, reverter),
    ]
