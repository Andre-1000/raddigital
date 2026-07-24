from django.db import migrations, models


def atualizar_servicos(apps, schema_editor):
    CatServico = apps.get_model('catalogos', 'CatServico')

    # "Excluir" Controle de Vegetacao = desativa (nunca aparece mais na
    # selecao), sem apagar de fato: RadServico tem FK PROTECT para
    # CatServico, entao um DELETE quebraria qualquer RAD antigo que
    # ja tenha usado esse servico.
    CatServico.objects.filter(nome='Controle de Vegetação').update(ativo=False)

    novos_servicos = [
        {
            'nome': 'Recolhimento de Lixo',
            'requer_terceiros': True,
            'terceiros_tem_op_maquina': True,
            'terceiros_tem_volume': True,
        },
        {
            'nome': 'Limpeza de Canaleta',
            'requer_terceiros': True,
            'terceiros_tem_op_maquina': False,
            'terceiros_tem_volume': True,
        },
        {
            'nome': 'Capina Química',
            'requer_terceiros': True,
            'terceiros_tem_op_maquina': True,
            'terceiros_tem_volume': False,
        },
        {
            'nome': 'Roçada/Poda',
            'requer_terceiros': True,
            'terceiros_tem_op_maquina': True,
            'terceiros_tem_volume': True,
        },
    ]
    for dados in novos_servicos:
        CatServico.objects.update_or_create(nome=dados['nome'], defaults={**dados, 'ativo': True})


def reverter(apps, schema_editor):
    CatServico = apps.get_model('catalogos', 'CatServico')
    CatServico.objects.filter(nome='Controle de Vegetação').update(ativo=True)
    CatServico.objects.filter(
        nome__in=['Recolhimento de Lixo', 'Limpeza de Canaleta', 'Capina Química', 'Roçada/Poda']
    ).update(ativo=False)


class Migration(migrations.Migration):

    dependencies = [
        ('catalogos', '0002_catequipe'),
    ]

    operations = [
        migrations.AddField(
            model_name='catservico',
            name='requer_terceiros',
            field=models.BooleanField(
                default=False,
                help_text='TRUE para Recolhimento de Lixo, Limpeza de Canaleta, Capina Quimica, Rocada/Poda.',
            ),
        ),
        migrations.AddField(
            model_name='catservico',
            name='terceiros_tem_op_maquina',
            field=models.BooleanField(
                default=False, help_text='So relevante quando requer_terceiros=True.'
            ),
        ),
        migrations.AddField(
            model_name='catservico',
            name='terceiros_tem_volume',
            field=models.BooleanField(
                default=False, help_text='So relevante quando requer_terceiros=True.'
            ),
        ),
        migrations.RunPython(atualizar_servicos, reverter),
    ]
