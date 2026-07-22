"""
Comando de correção pontual: garante login (Usuario) para todo
ColaboradorCadastro que ainda não tem um vinculado.

Necessário porque a migração 0002 só vinculava colaboradores cuja
matrícula já batia com um login existente -- quem não tinha
correspondência ficou sem login. Este comando roda a mesma lógica
de criação automática (colaboradores/views.py::_garantir_usuario)
para esses casos pendentes.

Uso:
    python manage.py backfill_usuarios
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from colaboradores.models import ColaboradorCadastro
from usuarios.models import Usuario, UsuarioPerfil


class Command(BaseCommand):
    help = 'Cria o login (Usuario) para colaboradores que ainda nao tem um vinculado.'

    def handle(self, *args, **opcoes):
        pendentes = ColaboradorCadastro.objects.filter(usuario__isnull=True)
        total = pendentes.count()

        if total == 0:
            self.stdout.write(self.style.SUCCESS('Nenhum colaborador pendente. Nada a fazer.'))
            return

        criados = 0
        vinculados = 0

        with transaction.atomic():
            for colaborador in pendentes:
                usuario, criado = Usuario.objects.get_or_create(
                    login=colaborador.registro_empresa
                )
                if criado:
                    UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.USUARIO)
                    criados += 1
                else:
                    vinculados += 1

                colaborador.usuario = usuario
                colaborador.save(update_fields=['usuario'])

        self.stdout.write(
            self.style.SUCCESS(
                f'{total} colaborador(es) processado(s): '
                f'{criados} login(s) novo(s) criado(s), {vinculados} vinculado(s) a login já existente.'
            )
        )
