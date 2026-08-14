# Gerado manualmente em 14/08/2026 -- ver rad/models.py::RadCanaleta e
# RadCanaletaDimensao para o contexto completo.
#
# Esta migration faz 3 coisas nesta ordem (a ordem importa: nao dá pra
# apagar as colunas antigas antes de copiar o dado delas):
#   1. Cria a tabela nova rad_canaleta_dimensoes.
#   2. RunPython: para cada RadCanaleta ja existente, cria UMA linha em
#      RadCanaletaDimensao (ordem=1) copiando as 5 medidas antigas --
#      preserva qualquer RAD com Inspecao de Canaleta ja sincronizado
#      (o bloco Canaleta foi ao ar hoje mesmo, 14/08, entao o volume
#      esperado aqui e pequeno ou zero, mas a copia roda de qualquer
#      forma por seguranca).
#   3. Adiciona rad_canaleta.justificativa e remove as 5 colunas
#      antigas (largura_inicial/final, altura_inicial/final,
#      comprimento) de rad_canaleta -- elas so existem agora dentro de
#      rad_canaleta_dimensoes.
import django.db.models.deletion
from django.db import migrations, models


def copiar_dimensoes_existentes(apps, schema_editor):
    RadCanaleta = apps.get_model('rad', 'RadCanaleta')
    RadCanaletaDimensao = apps.get_model('rad', 'RadCanaletaDimensao')

    dimensoes_novas = [
        RadCanaletaDimensao(
            canaleta=canaleta,
            ordem=1,
            largura_inicial=canaleta.largura_inicial,
            largura_final=canaleta.largura_final,
            altura_inicial=canaleta.altura_inicial,
            altura_final=canaleta.altura_final,
            comprimento=canaleta.comprimento,
        )
        for canaleta in RadCanaleta.objects.all()
    ]
    RadCanaletaDimensao.objects.bulk_create(dimensoes_novas)


def reverter_copia_dimensoes(apps, schema_editor):
    """
    Reversao: joga a primeira linha (ordem=1) de volta pros campos
    fixos antigos de cada RadCanaleta, antes das colunas antigas serem
    recriadas pelo AddField reverso. Linhas extras (ordem > 1) sao
    perdidas na reversao -- esperado, ja que o schema antigo nao tinha
    onde guarda-las.
    """
    RadCanaleta = apps.get_model('rad', 'RadCanaleta')

    for canaleta in RadCanaleta.objects.all():
        primeira = canaleta.dimensoes.order_by('ordem', 'id').first()
        if not primeira:
            continue
        canaleta.largura_inicial = primeira.largura_inicial
        canaleta.largura_final = primeira.largura_final
        canaleta.altura_inicial = primeira.altura_inicial
        canaleta.altura_final = primeira.altura_final
        canaleta.comprimento = primeira.comprimento
        canaleta.save(
            update_fields=[
                'largura_inicial', 'largura_final',
                'altura_inicial', 'altura_final', 'comprimento',
            ]
        )


class Migration(migrations.Migration):

    dependencies = [
        ('rad', '0015_canaleta'),
    ]

    operations = [
        migrations.CreateModel(
            name='RadCanaletaDimensao',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ordem', models.PositiveSmallIntegerField(default=1)),
                ('largura_inicial', models.DecimalField(decimal_places=2, max_digits=8)),
                ('largura_final', models.DecimalField(decimal_places=2, max_digits=8)),
                ('altura_inicial', models.DecimalField(decimal_places=2, max_digits=8)),
                ('altura_final', models.DecimalField(decimal_places=2, max_digits=8)),
                ('comprimento', models.DecimalField(decimal_places=2, max_digits=8)),
                ('canaleta', models.ForeignKey(db_column='id_canaleta', on_delete=django.db.models.deletion.CASCADE, related_name='dimensoes', to='rad.radcanaleta')),
            ],
            options={
                'verbose_name': 'Dimensão da Canaleta',
                'verbose_name_plural': 'Dimensões da Canaleta',
                'db_table': 'rad_canaleta_dimensoes',
                'ordering': ['ordem', 'id'],
            },
        ),
        migrations.RunPython(copiar_dimensoes_existentes, reverter_copia_dimensoes),
        migrations.AddField(
            model_name='radcanaleta',
            name='justificativa',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.RemoveField(model_name='radcanaleta', name='largura_inicial'),
        migrations.RemoveField(model_name='radcanaleta', name='largura_final'),
        migrations.RemoveField(model_name='radcanaleta', name='altura_inicial'),
        migrations.RemoveField(model_name='radcanaleta', name='altura_final'),
        migrations.RemoveField(model_name='radcanaleta', name='comprimento'),
    ]
