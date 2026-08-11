from django.contrib.auth.hashers import make_password
from django.db import migrations

# 30/07/2026: usuario de desenvolvimento/teste (Andre), com todos os
# perfis (Usuario + Supervisor + Administrador) e senha fixa "1234".
#
# ATENCAO -- risco de seguranca conhecido e aceito conscientemente:
# "1234" tem 4 digitos, bem abaixo do minimo de 8 caracteres que o
# proprio sistema exige em qualquer outro fluxo (troca de senha,
# redefinicao). Essa senha e criada aqui via make_password() direto,
# contornando de proposito o validador (usuarios/validadores_senha.py)
# -- e o UNICO lugar do sistema que faz isso. Se este usuario ganhar
# uso além de teste local, TROCAR A SENHA por uma forte antes.


def criar_usuario_teste(apps, schema_editor):
    Usuario = apps.get_model('usuarios', 'Usuario')
    UsuarioPerfil = apps.get_model('usuarios', 'UsuarioPerfil')

    usuario, _ = Usuario.objects.get_or_create(login='teste.dev')
    usuario.senha_hash = make_password('1234')
    usuario.ativo = True
    usuario.tentativas_login_falhas = 0
    usuario.bloqueado_ate = None
    usuario.save()

    for perfil in ('usuario', 'supervisor', 'administrador'):
        UsuarioPerfil.objects.get_or_create(usuario=usuario, perfil=perfil)


def reverter(apps, schema_editor):
    Usuario = apps.get_model('usuarios', 'Usuario')
    Usuario.objects.filter(login='teste.dev').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0002_senha_email'),
    ]

    operations = [
        migrations.RunPython(criar_usuario_teste, reverter),
    ]
