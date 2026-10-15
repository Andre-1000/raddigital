"""
Exportacao para Excel (.xlsx) -- 21/08/2026.

Formato "1 RAD = 1 linha, 1 campo = 1 coluna", pensado para consumo em
ferramentas de BI (Excel/Power Query, Looker Studio etc.) usadas pelos
colaboradores para acompanhar as pesquisas diarias -- nao para o
layout oficial do documento RDA (esse continua em
rad/exportacao_oficial.py, formato Word).

Campos de multipla selecao (Linhas, Vias, Equipes, Servicos,
Colaboradores, MCHs do bloco AMV) sao achatados em uma unica celula de
texto, separados por '; ' -- nao ha como representar uma relacao
1-para-N numa planilha onde cada RAD e uma linha so. Quem precisar do
detalhe individual (ex.: por MCH ou por colaborador) deve usar a tela
de Consulta ou a API, nao o Excel.

15/10/2026 (BI-RAD): a coluna "Serviços" passa a trazer a AREA de cada
servico junto do nome, no formato "Área > Serviço" (ex.:
"Geral > Soldagem; Infra > Roçada/Poda"). Antes ia so o nome e a area
(bloco de Servicos Executados do formulario) se perdia -- o BI nao
conseguia analisar por area sem uma tabela de-para mantida a mao.
O par area+servico viaja junto no mesmo item, entao quem dividir por
'; ' e depois por ' > ' nunca descasa um do outro. A area e a ATUAL do
catalogo (CatServico.area), nao a da epoca do RAD. Vale para os tres
consumidores desta funcao: planilha do Google (rad/google_sheets.py),
Excel do Dashboard e Excel da Consulta. Sem migration.
"""
import io

from django.utils import timezone as django_timezone
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from catalogos.models import CatServico

# Codigo da area -> rotulo exibido na tela (ex.: 'insp_ronda' ->
# 'Inspeção e Ronda'). Lido de AREA_CHOICES para nunca ficar
# desatualizado quando uma area nova for criada.
_ROTULO_AREA = dict(CatServico.AREA_CHOICES)
SEPARADOR_AREA = ' > '

COLUNAS = [
    ('numero_rad', 'Número RAD'),
    ('numero_os', 'OS'),
    ('numero_sa', 'SA'),
    ('status', 'Status'),
    ('data_preenchimento', 'Data'),
    ('local_inicial', 'Local Inicial'),
    ('local_final', 'Local Final'),
    ('tipo_manutencao', 'Tipo de Manutenção'),
    ('numero_falha', 'Nº Falha'),
    ('hora_prog_inicio', 'Hora Prog. Início'),
    ('hora_prog_termino', 'Hora Prog. Término'),
    ('hora_real_inicio', 'Hora Real Início'),
    ('hora_real_termino', 'Hora Real Término'),
    ('duracao_programada_min', 'Duração Programada (min)'),
    ('duracao_real_min', 'Duração Real (min)'),
    ('atraso_inicio', 'Atraso Início'),
    ('motivo_atraso_inicio', 'Motivo Atraso Início'),
    ('atraso_termino', 'Atraso Término'),
    ('motivo_atraso_termino', 'Motivo Atraso Término'),
    ('linhas', 'Linhas'),
    ('vias', 'Vias'),
    ('equipes', 'Equipes'),
    ('servicos', 'Serviços'),
    ('mchs', 'MCHs (Bloco AMV)'),
    ('colaboradores', 'Colaboradores'),
    # 21/08/2026: bloco "Anomalias" (Canaleta) -- so tem valor quando o
    # servico "Inspeção de Canaleta" foi selecionado nesse RAD; vazio
    # para os demais.
    ('canaleta_grau_criticidade', 'Canaleta - Grau de Criticidade'),
    ('canaleta_necessita_cautela', 'Canaleta - Necessita Cautela'),
    ('canaleta_anomalias', 'Canaleta - Anomalias'),
    ('canaleta_lados', 'Canaleta - Lado'),
    ('canaleta_justificativa', 'Canaleta - Justificativa'),
    ('canaleta_dimensoes', 'Canaleta - Dimensões'),
    ('login_usuario', 'Login de Quem Preencheu'),
    ('dispositivo', 'Dispositivo'),
    ('data_sincronizacao', 'Data de Sincronização'),
]


