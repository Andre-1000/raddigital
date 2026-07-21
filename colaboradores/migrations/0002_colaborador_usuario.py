"""
Liga ColaboradorCadastro a Usuario (matricula = login).

Decisao do projeto: toda pessoa cadastrada como colaborador passa a
ter automaticamente um login no sistema, usando a propria matricula.
Colaboradores/usuarios ja existentes sao vinculados aqui quando a
matricula bate com o login.
"""
from django.db import migrations, models
import django.db.models.deletion


def vincular_existentes(apps, schema_editor):
    ColaboradorCadastro = apps.get_model('colaboradores', 'ColaboradorCadastro')
    Usuario = apps.get_model('usuarios', 'Usuario')

    for colaborador in ColaboradorCadastro.objects.all():
        usuario = Usuario.objects.filter(login=colaborador.registro_empresa).first()
        if usuario:
            colaborador.usuario_id = usuario.id
            colaborador.save(update_fields=['usuario'])


def reverter(apps, schema_editor):
    # Nada a desfazer nos dados -- a coluna e removida pelo proprio Django.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('colaboradores', '0001_initial'),
        ('usuarios', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='colaboradorcadastro',
            name='usuario',
            field=models.OneToOneField(
                to='usuarios.usuario',
                on_delete=django.db.models.deletion.SET_NULL,
                null=True,
                blank=True,
                related_name='colaborador',
                db_column='id_usuario',
                help_text='Login vinculado. Matricula = login (criado automaticamente).',
            ),
        ),
        migrations.RunPython(vincular_existentes, reverter),
    ]
