import django.db.models.deletion
from django.db import migrations, models

# 30/07/2026: suporte a multiplos blocos AMV por RAD (ate 16, um por
# MCH verificada no dia). Antes, RadAmv era 1-para-1 com Rad, e
# RadAmvDefeito/RadAmvAcao apontavam direto pro Rad (fazia sentido
# quando so podia existir 1 bloco). Agora RadAmv vira 1-para-muitos
# (FK normal), e RadAmvDefeito/RadAmvAcao passam a apontar para o
# BLOCO (RadAmv) especifico, nao mais pro RAD.
#
# ORDEM TESTADA (com dados de exemplo, forward e backward, ver sessao
# de 30/07/2026): a ordem das operacoes abaixo NAO e arbitraria --
# uma primeira versao desta migration passava no forward mas quebrava
# ao reverter (`migrate rad 0013`), porque a coluna antiga 'rad' era
# recriada como NOT NULL sem dado nenhum. A ordem certa, testada com
# `python manage.py migrate rad 0013` num banco populado, e:
#   1. Coluna nova 'amv' entra nullable
#   2. Coluna antiga 'rad' vira nullable (permanece um tempo assim)
#   3. RunPython copia o dado (forward: rad->amv; backward: amv->rad)
#   4. Coluna nova 'amv' vira obrigatoria
#   5. So ENTAO a coluna antiga 'rad' e removida
# Isso garante que, ao reverter, a coluna 'rad' e recriada NULLABLE
# (nunca NOT NULL de cara), e so volta a ser obrigatoria depois do
# RunPython repopular o dado -- nunca falha por NOT NULL sem valor.
#
# Limite conhecido do rollback: se algum RAD ja tiver mais de 1 bloco
# AMV (usando a funcionalidade nova de verdade), a reversao ate o fim
# (que tenta restaurar RadAmv.rad como UNICO) vai falhar de proposito
# -- nao ha como um RAD com 2 MCHs "caber" num schema que so permite 1.
# Nesse caso o rollback so e seguro ATE a etapa da constraint unica;
# reverter mais que isso exigiria apagar manualmente os blocos extras.


def popular_fk_amv(apps, schema_editor):
    RadAmv = apps.get_model('rad', 'RadAmv')
    RadAmvDefeito = apps.get_model('rad', 'RadAmvDefeito')
    RadAmvAcao = apps.get_model('rad', 'RadAmvAcao')
    for amv in RadAmv.objects.all():
        RadAmvDefeito.objects.filter(rad_id=amv.rad_id).update(amv_id=amv.id)
        RadAmvAcao.objects.filter(rad_id=amv.rad_id).update(amv_id=amv.id)


def reverter_popular_fk_amv(apps, schema_editor):
    """
    Reverso: repopula a coluna antiga 'rad_id' a partir do bloco (amv),
    usando a relacao amv->rad que ainda existe nesse ponto da reversao
    (a coluna 'amv' so e removida depois desta funcao rodar).
    """
    RadAmv = apps.get_model('rad', 'RadAmv')
    RadAmvDefeito = apps.get_model('rad', 'RadAmvDefeito')
    RadAmvAcao = apps.get_model('rad', 'RadAmvAcao')
    for amv in RadAmv.objects.all():
        RadAmvDefeito.objects.filter(amv_id=amv.id).update(rad_id=amv.rad_id)
        RadAmvAcao.objects.filter(amv_id=amv.id).update(rad_id=amv.rad_id)


class Migration(migrations.Migration):

    dependencies = [
        ('rad', '0013_operador_ccm_abertura_entrega'),
    ]

    operations = [
        # 1. RadAmv deixa de ser OneToOne (unique) e vira ForeignKey normal
        migrations.AlterField(
            model_name='radamv',
            name='rad',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='amv_blocos',
                to='rad.rad',
                db_column='id_rad',
            ),
        ),
        # 2. Nova coluna 'amv' em Defeito/Acao, nullable por enquanto
        migrations.AddField(
            model_name='radamvdefeito',
            name='amv',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='defeitos',
                to='rad.radamv',
                db_column='id_amv',
            ),
        ),
        migrations.AddField(
            model_name='radamvacao',
            name='amv',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='acoes',
                to='rad.radamv',
                db_column='id_amv',
            ),
        ),
        # 3. Coluna antiga 'rad' vira nullable ANTES do RunPython e da
        # remocao -- e o que garante que reverter nao tenta recriar
        # 'rad' como NOT NULL sem dado (ver nota no topo do arquivo).
        migrations.AlterField(
            model_name='radamvdefeito',
            name='rad',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='amv_defeitos_legado',
                to='rad.rad',
                db_column='id_rad',
            ),
        ),
        migrations.AlterField(
            model_name='radamvacao',
            name='rad',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='amv_acoes_legado',
                to='rad.rad',
                db_column='id_rad',
            ),
        ),
        # 4. Copia o dado existente (RADs ja sincronizados com bloco AMV)
        migrations.RunPython(popular_fk_amv, reverter_popular_fk_amv),
        # 5. Torna a nova coluna obrigatoria, agora que esta populada
        migrations.AlterField(
            model_name='radamvdefeito',
            name='amv',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='defeitos',
                to='rad.radamv',
                db_column='id_amv',
            ),
        ),
        migrations.AlterField(
            model_name='radamvacao',
            name='amv',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='acoes',
                to='rad.radamv',
                db_column='id_amv',
            ),
        ),
        # 6. Remove a constraint e a coluna antigas, so depois do dado a salvo
        migrations.RemoveConstraint(model_name='radamvdefeito', name='uniq_rad_amv_defeito'),
        migrations.RemoveConstraint(model_name='radamvacao', name='uniq_rad_amv_acao'),
        migrations.RemoveField(model_name='radamvdefeito', name='rad'),
        migrations.RemoveField(model_name='radamvacao', name='rad'),
        migrations.AddConstraint(
            model_name='radamvdefeito',
            constraint=models.UniqueConstraint(fields=['amv', 'tipo_defeito'], name='uniq_amv_defeito'),
        ),
        migrations.AddConstraint(
            model_name='radamvacao',
            constraint=models.UniqueConstraint(fields=['amv', 'acao'], name='uniq_amv_acao'),
        ),
        # Metadados que ficaram sem migration em mudancas anteriores
        # desta mesma sessao (help_text/ordering -- nao alteram o
        # schema do banco, mas precisam ser declarados aqui pra
        # `makemigrations --check` nao acusar diferenca nenhuma).
        migrations.AlterModelOptions(
            name='radamv',
            options={'ordering': ['id'], 'verbose_name': 'Bloco AMV', 'verbose_name_plural': 'Blocos AMV'},
        ),
        migrations.AlterField(
            model_name='rad',
            name='operador',
            field=models.TextField(blank=True, help_text='Texto livre, sem limite de caracteres.', null=True),
        ),
        migrations.AlterField(
            model_name='rad',
            name='solicitante_sa',
            field=models.TextField(
                blank=True,
                help_text='Quem solicitou a SA. Texto livre, sem limite de caracteres (22/07/2026).',
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name='rad',
            name='tipo_veiculo',
            field=models.TextField(blank=True, help_text='Texto livre, sem limite de caracteres.', null=True),
        ),
    ]
