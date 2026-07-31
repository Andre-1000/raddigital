"""
Views do app consulta — Tela de Consulta de RADs (EFD secao 4.6).

Listagem administrativa (listar_rads) e detalhe (detalhe_rad): acesso
Supervisor, Administrador, ou o proprio criador do RAD (PRM-028 a
PRM-038 + tela "RADs Preenchidos", 22/07/2026).
listar_meus_rads: qualquer usuario autenticado, sempre filtrado ao
proprio login.

22/07/2026: exportacao pos-sincronizacao agora usa exclusivamente o
layout oficial (rad/exportacao_oficial.py) -- o antigo layout simples
(rad/exportacao.py, endpoints /pdf/ e /docx/) foi descontinuado.
"""
from django.core.paginator import Paginator
from django.http import FileResponse, HttpResponse, JsonResponse

from comum.datas import parse_data, parse_datetime_aware
from usuarios.decorators import requer_perfil, requer_token
from usuarios.models import UsuarioPerfil

from rad.models import Rad

RADS_POR_PAGINA = 15  # PRM-032


def _remover_campos_desabilitados(dados):
    """
    Regra de negocio (17/07/2026): campo desabilitado nao aparece para
    nenhum usuario -- inclusive Supervisor e Administrador na tela de
    consulta. Remove do dicionario de resposta qualquer chave que
    corresponda a um campo desabilitado. Generico: funciona para
    qualquer chave presente em configuracoes.CampoFormulario, sem
    precisar listar campos manualmente aqui.

    Limitacao conhecida: os anexos (fotos_intervencao_verificada,
    fotos_acao_realizada, pdf) sao combinados em uma unica chave
    'anexos' na resposta -- desabilitar so uma categoria de foto ainda
    nao filtra parcialmente esse bloco.
    """
    from configuracoes.servicos import campos_desabilitados

    for chave in campos_desabilitados():
        dados.pop(chave, None)
    return dados


def _aplicar_filtros(queryset, params):
    """
    PRM-028: um ou mais filtros aplicados simultaneamente (AND).
    PRM-029: lista de filtros permitidos.
    PRM-030: campos de multipla selecao (servicos, colaboradores, via,
    linha do RAD) NAO sao filtraveis aqui -- so aparecem no detalhe.
    Excepcao explicita da propria EFD: MCH e Linha da MCH (do bloco AMV,
    valor unico por RAD) SAO filtraveis.
    """
    if params.get('numero_rad'):
        queryset = queryset.filter(numero_rad=params['numero_rad'])
    if params.get('numero_os'):
        queryset = queryset.filter(numero_os=params['numero_os'])
    if params.get('numero_sa'):
        queryset = queryset.filter(numero_sa=params['numero_sa'])
    if params.get('status'):
        queryset = queryset.filter(status=params['status'])
    if params.get('data_de'):
        queryset = queryset.filter(data_preenchimento__gte=parse_data(params['data_de']))
    if params.get('data_ate'):
        queryset = queryset.filter(data_preenchimento__lte=parse_data(params['data_ate']))
    if params.get('id_local_inicial'):
        queryset = queryset.filter(local_inicial_id=params['id_local_inicial'])
    if params.get('id_local_final'):
        queryset = queryset.filter(local_final_id=params['id_local_final'])
    if params.get('id_tipo_manutencao'):
        queryset = queryset.filter(tipo_manutencao_id=params['id_tipo_manutencao'])
    if params.get('numero_falha'):
        queryset = queryset.filter(numero_falha=params['numero_falha'])
    if params.get('id_mch'):
        queryset = queryset.filter(amv__mch_id=params['id_mch'])
    if params.get('linha_mch'):
        queryset = queryset.filter(amv__linha_mch=params['linha_mch'])
    if params.get('login_usuario'):
        queryset = queryset.filter(usuario__login=params['login_usuario'])
    if params.get('dispositivo'):
        queryset = queryset.filter(dispositivo=params['dispositivo'])
    if params.get('hp_inicio_de'):
        queryset = queryset.filter(
            data_hora_prog_inicio__gte=parse_datetime_aware(params['hp_inicio_de'])
        )
    if params.get('hp_inicio_ate'):
        queryset = queryset.filter(
            data_hora_prog_inicio__lte=parse_datetime_aware(params['hp_inicio_ate'])
        )
    if params.get('hr_inicio_de'):
        queryset = queryset.filter(
            data_hora_real_inicio__gte=parse_datetime_aware(params['hr_inicio_de'])
        )
    if params.get('hr_inicio_ate'):
        queryset = queryset.filter(
            data_hora_real_inicio__lte=parse_datetime_aware(params['hr_inicio_ate'])
        )
    return queryset


