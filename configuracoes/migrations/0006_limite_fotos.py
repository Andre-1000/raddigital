from django.db import migrations, models

# 30/07/2026: limites de foto configuraveis pelo Administrador, sem
# precisar de deploy. Servicos da area Infra passam a permitir 5 fotos
# por categoria (10 no total) em vez do padrao de 2 por categoria (4 no
# total) -- decisao de negocio, ver conversa com Andre.


def popular_limites_padrao(apps, schema_editor):
    LimiteFotos = apps.get_model('configuracoes', 'LimiteFotos')
    valores = [
        ('intervencao_verificada', 'padrao', 2),
        ('acao_realizada', 'padrao', 2),
        ('intervencao_verificada', 'infra', 5),
        ('acao_realizada', 'infra', 5),
    ]
    for categoria, area, limite in valores:
        LimiteFotos.objects.get_or_create(
            categoria=categoria, area=area, defaults={'limite': limite}
        )


def reverter(apps, schema_editor):
    LimiteFotos = apps.get_model('configuracoes', 'LimiteFotos')
    LimiteFotos.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('configuracoes', '0005_operador_ccm_abertura_entrega'),
        ('usuarios', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='LimiteFotos',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                (
                    'categoria',
                    models.CharField(
                        choices=[
                            ('intervencao_verificada', 'Intervenção Verificada'),
                            ('acao_realizada', 'Ação Realizada'),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    'area',
                    models.CharField(
                        choices=[('padrao', 'Padrão (Geral e demais áreas)'), ('infra', 'Infra')],
                        max_length=10,
                    ),
                ),
                ('limite', models.PositiveSmallIntegerField()),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
                (
                    'atualizado_por',
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=models.deletion.SET_NULL,
                        related_name='+',
                        to='usuarios.usuario',
                    ),
                ),
            ],
            options={
                'db_table': 'configuracoes_limite_fotos',
                'verbose_name': 'Limite de Fotos',
                'verbose_name_plural': 'Configuração de Limites de Fotos',
                'ordering': ['categoria', 'area'],
            },
        ),
        migrations.AddConstraint(
            model_name='limitefotos',
            constraint=models.UniqueConstraint(fields=['categoria', 'area'], name='uniq_categoria_area_limite'),
        ),
        migrations.RunPython(popular_limites_padrao, reverter),
    ]
