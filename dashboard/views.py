"""
Views do app dashboard -- paineis agregados sobre RADs sincronizados,
para Supervisor e Administrador (28/08/2026, ampliado 03/09/2026).

Reaproveita a mesma logica de filtro de Servico Executado (macro/micro/
outros) ja usada em consulta/views.py::_aplicar_filtros -- mesmo
raciocinio de combinacao em OR, ver os comentarios la para o historico
completo da decisao. Diferencas daqui pro filtro de Consulta:
  - 'local' e um UNICO parametro que bate com local_inicial OU
    local_final -- o Dashboard nao precisa saber qual dos dois foi
    (decisao do cliente: "nao preciso saber exatamente se comeco ou
    fim").
  - servico_areas aqui aceita MULTIPLAS areas ao mesmo tempo (decisao
    do cliente) -- tecnicamente ja funcionava assim em consulta/
    views.py tambem (o filtro usa __in), so o frontend de Consulta e
    que restringia a selecao a uma area por vez.

Sem filtro nenhum informado na requisicao, este endpoint NAO aplica
nenhum periodo padrao sozinho -- quem decide "ultimos 30 dias" ao
abrir a tela e o frontend (dashboard.js), enviando data_de/data_ate
explicitos na primeira chamada. O backend so aplica o que receber.

Conta apenas RADs com status Sincronizado -- RADs cancelados nao
entram nos calculos (nao fazem sentido nas metricas de duracao/atraso;
decisao do cliente de nao analisar cancelamento aqui, volume baixo).

03/09/2026: ampliado com analises adicionais, todas usando dados que
ja existiam no sistema, sem nenhum campo novo:
  - Top motivos de atraso no termino (lista completa, nao so top N --
    o cliente pediu lista com scroll, nao um recorte).
  - Top 10 locais com mais RAD (inicial + final somados, sem
    distinguir -- mesma logica do filtro 'local').
  - Top 10 usuarios que mais preencheram RAD.
  - MCH mais recorrente no bloco AMV.
  - Bloco Anomalias (Canaleta) por grau de criticidade -- sempre
    calculado aqui, mas o FRONTEND decide se mostra esse painel (so
    quando o servico especifico "Inspecao de Canaleta" estiver
    marcado no filtro de Servico Executado -- decisao do cliente).
  - percentual_atraso_termino ganhou irmao total_atraso_termino (o
    card agora alterna entre % e numero absoluto).

30/09/2026: adicionado "Sync BD" -- sync_bd_dados e
sync_bd_sincronizar, exclusivos do Administrador (nao Supervisor, ao
contrario do resto deste arquivo). Envia os RADs para uma planilha do
Google (rad/google_sheets.py), 1 RAD = 1 linha, servindo como base de
dados externa consultavel fora do sistema.
"""
from django.contrib.postgres.aggregates import ArrayAgg
from django.db.models import Avg, Count, Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

from colaboradores.models import ColaboradorCadastro
from comum.datas import parse_data
from rad.models import Rad, RadAmv, RadCanaleta, RadCanaletaAnomalia
from usuarios.decorators import requer_perfil, requer_token
from usuarios.models import UsuarioPerfil


def _aplicar_filtros(queryset, params):
    if params.get('data_de'):
        queryset = queryset.filter(data_preenchimento__gte=parse_data(params['data_de']))
    if params.get('data_ate'):
        queryset = queryset.filter(data_preenchimento__lte=parse_data(params['data_ate']))
    if params.get('login_usuario'):
        queryset = queryset.filter(usuario__login=params['login_usuario'])
    if params.get('linha'):
        queryset = queryset.filter(linhas__linha_id=params['linha'])
    if params.get('via'):
        queryset = queryset.filter(vias__via_id=params['via'])
    if params.get('local'):
        # Combinado: bate se o local aparecer como inicial OU final,
        # sem distinguir qual (pedido do cliente).
        queryset = queryset.filter(
            Q(local_inicial_id=params['local']) | Q(local_final_id=params['local'])
        )
    if params.get('id_tipo_manutencao'):
        queryset = queryset.filter(tipo_manutencao_id=params['id_tipo_manutencao'])

    # Servico executado -- macro (multiplo) + micro (multiplo) + Outros
    # solto. Nenhum marcado = nao filtra por servico (todos passam).
    servico_areas = params.get('servico_areas')
    servico_ids = params.get('servico_ids')
    servico_outros = params.get('servico_outros') == '1'

    if servico_areas or servico_ids or servico_outros:
        condicao_servico = Q(pk__in=[])  # base vazia, cada trecho abaixo soma em OR

        if servico_areas:
            areas = [a for a in servico_areas.split(',') if a]
            if areas:
                condicao_servico |= Q(servicos__servico__area__in=areas)

        if servico_ids:
            ids = [int(i) for i in servico_ids.split(',') if i.isdigit()]
            if ids:
                condicao_servico |= Q(servicos__servico_id__in=ids)

        if servico_outros:
            condicao_servico |= Q(servicos__servico__nome='Outros')

        queryset = queryset.filter(condicao_servico)

    return queryset.distinct()