def _linha_resumo(rad):
    """Monta uma linha da lista de resultados (PRM-034/035)."""
    return {
        'numero_rad': rad.numero_rad,
        'numero_os': rad.numero_os,
        'numero_sa': rad.numero_sa,
        'status': rad.status,
        'data_preenchimento': rad.data_preenchimento.isoformat(),
        'local_inicial': rad.local_inicial.sigla,
        'local_final': rad.local_final.sigla,
        'tipo_manutencao': rad.tipo_manutencao.nome,
        'numero_falha': rad.numero_falha,
        'identificacao_mch': rad.amv.mch.identificacao if hasattr(rad, 'amv') else None,
        'linha_mch': rad.amv.linha_mch if hasattr(rad, 'amv') else None,
        'login_usuario': rad.usuario.login,
        'hora_prog_inicio': rad.hora_prog_inicio.isoformat(),
        'hora_real_inicio': rad.hora_real_inicio.isoformat(),
        'dispositivo': rad.get_dispositivo_display(),
    }


@requer_token
@requer_perfil(UsuarioPerfil.SUPERVISOR, UsuarioPerfil.ADMINISTRADOR)
def listar_rads(request):
    """
    GET /consulta/rads/?numero_os=1234&status=sincronizado&pagina=1 ...
    Acesso: Supervisor e Administrador (RG conforme EFD 4.6 "Acesso").
    """
    queryset = Rad.objects.select_related(
        'local_inicial', 'local_final', 'tipo_manutencao', 'usuario'
    ).prefetch_related('amv__mch').order_by('-data_sincronizacao')

    queryset = _aplicar_filtros(queryset, request.GET)

    numero_pagina = request.GET.get('pagina') or 1
    paginador = Paginator(queryset, RADS_POR_PAGINA)  # PRM-032
    pagina = paginador.get_page(numero_pagina)

    return JsonResponse(
        {
            'total_encontrado': paginador.count,  # PRM-031
            'pagina_atual': pagina.number,
            'total_paginas': paginador.num_pages,
            'resultados': [
                _remover_campos_desabilitados(_linha_resumo(rad)) for rad in pagina.object_list
            ],
        }
    )


def _pode_ver_dispositivo(usuario):
    """
    Regra de negocio (22/07/2026): o campo Dispositivo (computador/
    celular) so e visivel para Supervisor e Administrador -- um
    Usuario comum nunca ve essa informacao, nem na lista "RADs
    Preenchidos" nem no detalhe do RAD, mesmo sendo o proprio autor.
    """
    perfis = set(usuario.lista_perfis)
    return UsuarioPerfil.SUPERVISOR in perfis or UsuarioPerfil.ADMINISTRADOR in perfis


