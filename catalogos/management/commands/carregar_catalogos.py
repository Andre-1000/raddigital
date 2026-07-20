"""
Comando: python manage.py carregar_catalogos

Executa os arquivos seed_cat_*.sql (pasta seeds_sql/ na raiz do projeto)
diretamente no banco, na ordem correta. Os nomes de tabela/coluna dos
modelos foram definidos identicos aos dos seeds, entao nenhuma adaptacao
e necessaria.

Uso:
    python manage.py carregar_catalogos
    python manage.py carregar_catalogos --arquivo seed_cat_linhas.sql
"""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection

# Ordem de carga: catalogos independentes primeiro. Nenhum destes tem FK
# entre si, mas mantemos a ordem do briefing para clareza.
ARQUIVOS_SEED = [
    'seed_cat_linhas.sql',
    'seed_cat_locais.sql',
    'seed_cat_tipos_manutencao.sql',
    'seed_cat_vias.sql',
    'seed_cat_servicos.sql',
    'seed_cat_motivos_atraso.sql',
    'seed_cat_mch.sql',
    'seed_cat_tipos_defeito_amv.sql',
    'seed_cat_acoes_amv.sql',
    'seed_cat_equipes.sql',
]


class Command(BaseCommand):
    help = 'Carrega os catalogos do sistema a partir dos arquivos seed_cat_*.sql'

    def add_arguments(self, parser):
        parser.add_argument(
            '--arquivo',
            type=str,
            help='Nome de um unico arquivo seed para carregar (opcional).',
        )

    def handle(self, *args, **options):
        pasta_seeds = Path(settings.BASE_DIR) / 'seeds_sql'
        if not pasta_seeds.exists():
            raise CommandError(f'Pasta de seeds nao encontrada: {pasta_seeds}')

        arquivos = [options['arquivo']] if options.get('arquivo') else ARQUIVOS_SEED

        with connection.cursor() as cursor:
            for nome_arquivo in arquivos:
                caminho = pasta_seeds / nome_arquivo
                if not caminho.exists():
                    self.stderr.write(
                        self.style.WARNING(f'Arquivo nao encontrado, pulando: {nome_arquivo}')
                    )
                    continue

                sql = caminho.read_text(encoding='utf-8')
                cursor.execute(sql)
                self.stdout.write(self.style.SUCCESS(f'Carregado: {nome_arquivo}'))

        self.stdout.write(self.style.SUCCESS('Catalogos carregados com sucesso.'))