def _top_locais(queryset, limite=10):
    """
    03/09/2026. Soma ocorrencias de cada local, tanto como Local
    Inicial quanto Local Final -- um RAD que usa o mesmo local nos
    dois papeis conta 2x para esse local (faz sentido: o local
    apareceu em 2 "pontas" de atividade), mas cada papel e contado
    separadamente porque sao consultas independentes (nao da pra somar
    direto no banco sem duplicar via JOIN).
    """
    contagem = {}

    for item in queryset.values('local_inicial__sigla', 'local_inicial__nome').annotate(
        total=Count('id_rad', distinct=True)
    ):
        chave = (item['local_inicial__sigla'], item['local_inicial__nome'])
        contagem[chave] = contagem.get(chave, 0) + item['total']

    for item in queryset.values('local_final__sigla', 'local_final__nome').annotate(
        total=Count('id_rad', distinct=True)
    ):
        chave = (item['local_final__sigla'], item['local_final__nome'])
        contagem[chave] = contagem.get(chave, 0) + item['total']

    lista = [
        {'sigla': sigla, 'nome': nome, 'total': total}
        for (sigla, nome), total in contagem.items()
    ]
    lista.sort(key=lambda item: -item['total'])
    return lista[:limite]


def _nome_de_usuario(login):
    colaborador = ColaboradorCadastro.objects.filter(usuario__login=login).only('nome').first()
    return colaborador.nome if colaborador else login