@requer_token
def listar_meus_rads(request):
    """
    GET /consulta/meus-rads/?pagina=1
    Tela "RADs Preenchidos" (22/07/2026) -- qualquer usuario
    autenticado, qualquer perfil, sempre filtrado ao proprio login.
    Sem filtros administrativos (o volume por pessoa e naturalmente
    pequeno); so pagina e mostra tudo que ela mesma preencheu.
    """
    queryset = Rad.objects.select_related(
        'local_inicial', 'local_final', 'tipo_manutencao', 'usuario'
    ).filter(usuario_id=request.usuario_rad.login).order_by('-data_sincronizacao')

    numero_pagina = request.GET.get('pagina') or 1
    paginador = Paginator(queryset, RADS_POR_PAGINA)
    pagina = paginador.get_page(numero_pagina)

    mostrar_dispositivo = _pode_ver_dispositivo(request.usuario_rad)

    def _linha(rad):
        dados = _remover_campos_desabilitados(_linha_resumo(rad))
        if not mostrar_dispositivo:
            dados.pop('dispositivo', None)
        return dados

    return JsonResponse(
        {
            'total_encontrado': paginador.count,
            'pagina_atual': pagina.number,
            'total_paginas': paginador.num_pages,
            'resultados': [_linha(rad) for rad in pagina.object_list],
        }
    )


def _colaboradores_resumo(rad):
    return [
        {'registro_empresa': c.registro_empresa, 'nome': c.nome, 'tipo': c.tipo}
        for c in rad.colaboradores.all()
    ]


def _anexos_resumo(rad):
    return [
        {
            'id': a.id,
            'tipo_arquivo': a.tipo_arquivo,
            'categoria_foto': a.get_categoria_foto_display() if a.categoria_foto else None,
            'nome_original': a.nome_original,
            'tamanho_bytes': a.tamanho_bytes,
        }
        for a in rad.anexos.all()
    ]


def _amv_resumo(rad):
    if not hasattr(rad, 'amv'):
        return None
    amv = rad.amv
    return {
        'identificacao_mch': amv.mch.identificacao,
        'modelo_mch': amv.modelo_mch,
        'via_mch': amv.via_mch,
        'ur_mch': amv.ur_mch,
        'local_mch': amv.local_mch,
        'linha_mch': amv.linha_mch,
        'tipos_defeito': list(rad.amv_defeitos.values_list('tipo_defeito__nome', flat=True)),
        'acoes': list(rad.amv_acoes.values_list('acao__nome', flat=True)),
        'desc_outros_tipo_defeito': amv.desc_outros_tipo_defeito,
        'desc_outros_acao': amv.desc_outros_acao,
    }


def nome_de_quem_preencheu(rad):
    """
    Nome completo de quem preencheu o RAD (22/07/2026) -- usado no
    export oficial no lugar de "RESPONSAVEL RAD" digitado manualmente.
    Busca o nome no cadastro de colaboradores vinculado ao login que
    sincronizou o RAD; se essa pessoa nao tiver cadastro de colaborador
    (raro -- ex.: usuario criado direto pelo app de usuarios, sem
    passar pelo cadastro de colaboradores), cai para o proprio login.
    """
    colaborador = getattr(rad.usuario, 'colaborador', None)
    if colaborador and colaborador.nome:
        return colaborador.nome
    return rad.usuario.login


def _exportacao_pdf_oficial_habilitada():
    """
    22/07/2026: le o interruptor da tela de Configuracoes
    (CampoFormulario.chave='exportar_pdf_oficial'). Desligado ate o
    LibreOffice ser instalado no servidor -- ver
    rad/exportacao_oficial.py::gerar_pdf_oficial_bytes.
    """
    from configuracoes.models import CampoFormulario

    campo = CampoFormulario.objects.filter(chave='exportar_pdf_oficial').first()
    return bool(campo and campo.habilitado)


@requer_token
def mensagem_copiar(request, numero_rad):
    """
    GET /consulta/rads/<numero_rad>/mensagem/
    RG-EXP-013. Acesso: Supervisor, Administrador, ou o proprio
    tecnico que criou o RAD (RG-EXP-001 previa que quem preenche pode
    exportar; aqui a exportacao e pos-sincronizacao, entao mantemos o
    criador com acesso ao seu proprio RAD).
    """
    try:
        rad = Rad.objects.select_related(
            'local_inicial', 'local_final', 'usuario',
            'motivo_atraso_inicio', 'motivo_atraso_termino',
        ).get(numero_rad=numero_rad)
    except Rad.DoesNotExist:
        return JsonResponse({'erro': 'RAD nao encontrado.'}, status=404)

    if not _pode_exportar(request.usuario_rad, rad):
        return JsonResponse({'erro': 'Acesso nao autorizado.'}, status=403)

    from rad.exportacao import gerar_mensagem_copiar

    return JsonResponse({'mensagem': gerar_mensagem_copiar(rad)})


