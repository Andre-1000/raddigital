from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0003_usuario_teste_dev'),
    ]

    operations = [
        migrations.CreateModel(
            name='TentativaLoginAdmin',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('ip', models.GenericIPAddressField(unique=True)),
                ('tentativas', models.PositiveSmallIntegerField(default=0)),
                ('bloqueado_ate', models.DateTimeField(blank=True, null=True)),
                ('atualizado_em', models.DateTimeField(auto_now=True)),
            ],
            options={
                'db_table': 'tentativas_login_admin',
                'verbose_name': 'Tentativa de Login (Admin)',
                'verbose_name_plural': 'Tentativas de Login (Admin)',
            },
        ),
    ]