@requer_token
@requer_perfil(UsuarioPerfil.SUPERVISOR, UsuarioPerfil.ADMINISTRADOR)
def dados(request):
    """
    GET /dashboard/dados/?data_de=...&data_ate=...&login_usuario=...&linha=...
        &via=...&local=...&id_tipo_manutencao=...&servico_areas=...&servico_ids=...
        &servico_outros=1
    """
    queryset = Rad.objects.filter(status=Rad.SINCRONIZADO)
    queryset = _aplicar_filtros(queryset, request.GET)

    total = queryset.count()

    if total > 0:
        total_atraso_termino = queryset.filter(atraso_termino=True).count()
        percentual_atraso = round((total_atraso_termino / total) * 100, 1)
    else:
        total_atraso_termino = 0
        percentual_atraso = 0

    rads_por_dia = list(
        queryset.values('data_preenchimento')
        .annotate(total=Count('id_rad', distinct=True))
        .order_by('data_preenchimento')
    )

    rads_por_area = list(
        queryset.exclude(servicos__servico__area__isnull=True)
        .values('servicos__servico__area')
        .annotate(total=Count('id_rad', distinct=True))
        .order_by('servicos__servico__area')
    )

    # Top motivos de atraso no termino -- LISTA COMPLETA (o cliente
    # pediu com barra de rolagem, nao um recorte de top N). Motivo do
    # atraso no INICIO nao existe mais no formulario (decisao de
    # negocio de 22/07/2026), entao so ha dado para termino.
    #
    # 03/09/2026: coluna extra com as descricoes de texto livre --
    # relevante so quando o motivo e "Outros" (os demais motivos nao
    # tem campo de descricao). ArrayAgg(distinct=True) junta os
    # valores UNICOS digitados por quem preencheu, sem repetir a mesma
    # frase varias vezes so porque varios RADs usaram o mesmo texto.
    motivos_atraso_bruto = list(
        queryset.filter(atraso_termino=True, motivo_atraso_termino__isnull=False)
        .values('motivo_atraso_termino__nome')
        .annotate(
            total=Count('id_rad', distinct=True),
            descricoes=ArrayAgg(
                'desc_motivo_atraso_termino',
                distinct=True,
                filter=Q(desc_motivo_atraso_termino__isnull=False) & ~Q(desc_motivo_atraso_termino=''),
            ),
        )
        .order_by('-total')
    )
    motivos_atraso = [
        {
            'motivo': item['motivo_atraso_termino__nome'],
            'total': item['total'],
            'descricoes': '; '.join(item['descricoes']) if item['descricoes'] else None,
        }
        for item in motivos_atraso_bruto
    ]

    top_locais = _top_locais(queryset)

    top_usuarios_bruto = list(
        queryset.values('usuario__login')
        .annotate(total=Count('id_rad', distinct=True))
        .order_by('-total')[:10]
    )
    top_usuarios = [
        {'login': item['usuario__login'], 'nome': _nome_de_usuario(item['usuario__login']), 'total': item['total']}
        for item in top_usuarios_bruto
    ]

    # 04/09/2026: exclui blocos com mch_nao_cadastrada=True -- este
    # ranking e sobre MCHs do catalogo que aparecem com frequencia;
    # descricoes de texto livre (uma por bloco, quase sempre unicas)
    # nao fazem sentido como "recorrente".
    top_mch_defeito = list(
        RadAmv.objects.filter(rad__in=queryset, mch__isnull=False)
        .values('mch__identificacao')
        .annotate(total=Count('id', distinct=True))
        .order_by('-total')[:10]
    )

    # Canaleta por grau de criticidade -- sempre calculado aqui; o
    # FRONTEND decide se mostra esse painel (so quando o servico
    # especifico "Inspecao de Canaleta" estiver marcado no filtro,
    # decisao do cliente).
    rotulos_criticidade = dict(RadCanaleta.GRAU_CRITICIDADE_CHOICES)
    canaleta_por_criticidade_bruto = list(
        queryset.filter(canaleta_itens__isnull=False)
        .values('canaleta_itens__grau_criticidade')
        .annotate(total=Count('id_rad', distinct=True))
        .order_by('canaleta_itens__grau_criticidade')
    )
    canaleta_por_criticidade = [
        {
            'grau': item['canaleta_itens__grau_criticidade'],
            'rotulo': rotulos_criticidade.get(item['canaleta_itens__grau_criticidade'], item['canaleta_itens__grau_criticidade']),
            'total': item['total'],
        }
        for item in canaleta_por_criticidade_bruto
    ]

    # 04/09/2026: segundo indicador do bloco Anomalias -- quantidade de
    # cada TIPO de anomalia (Limpa, Obstruída, Ausente, Quebrada,
    # Vegetação, Lastro, Lixo, Dormentes, Entulho, Terra). Um RAD pode
    # ter varias anomalias marcadas ao mesmo tempo -- cada uma conta
    # para o proprio tipo (nao e mutuamente exclusivo, entao a soma
    # dos totais pode passar do numero de RADs com Canaleta).
    rotulos_anomalia = dict(RadCanaletaAnomalia.ANOMALIA_CHOICES)
    canaleta_por_anomalia_bruto = list(
        RadCanaletaAnomalia.objects.filter(canaleta__rad__in=queryset)
        .values('anomalia')
        .annotate(total=Count('id', distinct=True))
        .order_by('-total')
    )
    canaleta_por_anomalia = [
        {
            'anomalia': item['anomalia'],
            'rotulo': rotulos_anomalia.get(item['anomalia'], item['anomalia']),
            'total': item['total'],
        }
        for item in canaleta_por_anomalia_bruto
    ]

    return JsonResponse({
        'total_rads': total,
        'percentual_atraso_termino': percentual_atraso,
        'total_atraso_termino': total_atraso_termino,
        'rads_por_dia': [
            {'data': item['data_preenchimento'].isoformat(), 'total': item['total']}
            for item in rads_por_dia
        ],
        'rads_por_area': [
            {'area': item['servicos__servico__area'], 'total': item['total']}
            for item in rads_por_area
        ],
        'motivos_atraso': motivos_atraso,
        'top_locais': top_locais,
        'top_usuarios': top_usuarios,
        'top_mch_defeito': [
            {'mch': item['mch__identificacao'], 'total': item['total']}
            for item in top_mch_defeito
        ],
        'canaleta_por_criticidade': canaleta_por_criticidade,
        'canaleta_por_anomalia': canaleta_por_anomalia,
    })