def _carregar_rad_para_exportacao(numero_rad):
    return Rad.objects.select_related(
        'local_inicial', 'local_final', 'tipo_manutencao', 'usuario',
        'motivo_atraso_inicio', 'motivo_atraso_termino',
    ).prefetch_related(
        'servicos__servico', 'colaboradores', 'anexos', 'linhas', 'vias', 'equipes'
    ).get(numero_rad=numero_rad)


@requer_token
def exportar_docx_oficial(request, numero_rad):
    """
    GET /consulta/rads/<numero_rad>/docx-oficial/
    22/07/2026: unico formato de exportacao de arquivo pos-
    sincronizacao do sistema -- layout do documento RDA oficial da
    TRIVIA (RDA_Relatorio_Trivia_Ajustado_original.docx), usado como
    molde. Sempre disponivel (nao depende de nenhuma instalacao extra
    no servidor, ao contrario do PDF -- ver exportar_pdf_oficial).
    """
    try:
        rad = _carregar_rad_para_exportacao(numero_rad)
    except Rad.DoesNotExist:
        return JsonResponse({'erro': 'RAD nao encontrado.'}, status=404)

    if not _pode_exportar(request.usuario_rad, rad):
        return JsonResponse({'erro': 'Acesso nao autorizado.'}, status=403)

    from rad.exportacao_oficial import gerar_docx_oficial_bytes

    docx_bytes = gerar_docx_oficial_bytes(rad)
    resposta = HttpResponse(
        docx_bytes,
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    resposta['Content-Disposition'] = f'attachment; filename="{rad.numero_rad}.docx"'
    return resposta


@requer_token
def exportar_pdf_oficial(request, numero_rad):
    """
    GET /consulta/rads/<numero_rad>/pdf-oficial/
    22/07/2026: mesmo layout oficial, em PDF -- exige LibreOffice no
    servidor (ver rad/exportacao_oficial.py::gerar_pdf_oficial_bytes).
    So funciona quando o Administrador habilitar "Exportação em PDF
    (layout oficial)" na tela de Configuracoes -- desligado por
    padrao, porque o servidor de producao atual nao tem o LibreOffice
    instalado (risco de OOM no plano gratuito do Render).
    """
    if not _exportacao_pdf_oficial_habilitada():
        return JsonResponse(
            {
                'erro': (
                    'A exportação em PDF está desabilitada. '
                    'Um Administrador pode habilitá-la em Configurações, '
                    'quando o servidor tiver suporte a essa conversão.'
                )
            },
            status=403,
        )

    try:
        rad = _carregar_rad_para_exportacao(numero_rad)
    except Rad.DoesNotExist:
        return JsonResponse({'erro': 'RAD nao encontrado.'}, status=404)

    if not _pode_exportar(request.usuario_rad, rad):
        return JsonResponse({'erro': 'Acesso nao autorizado.'}, status=403)

    from rad.exportacao_oficial import PdfNaoDisponivelError, gerar_pdf_oficial_bytes

    try:
        pdf_bytes = gerar_pdf_oficial_bytes(rad)
    except PdfNaoDisponivelError as erro:
        return JsonResponse({'erro': str(erro)}, status=503)

    resposta = HttpResponse(pdf_bytes, content_type='application/pdf')
    resposta['Content-Disposition'] = f'attachment; filename="{rad.numero_rad}.pdf"'
    return resposta


@requer_token
def visualizar_anexo(request, numero_rad, id_anexo):
    """
    GET /consulta/rads/<numero_rad>/anexos/<id_anexo>/?baixar=1
    Novo (22/07/2026): serve o arquivo de uma foto ou PDF anexado a um
    RAD ja sincronizado. Mesma regra de acesso das outras rotas de
    exportacao (_pode_exportar): Supervisor, Administrador, ou o
    proprio criador do RAD -- nunca publico, mesmo com o link em maos.

    Sem '?baixar=1': serve inline (abre no navegador -- usado para
    "Ver" uma foto). Com '?baixar=1': forca download
    (Content-Disposition attachment).
    """
    from django.core.files.storage import default_storage

    from rad.models import RadAnexo

    try:
        rad = Rad.objects.get(numero_rad=numero_rad)
    except Rad.DoesNotExist:
        return JsonResponse({'erro': 'RAD nao encontrado.'}, status=404)

    if not _pode_exportar(request.usuario_rad, rad):
        return JsonResponse({'erro': 'Acesso nao autorizado.'}, status=403)

    try:
        anexo = RadAnexo.objects.get(id=id_anexo, rad=rad)
    except RadAnexo.DoesNotExist:
        return JsonResponse({'erro': 'Anexo nao encontrado para este RAD.'}, status=404)

    if not default_storage.exists(anexo.caminho_servidor):
        return JsonResponse({'erro': 'Arquivo nao encontrado no servidor.'}, status=404)

    arquivo = default_storage.open(anexo.caminho_servidor, 'rb')
    content_type = 'application/pdf' if anexo.tipo_arquivo == RadAnexo.PDF else 'image/jpeg'
    resposta = FileResponse(arquivo, content_type=content_type)

    forcar_download = request.GET.get('baixar') == '1'
    disposicao = 'attachment' if forcar_download else 'inline'
    resposta['Content-Disposition'] = f'{disposicao}; filename="{anexo.nome_original}"'
    return resposta


def _pode_exportar(usuario, rad):
    """
    rad.usuario e uma FK com to_field='login' (ver rad/models.py), entao
    rad.usuario_id guarda o LOGIN, nao o id numerico do Usuario -- por
    isso a comparacao e contra usuario.login, nao usuario.id.
    """
    perfis = set(usuario.lista_perfis)
    if UsuarioPerfil.SUPERVISOR in perfis or UsuarioPerfil.ADMINISTRADOR in perfis:
        return True
    return rad.usuario_id == usuario.login


@requer_token
def detalhe_rad(request, numero_rad):
    """
    GET /consulta/rads/<numero_rad>/
    PRM-036: todas as informacoes do RAD, incluindo campos de multipla
    selecao e anexos.
    PRM-037: 'pode_cancelar' so e True para Administrador, e somente se
    o RAD ainda nao estiver cancelado (RG-CAN-009).
    Acesso: Supervisor, Administrador, ou o proprio criador do RAD
    (22/07/2026 -- tela "RADs Preenchidos", mesma regra de
    _pode_exportar).
    """
    try:
        rad = Rad.objects.select_related(
            'local_inicial', 'local_final', 'tipo_manutencao', 'usuario',
            'motivo_atraso_inicio', 'motivo_atraso_termino', 'usuario_cancelamento',
        ).get(numero_rad=numero_rad)
    except Rad.DoesNotExist:
        return JsonResponse({'erro': 'RAD nao encontrado.'}, status=404)

    if not _pode_exportar(request.usuario_rad, rad):
        return JsonResponse({'erro': 'Acesso nao autorizado.'}, status=403)

    perfis_usuario = set(request.usuario_rad.lista_perfis)
    pode_cancelar = (
        UsuarioPerfil.ADMINISTRADOR in perfis_usuario and rad.status != Rad.CANCELADO
    )

    resposta = _remover_campos_desabilitados(
            {
                'numero_rad': rad.numero_rad,
                'numero_os': rad.numero_os,
                'numero_sa': rad.numero_sa,
                'solicitante_sa': rad.solicitante_sa,
                'numero_execucao': rad.numero_execucao,
                'status': rad.status,
                'data_preenchimento': rad.data_preenchimento.isoformat(),
                'local_inicial': rad.local_inicial.sigla,
                'local_final': rad.local_final.sigla,
                'km_poste': rad.km_poste,
                'tipo_veiculo': rad.tipo_veiculo,
                'operador': rad.operador,
                'linhas': list(rad.linhas.values_list('linha_id', flat=True)),
                'vias': list(rad.vias.values_list('via__nome', flat=True)),
                'equipes': list(rad.equipes.values_list('equipe_id', flat=True)),
                'tipo_manutencao': rad.tipo_manutencao.nome,
                'numero_falha': rad.numero_falha,
                'hora_prog_inicio': rad.hora_prog_inicio.isoformat(),
                'hora_prog_termino': rad.hora_prog_termino.isoformat(),
                'hora_real_inicio': rad.hora_real_inicio.isoformat(),
                'hora_real_termino': rad.hora_real_termino.isoformat(),
                'duracao_programada_min': rad.duracao_programada_min,
                'duracao_real_min': rad.duracao_real_min,
                'atraso_inicio': rad.atraso_inicio,
                'motivo_atraso_inicio': (
                    rad.motivo_atraso_inicio.nome if rad.motivo_atraso_inicio else None
                ),
                'desc_motivo_atraso_inicio': rad.desc_motivo_atraso_inicio,
                'atraso_termino': rad.atraso_termino,
                'motivo_atraso_termino': (
                    rad.motivo_atraso_termino.nome if rad.motivo_atraso_termino else None
                ),
                'desc_motivo_atraso_termino': rad.desc_motivo_atraso_termino,
                'servicos': list(rad.servicos.values_list('servico__nome', flat=True)),
                'outros_servico_desc': rad.outros_servico_desc,
                'desc_foto_1': rad.desc_foto_1,
                'desc_foto_2': rad.desc_foto_2,
                'desc_foto_3': rad.desc_foto_3,
                'desc_foto_4': rad.desc_foto_4,
                'terceiros_num_encarregados': rad.terceiros_num_encarregados,
                'terceiros_num_op_maquina': rad.terceiros_num_op_maquina,
                'terceiros_num_ajudantes': rad.terceiros_num_ajudantes,
                'terceiros_num_motorista': rad.terceiros_num_motorista,
                'terceiros_volume': rad.terceiros_volume,
                'materiais_utilizados': rad.materiais_utilizados,
                'responsavel_atividade': rad.responsavel_atividade,
                'operador_ccm_abertura_nome': rad.operador_ccm_abertura_nome,
                'operador_ccm_abertura_hora': (
                    rad.operador_ccm_abertura_hora.isoformat()
                    if rad.operador_ccm_abertura_hora else None
                ),
                'operador_ccm_entrega_nome': rad.operador_ccm_entrega_nome,
                'operador_ccm_entrega_hora': (
                    rad.operador_ccm_entrega_hora.isoformat()
                    if rad.operador_ccm_entrega_hora else None
                ),
                'descricao_tecnica_atividade': rad.descricao_tecnica_atividade,
                'observacoes_gerais': rad.observacoes_gerais,
                'colaboradores': _colaboradores_resumo(rad),
                'amv': _amv_resumo(rad),
                'anexos': _anexos_resumo(rad),
                'login_usuario': rad.usuario.login,
                'preenchido_por_nome': nome_de_quem_preencheu(rad),
                'dispositivo': rad.get_dispositivo_display(),
                'data_sincronizacao': rad.data_sincronizacao.isoformat(),
                'justificativa_cancelamento': rad.justificativa_cancelamento,
                'login_cancelamento': (
                    rad.usuario_cancelamento.login if rad.usuario_cancelamento else None
                ),
                'data_cancelamento': (
                    rad.data_cancelamento.isoformat() if rad.data_cancelamento else None
                ),
                'pode_cancelar': pode_cancelar,  # PRM-037
                'exportacao_pdf_disponivel': _exportacao_pdf_oficial_habilitada(),
            }
    )

    if not _pode_ver_dispositivo(request.usuario_rad):
        resposta.pop('dispositivo', None)

    return JsonResponse(resposta)
