# Gerado manualmente em 25/08/2026 -- adiciona o model
# LogSenhaTemporaria (auditoria de quem gerou senha temporaria para
# quem, ver usuarios/views.py::definir_senha_temporaria). Nao ha
# mudanca de schema em TokenRedefinicaoSenha nem em Token: ambos
# continuam sendo CharField, so o que fica gravado dentro do campo
# 'token' mudou (hash em vez de texto puro) -- isso e uma mudanca de
# codigo, nao de banco, entao nao precisa de migration.
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0004_tentativa_login_admin'),
    ]

    operations = [
        migrations.CreateModel(
            name='LogSenhaTemporaria',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('administrador_login_snapshot', models.CharField(max_length=100)),
                ('usuario_alvo_login_snapshot', models.CharField(max_length=100)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('administrador', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='logs_senha_temporaria_gerada',
                    to='usuarios.usuario',
                )),
                ('usuario_alvo', models.ForeignKey(
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='logs_senha_temporaria_recebida',
                    to='usuarios.usuario',
                )),
            ],
            options={
                'verbose_name': 'Log de Senha Temporária',
                'verbose_name_plural': 'Logs de Senha Temporária',
                'db_table': 'log_senha_temporaria',
                'ordering': ['-criado_em'],
            },
        ),
    ]
