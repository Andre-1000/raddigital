import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='email',
            field=models.EmailField(
                max_length=254, null=True, blank=True, unique=True,
                help_text=(
                    '30/07/2026: usado para o fluxo de "Esqueci minha senha". '
                    'Pode ficar vazio para usuarios legados ate o Administrador '
                    'preencher (Postgres permite varios NULL num campo unique, '
                    'entao nao ha conflito entre usuarios sem e-mail ainda).'
                ),
            ),
        ),
        migrations.AddField(
            model_name='usuario',
            name='senha_hash',
            field=models.CharField(
                max_length=255, null=True, blank=True,
                help_text=(
                    '30/07/2026: hash da senha (django.contrib.auth.hashers.make_password '
                    '-- PBKDF2, nunca texto plano). Vazio = usuario legado que ainda nao '
                    'definiu senha; o login bloqueia e orienta a usar "Esqueci minha senha" '
                    'nesse caso, que funciona tambem como fluxo de primeira senha.'
                ),
            ),
        ),
        migrations.AddField(
            model_name='usuario',
            name='tentativas_login_falhas',
            field=models.PositiveSmallIntegerField(
                default=0,
                help_text='Zerado a cada login correto. Ver bloqueado_ate.',
            ),
        ),
        migrations.AddField(
            model_name='usuario',
            name='bloqueado_ate',
            field=models.DateTimeField(
                null=True, blank=True,
                help_text='30/07/2026: rate limit contra forca bruta -- ver settings.MAXIMO_TENTATIVAS_LOGIN.',
            ),
        ),
        migrations.AlterField(
            model_name='usuario',
            name='login',
            field=models.CharField(max_length=100, unique=True, help_text='Login unico.'),
        ),
        migrations.CreateModel(
            name='TokenRedefinicaoSenha',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('token', models.CharField(max_length=255, unique=True)),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
                ('validade', models.DateTimeField()),
                ('usado', models.BooleanField(default=False)),
                (
                    'usuario',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='tokens_redefinicao',
                        to='usuarios.usuario',
                        db_column='id_usuario',
                    ),
                ),
            ],
            options={
                'db_table': 'tokens_redefinicao_senha',
                'verbose_name': 'Token de Redefinição de Senha',
                'verbose_name_plural': 'Tokens de Redefinição de Senha',
            },
        ),
        migrations.AddIndex(
            model_name='tokenredefinicaosenha',
            index=models.Index(fields=['token'], name='idx_token_redef_token'),
        ),
    ]
