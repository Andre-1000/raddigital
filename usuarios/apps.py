from django.apps import AppConfig


class UsuariosConfig(AppConfig):
    name = 'usuarios'

    def ready(self):
        # 30/07/2026: registra os sinais de login do /admin/ (Seguranca
        # A02) -- precisa ser importado aqui, e nao no topo do arquivo,
        # porque `ready()` roda depois que todos os apps ja carregaram
        # (import direto no topo do apps.py pode disparar erro de app
        # nao pronto ainda, dependendo da ordem de carregamento).
        from . import signals  # noqa: F401