def _valor_ou_vazio(valor):
    return valor if valor not in (None, '') else ''


def _sem_timezone(valor_datetime):
    """
    O Excel (e o openpyxl) nao aceita datetime com timezone -- so
    aceita "horario de parede" puro. Django guarda data_sincronizacao
    com timezone (USE_TZ=True); converte para o horario local
    configurado no projeto e remove o tzinfo antes de gravar na
    celula, para nao perder as 3h de diferenca (UTC vs America/Sao_Paulo)
    silenciosamente.
    """
    if valor_datetime is None:
        return None
    return django_timezone.localtime(valor_datetime).replace(tzinfo=None)


def _campos_canaleta(rad):
    """
    "Anomalias Observadas" (21/08/2026, redesenhado 15/09/2026):
    achata TODOS os itens do RAD (agora pode ter varios, ate 15 --
    mesmo padrao do bloco AMV) em texto para as colunas do Excel,
    separando cada item por '; '. Sem nenhum item, todas as colunas
    ficam vazias, sem erro.
    """
    itens = list(rad.canaleta_itens.all())
    if not itens:
        return {
            'canaleta_grau_criticidade': '',
            'canaleta_necessita_cautela': '',
            'canaleta_anomalias': '',
            'canaleta_lados': '',
            'canaleta_justificativa': '',
            'canaleta_dimensoes': '',
        }

    graus, cautelas, anomalias_todas, lados_todos, justificativas, linhas_dimensao = (
        [], [], [], [], [], []
    )

    for canaleta in itens:
        graus.append(canaleta.get_grau_criticidade_display())
        cautelas.append('Sim' if canaleta.necessita_cautela else 'Não')
        anomalias_todas.extend(a.get_anomalia_display() for a in canaleta.anomalias.all())
        lados_todos.extend(l.get_lado_display() for l in canaleta.lados.all())
        if canaleta.justificativa:
            justificativas.append(canaleta.justificativa)

        # 15/09/2026: item novo -- Dimensoes sao campos diretos, um
        # conjunto so. Campos nao identificados ficam como "?".
        if any(
            v is not None
            for v in (
                canaleta.largura_inicial, canaleta.largura_final,
                canaleta.altura_inicial, canaleta.altura_final,
                canaleta.comprimento, canaleta.km_poste_inicial, canaleta.km_poste_final,
            )
        ):
            km = (
                f' (Km {canaleta.km_poste_inicial or "?"} - {canaleta.km_poste_final or "?"})'
                if canaleta.km_poste_inicial or canaleta.km_poste_final else ''
            )
            linhas_dimensao.append(
                f'L:{canaleta.largura_inicial if canaleta.largura_inicial is not None else "?"}'
                f'-{canaleta.largura_final if canaleta.largura_final is not None else "?"} '
                f'A:{canaleta.altura_inicial if canaleta.altura_inicial is not None else "?"}'
                f'-{canaleta.altura_final if canaleta.altura_final is not None else "?"} '
                f'C:{canaleta.comprimento if canaleta.comprimento is not None else "?"}{km}'
            )

        # RADs sincronizados antes desta mudanca: Dimensoes vivem na
        # tabela antiga (RadCanaletaDimensao), possivelmente varias
        # linhas por item.
        for d in canaleta.dimensoes.all():
            km = (
                f' (Km {d.km_poste_inicial} - {d.km_poste_final})'
                if d.km_poste_inicial or d.km_poste_final else ''
            )
            linhas_dimensao.append(
                f'L:{d.largura_inicial}-{d.largura_final} '
                f'A:{d.altura_inicial}-{d.altura_final} '
                f'C:{d.comprimento}{km}'
            )

    return {
        'canaleta_grau_criticidade': '; '.join(graus),
        'canaleta_necessita_cautela': '; '.join(cautelas),
        'canaleta_anomalias': '; '.join(anomalias_todas),
        'canaleta_lados': '; '.join(lados_todos),
        'canaleta_justificativa': '; '.join(justificativas),
        'canaleta_dimensoes': ' | '.join(linhas_dimensao),
    }