@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def exportar_excel(request):
    """
    GET /dashboard/exportar-excel/?<mesmos filtros de dados()>
    Exclusivo do Administrador -- exporta exatamente o conjunto de
    RADs que compoe o resultado filtrado do Dashboard. Reaproveita o
    mesmo gerador de Excel de rad/exportacao_excel.py (o mesmo usado
    em consulta/views.py::exportar_excel).

    Diferente da exportacao de Consulta, esta NAO marca
    data_ultima_exportacao_excel -- e uma extracao de dados pra
    analise, nao o fluxo de "exportar RADs novos" da tela de Consulta.
    """
    queryset = Rad.objects.select_related(
        'local_inicial', 'local_final', 'tipo_manutencao', 'usuario',
        'motivo_atraso_inicio', 'motivo_atraso_termino',
    ).prefetch_related(
        'linhas', 'vias', 'equipes', 'servicos__servico', 'amv_blocos__mch', 'colaboradores',
        'canaleta_itens__anomalias', 'canaleta_itens__lados', 'canaleta_itens__dimensoes',
    ).filter(status=Rad.SINCRONIZADO).order_by('numero_rad')

    queryset = _aplicar_filtros(queryset, request.GET)
    rads = list(queryset)

    if not rads:
        return JsonResponse(
            {'erro': 'Nenhum RAD encontrado para exportar com os filtros informados.'},
            status=404,
        )

    from rad.exportacao_excel import gerar_excel_bytes

    excel_bytes = gerar_excel_bytes(rads)

    resposta = HttpResponse(
        excel_bytes,
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    agora = timezone.now()
    nome_arquivo = f'dashboard_export_{agora.strftime("%Y%m%d_%H%M%S")}.xlsx'
    resposta['Content-Disposition'] = f'attachment; filename="{nome_arquivo}"'
    return resposta


# ---------------------------------------------------------------------------
# Sync BD (30/09/2026) -- exclusivo do Administrador
# ---------------------------------------------------------------------------

# Quantos RADs vao em CADA chamada a API do Sheets (um "lote"). Manter
# baixo (nao centenas) evita segurar memoria demais de uma vez so --
# ver docstring de sync_bd_sincronizar para o raciocinio completo.
TAMANHO_LOTE_SYNC_BD = 200

# Quantos RADs no MAXIMO um unico clique em "Sincronizar" processa,
# mesmo que existam muitos mais pendentes -- protege contra estourar o
# timeout de 60s do gunicorn (ver start.sh) quando ha um backlog grande
# (ex.: primeira vez que a funcionalidade e usada, com todo o historico
# pendente). Se sobrar RAD nao sincronizado depois do limite, o proprio
# contador "Não sincronizados" na tela mostra isso -- um segundo clique
# continua de onde parou, sem duplicar nada (cada RAD so e processado
# uma vez, marcado assim que a linha dele e confirmada na planilha).
MAXIMO_RADS_POR_CLIQUE_SYNC_BD = 600

_PREFETCH_SYNC_BD = (
    'linhas', 'vias', 'equipes', 'servicos__servico', 'amv_blocos__mch', 'colaboradores',
    'canaleta_itens__anomalias', 'canaleta_itens__lados', 'canaleta_itens__dimensoes',
)
_SELECT_RELATED_SYNC_BD = (
    'local_inicial', 'local_final', 'tipo_manutencao', 'usuario',
    'motivo_atraso_inicio', 'motivo_atraso_termino',
)


def _contadores_sync_bd():
    """
    30/09/2026. Os 3 numeros da tela "Sync BD". Inclui RADs CANCELADOS
    tanto no total quanto no que vai pra planilha (decisao do cliente --
    diferente do resto deste arquivo, que so conta Sincronizado).
    """
    total = Rad.objects.count()
    sincronizados = Rad.objects.filter(
        data_ultima_sincronizacao_planilha__isnull=False
    ).count()
    return {
        'total_rad_preenchidos': total,
        'total_rad_sincronizados': sincronizados,
        'total_rad_nao_sincronizados': total - sincronizados,
    }


@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def sync_bd_dados(request):
    """
    GET /dashboard/sync-bd/
    Exclusivo do Administrador. Os 3 numeros da tela "Sync BD" -- usado
    tanto para carregar a tela quanto pelo botao "Atualizar".
    """
    return JsonResponse(_contadores_sync_bd())


@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def sync_bd_sincronizar(request):
    """
    POST /dashboard/sync-bd/sincronizar/
    Exclusivo do Administrador. Envia para a planilha do Google
    (rad/google_sheets.py) todo RAD com data_ultima_sincronizacao_planilha
    NULA -- inclusive cancelados (decisao do cliente).

    Processa em LOTES de TAMANHO_LOTE_SYNC_BD, cada lote numa unica
    chamada a API (values().append() aceita varias linhas de uma vez) --
    e o que evita tanto uma chamada de API por RAD (lento, esbarra em
    cota) quanto carregar milhares de RADs na memoria de uma vez so
    (risco real aqui, com o historico de estouro de memoria do
    servico -- ver conversa sobre o plano de 512MB do Render). Cada
    lote so e marcado como sincronizado DEPOIS que a chamada a API
    confirma -- se um lote falhar no meio do caminho, os lotes
    anteriores ja processados ficam marcados (nao se perde nem duplica
    nada), e a resposta avisa quantos RADs faltam pro Administrador
    tentar de novo.

    MAXIMO_RADS_POR_CLIQUE_SYNC_BD limita quanto um UNICO clique
    processa, para nunca chegar perto do timeout de 60s do gunicorn
    mesmo com um backlog grande -- um segundo clique continua de onde
    parou.
    """
    from rad.google_sheets import SheetsNaoConfiguradoError, enviar_linhas, montar_linha

    pendentes = Rad.objects.select_related(*_SELECT_RELATED_SYNC_BD).prefetch_related(
        *_PREFETCH_SYNC_BD
    ).filter(
        data_ultima_sincronizacao_planilha__isnull=True
    ).order_by('id_rad')[:MAXIMO_RADS_POR_CLIQUE_SYNC_BD]

    pendentes = list(pendentes)

    if not pendentes:
        return JsonResponse({'processados': 0, **_contadores_sync_bd()})

    total_processado = 0
    agora = timezone.now()

    for inicio in range(0, len(pendentes), TAMANHO_LOTE_SYNC_BD):
        lote = pendentes[inicio:inicio + TAMANHO_LOTE_SYNC_BD]

        try:
            linhas = [montar_linha(rad) for rad in lote]
            enviar_linhas(linhas)
        except SheetsNaoConfiguradoError as erro:
            return JsonResponse(
                {'erro': str(erro), 'processados': total_processado, **_contadores_sync_bd()},
                status=503,
            )
        except Exception as erro:
            # Mesmo padrao ja usado em rad/google_drive.py -- resposta
            # generica pro cliente, erro real no log do Render pra
            # diagnosticar (falha de rede, cota da API excedida, etc.).
            print(f'[ERRO] Falha ao enviar lote pra planilha (Sync BD): {erro!r}')
            return JsonResponse(
                {
                    'erro': 'Não foi possível enviar um dos lotes para a planilha. Tente novamente.',
                    'processados': total_processado,
                    **_contadores_sync_bd(),
                },
                status=502,
            )

        ids_do_lote = [rad.id_rad for rad in lote]
        Rad.objects.filter(id_rad__in=ids_do_lote).update(
            data_ultima_sincronizacao_planilha=agora
        )
        total_processado += len(lote)

    return JsonResponse({'processados': total_processado, **_contadores_sync_bd()})
