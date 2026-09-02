"""
Views do app dashboard -- paineis agregados sobre RADs sincronizados,
para Supervisor e Administrador (28/08/2026).

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
entram nos calculos (nao fazem sentido nas metricas de duracao/atraso).
"""
from django.db.models import Avg, Count, Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

from colaboradores.models import ColaboradorCadastro
from comum.datas import parse_data
from rad.models import Rad
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
        atrasados_termino = queryset.filter(atraso_termino=True).count()
        percentual_atraso = round((atrasados_termino / total) * 100, 1)
        duracao_media = queryset.aggregate(media=Avg('duracao_real_min'))['media']
        duracao_media = round(duracao_media) if duracao_media is not None else 0
    else:
        percentual_atraso = 0
        duracao_media = 0

    # Colaboradores ativos: cadastro atual, nao filtrado por data --
    # e uma foto de "agora", nao do periodo pesquisado.
    colaboradores_ativos = ColaboradorCadastro.objects.filter(ativo=True).count()

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

    return JsonResponse({
        'total_rads': total,
        'percentual_atraso_termino': percentual_atraso,
        'duracao_media_real_min': duracao_media,
        'colaboradores_ativos': colaboradores_ativos,
        'rads_por_dia': [
            {'data': item['data_preenchimento'].isoformat(), 'total': item['total']}
            for item in rads_por_dia
        ],
        'rads_por_area': [
            {'area': item['servicos__servico__area'], 'total': item['total']}
            for item in rads_por_area
        ],
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
        'motivo_atraso_inicio', 'motivo_atraso_termino', 'canaleta',
    ).prefetch_related(
        'linhas', 'vias', 'equipes', 'servicos__servico', 'amv_blocos__mch', 'colaboradores',
        'canaleta__anomalias', 'canaleta__lados', 'canaleta__dimensoes',
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