def _rotulo_area(codigo):
    """
    Rotulo legivel da area. Codigo desconhecido (area criada no banco
    sem estar em AREA_CHOICES) aparece como o proprio codigo, e area
    vazia como 'Sem área' -- nunca quebra a exportacao.
    """
    if not codigo:
        return 'Sem área'
    return _ROTULO_AREA.get(codigo, codigo)


def _servicos_com_area(rad):
    """'Área > Serviço' de cada servico do RAD, separados por '; '."""
    return '; '.join(
        f'{_rotulo_area(area)}{SEPARADOR_AREA}{nome}'
        for area, nome in rad.servicos.values_list('servico__area', 'servico__nome')
    )


def _linha_para_rad(rad):
    return {
        'numero_rad': rad.numero_rad,
        'numero_os': rad.numero_os,
        'numero_sa': rad.numero_sa,
        'status': rad.get_status_display(),
        'data_preenchimento': rad.data_preenchimento,
        'local_inicial': rad.local_inicial.sigla,
        'local_final': rad.local_final.sigla,
        'tipo_manutencao': rad.tipo_manutencao.nome,
        'numero_falha': rad.numero_falha,
        'hora_prog_inicio': rad.hora_prog_inicio,
        'hora_prog_termino': rad.hora_prog_termino,
        'hora_real_inicio': rad.hora_real_inicio,
        'hora_real_termino': rad.hora_real_termino,
        'duracao_programada_min': rad.duracao_programada_min,
        'duracao_real_min': rad.duracao_real_min,
        'atraso_inicio': 'Sim' if rad.atraso_inicio else 'Não',
        'motivo_atraso_inicio': (
            rad.motivo_atraso_inicio.nome if rad.motivo_atraso_inicio else ''
        ),
        'atraso_termino': 'Sim' if rad.atraso_termino else 'Não',
        'motivo_atraso_termino': (
            rad.motivo_atraso_termino.nome if rad.motivo_atraso_termino else ''
        ),
        'linhas': '; '.join(str(v) for v in rad.linhas.values_list('linha_id', flat=True)),
        'vias': '; '.join(rad.vias.values_list('via__nome', flat=True)),
        'equipes': '; '.join(rad.equipes.values_list('equipe_id', flat=True)),
        # 15/10/2026: "Área > Serviço" (ver docstring do modulo).
        'servicos': _servicos_com_area(rad),
        # 04/09/2026: um bloco AMV pode ter mch=None (via "MCH não
        # cadastrada") -- nesse caso mostra o texto livre digitado no
        # lugar da identificação real, prefixado para ficar claro que
        # não é uma MCH do catálogo.
        'mchs': '; '.join(
            (amv.mch.identificacao if amv.mch else f'Não cadastrada: {amv.desc_mch_nao_cadastrada}')
            for amv in rad.amv_blocos.all()
        ),
        'colaboradores': '; '.join(c.nome for c in rad.colaboradores.all()),
        **_campos_canaleta(rad),
        'login_usuario': rad.usuario_id,
        'dispositivo': rad.get_dispositivo_display(),
        'data_sincronizacao': _sem_timezone(rad.data_sincronizacao),
    }


def gerar_excel_bytes(rads):
    """
    Recebe uma lista (ou queryset ja avaliado) de Rad, com
    select_related/prefetch_related ja aplicados pelo chamador, e
    retorna os bytes de um .xlsx pronto para download -- uma linha por
    RAD.
    """
    workbook = Workbook()
    planilha = workbook.active
    planilha.title = 'RADs'

    cabecalho = [rotulo for _, rotulo in COLUNAS]
    planilha.append(cabecalho)

    for rad in rads:
        dados = _linha_para_rad(rad)
        planilha.append([_valor_ou_vazio(dados.get(chave)) for chave, _ in COLUNAS])

    for indice, (_, rotulo) in enumerate(COLUNAS, start=1):
        largura = max(len(rotulo) + 2, 14)
        planilha.column_dimensions[get_column_letter(indice)].width = largura

    buffer_saida = io.BytesIO()
    workbook.save(buffer_saida)
    return buffer_saida.getvalue()
