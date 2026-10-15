"""
Views do app rad.
"""
import json

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from comum.datas import parse_data
from usuarios.decorators import requer_perfil, requer_token
from usuarios.models import UsuarioPerfil

from .models import Rad
from .regras_negocio import processar_sincronizacao


def _normalizar_payload(dados):
    """
    Converte os campos de data recebidos como string (JSON nao tem tipo
    date/time nativo) para objetos Python. Os campos de hora
    permanecem como string 'HH:MM' — sao convertidos mais adiante em
    regras_negocio, que e reutilizado tanto aqui quanto pelos testes.
    """
    dados = dict(dados)
    for campo in (
        'data_preenchimento', 'data_atividade', 'data_hp_inicio', 'data_hp_termino',
        'data_hr_inicio', 'data_hr_termino',
    ):
        if campo in dados:
            dados[campo] = parse_data(dados[campo])
    return dados


def _detectar_dispositivo(user_agent):
    """
    Heuristica simples e amplamente usada: navegadores mobile sempre
    incluem 'Mobi' no User-Agent (Android, iPhone, Windows Phone).
    Tablets ficam classificados como 'mobile' tambem, de proposito --
    o que importa aqui e distinguir "preenchido em campo" (celular/
    tablet) de "preenchido no escritorio" (computador). Detectado
    sempre no servidor a partir do cabecalho HTTP real -- nunca
    informado pelo cliente, para nao poder ser falsificado a toa.
    """
    if not user_agent:
        return Rad.DESCONHECIDO
    return Rad.MOBILE if 'Mobi' in user_agent else Rad.DESKTOP


@csrf_exempt
@require_POST
@requer_token
def sincronizar(request):
    """
    POST /rad/sincronizar/
    Cabecalho: Authorization: Token <token>

    Aceita dois formatos de corpo:
    - application/json: quando o RAD nao tem anexos (VLD-026 permite).
    - multipart/form-data: quando ha fotos e/ou PDF. O campo 'dados'
      contem o JSON do RAD (mesmo formato de sempre, como string), e os
      arquivos vao em tres campos: 'fotos_intervencao_verificada' (ate
      3), 'fotos_acao_realizada' (ate 3) e 'pdf' (no maximo 1) --
      RG-ANX-001/002/003/004. As fotos sao sempre enviadas com a
      categoria explicita no nome do campo -- nunca misturadas em um
      grupo generico.

    Se qualquer validacao falhar (VLD-001 a VLD-026, incluindo VLD-023/
    024 dos anexos), retorna 422 com a lista completa de erros e nao
    grava nada -- nem o RAD, nem os arquivos (RG-VLD-002). Em caso de
    sucesso, retorna 201 com o numero do RAD e o numero de execucao
    definitivos.

    O corpo deve conter 'sync_id_tentativa' unico por tentativa de
    envio -- reenvios com o mesmo id sao idempotentes (retornam o RAD
    ja gravado com status 200, sem duplicar).
    """
    fotos_intervencao = []
    fotos_acao = []
    pdfs = []

    if request.content_type.startswith('multipart/form-data'):
        try:
            dados_brutos = json.loads(request.POST.get('dados') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'erro': 'Campo "dados" invalido.'}, status=400)
        fotos_intervencao = request.FILES.getlist('fotos_intervencao_verificada')
        fotos_acao = request.FILES.getlist('fotos_acao_realizada')
        pdfs = request.FILES.getlist('pdf')
    else:
        try:
            dados_brutos = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'erro': 'Corpo da requisicao invalido.'}, status=400)

    if not dados_brutos.get('sync_id_tentativa'):
        return JsonResponse(
            {'erro': 'sync_id_tentativa e obrigatorio para garantir idempotencia.'},
            status=400,
        )

    payload = _normalizar_payload(dados_brutos)
    payload['dispositivo'] = _detectar_dispositivo(request.META.get('HTTP_USER_AGENT', ''))

    rad_ja_existia = _sync_id_ja_processado(payload['sync_id_tentativa'])

    rad, erros = processar_sincronizacao(
        payload,
        usuario=request.usuario_rad,
        fotos_intervencao=fotos_intervencao,
        fotos_acao=fotos_acao,
        pdfs=pdfs,
    )

    if erros:
        return JsonResponse({'erros': erros}, status=422)

    return JsonResponse(
        {
            'numero_rad': rad.numero_rad,
            'numero_os': rad.numero_os,
            'numero_sa': rad.numero_sa,
            'numero_execucao': rad.numero_execucao,
            'status': rad.status,
        },
        status=200 if rad_ja_existia else 201,
    )


def _sync_id_ja_processado(sync_id_tentativa):
    from .models import Rad

    return Rad.objects.filter(sync_id_tentativa=sync_id_tentativa).exists()


@csrf_exempt
@require_POST
@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def cancelar_rad(request, numero_rad):
    """
    POST /rad/<numero_rad>/cancelar/
    Cabecalho: Authorization: Token <token>
    Body: {"justificativa": "texto livre"}

    RG-CAN-001: exclusivo do perfil Administrador (@requer_perfil ja
    bloqueia os demais perfis com 403 antes de chegar aqui).
    RG-CAN-005: justificativa obrigatoria.
    RG-CAN-009: cancelamento e irreversivel -- um RAD ja cancelado nao
    pode ser cancelado de novo.
    RG-CAN-011: numero_execucao nao e alterado por este endpoint.
    """
    try:
        dados = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Corpo da requisicao invalido.'}, status=400)

    justificativa = (dados.get('justificativa') or '').strip()
    if not justificativa:
        return JsonResponse(
            {'erro': 'A justificativa e obrigatoria para cancelar um RAD.'}, status=422
        )

    try:
        rad = Rad.objects.get(numero_rad=numero_rad)
    except Rad.DoesNotExist:
        return JsonResponse({'erro': 'RAD nao encontrado.'}, status=404)

    if rad.status == Rad.CANCELADO:
        return JsonResponse(
            {'erro': 'Este RAD ja esta cancelado. O cancelamento e irreversivel.'},
            status=409,
        )

    rad.status = Rad.CANCELADO
    rad.justificativa_cancelamento = justificativa
    rad.usuario_cancelamento = request.usuario_rad
    rad.data_cancelamento = timezone.now()
    rad.save(
        update_fields=[
            'status',
            'justificativa_cancelamento',
            'usuario_cancelamento',
            'data_cancelamento',
        ]
    )

    return JsonResponse(
        {
            'numero_rad': rad.numero_rad,
            'status': rad.status,
            'data_cancelamento': rad.data_cancelamento.isoformat(),
        }
    )


@csrf_exempt
@require_POST
@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def remover_anexo(request, numero_rad, id_anexo):
    """
    POST /rad/<numero_rad>/anexos/<id_anexo>/remover/
    Cabecalho: Authorization: Token <token>

    RG-ANX-011: somente o Administrador pode remover anexos apos a
    sincronizacao. Remove tanto o arquivo do storage quanto a
    referencia no banco.
    """
    from django.core.files.storage import default_storage

    from .models import RadAnexo

    try:
        anexo = RadAnexo.objects.get(id=id_anexo, rad__numero_rad=numero_rad)
    except RadAnexo.DoesNotExist:
        return JsonResponse({'erro': 'Anexo nao encontrado para este RAD.'}, status=404)

    if default_storage.exists(anexo.caminho_servidor):
        default_storage.delete(anexo.caminho_servidor)
    anexo.delete()

    return JsonResponse({'removido': True, 'numero_rad': numero_rad})


# ---------------------------------------------------------------------------
# Edicao de RAD ja sincronizado (13/10/2026) -- exclusivo do Administrador.
# Regras e motivos de projeto em rad/edicao.py.
# ---------------------------------------------------------------------------

def _anexos_para_edicao(rad):
    return [
        {
            'id': a.id,
            'tipo_arquivo': a.tipo_arquivo,
            'categoria_foto': a.categoria_foto,
            'categoria_foto_rotulo': a.get_categoria_foto_display() if a.categoria_foto else None,
            'nome_original': a.nome_original,
            'tamanho_bytes': a.tamanho_bytes,
        }
        for a in rad.anexos.all()
    ]


@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def dados_edicao(request, numero_rad):
    """
    GET /rad/<numero_rad>/dados-edicao/
    Entrega o RAD no formato do rascunho do formulario (para a tela de
    edicao carregar) + os anexos visiveis. 409 se o RAD esta cancelado
    (cancelamento e irreversivel e o RAD deixa de ser editavel).
    """
    from .edicao import RadNaoEncontradoError, carregar_rad_para_edicao, montar_rascunho

    try:
        rad = carregar_rad_para_edicao(numero_rad)
    except RadNaoEncontradoError:
        return JsonResponse({'erro': 'RAD nao encontrado.'}, status=404)

    if rad.status == Rad.CANCELADO:
        return JsonResponse({'erro': 'RAD cancelado nao pode ser editado.'}, status=409)

    return JsonResponse(
        {
            'numero_rad': rad.numero_rad,
            'numero_execucao': rad.numero_execucao,
            'rascunho': montar_rascunho(rad),
            'anexos': _anexos_para_edicao(rad),
            # 14/10/2026: servicos desativados que o RAD ainda usa (o
            # catalogo do formulario so traz os ativos) -- mesmos campos
            # do catalogo, para a tela mostrar o checkbox e deixar o
            # Administrador desmarcar/trocar.
            'servicos_desativados': [
                {
                    'id': s.id, 'nome': s.nome, 'descricao': s.descricao,
                    'requer_amv': s.requer_amv, 'requer_descricao': s.requer_descricao,
                    'requer_terceiros': s.requer_terceiros,
                    'terceiros_tem_op_maquina': s.terceiros_tem_op_maquina,
                    'terceiros_tem_volume': s.terceiros_tem_volume,
                    'requer_canaleta': s.requer_canaleta, 'area': s.area,
                }
                for s in (rs.servico for rs in rad.servicos.all())
                if not s.ativo
            ],
        }
    )


@csrf_exempt
@require_POST
@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def editar(request, numero_rad):
    """
    POST /rad/<numero_rad>/editar/
    Mesmo formato de /rad/sincronizar/ (JSON, ou multipart com 'dados' +
    arquivos NOVOS), com duas chaves extras dentro de 'dados':
      motivo_edicao   -- texto, obrigatorio;
      ocultar_anexos  -- lista de ids de anexos existentes a ocultar.
    Qualquer erro de validacao devolve 422 e nao grava nada. Sem
    nenhuma diferenca real em relacao ao que ja estava gravado, tambem
    devolve 422 ("Nenhuma alteracao").
    """
    from .edicao import RadCanceladoError, RadNaoEncontradoError, editar_rad

    fotos_intervencao = []
    fotos_acao = []
    pdfs = []
    if request.content_type.startswith('multipart/form-data'):
        try:
            dados_brutos = json.loads(request.POST.get('dados') or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'erro': 'Campo "dados" invalido.'}, status=400)
        fotos_intervencao = request.FILES.getlist('fotos_intervencao_verificada')
        fotos_acao = request.FILES.getlist('fotos_acao_realizada')
        pdfs = request.FILES.getlist('pdf')
    else:
        try:
            dados_brutos = json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return JsonResponse({'erro': 'Corpo da requisicao invalido.'}, status=400)

    motivo = dados_brutos.pop('motivo_edicao', '')
    ids_ocultar = dados_brutos.pop('ocultar_anexos', []) or []
    if not isinstance(motivo, str):
        motivo = ''
    try:
        ids_ocultar = [int(i) for i in ids_ocultar]
    except (TypeError, ValueError):
        return JsonResponse({'erro': 'ocultar_anexos invalido.'}, status=400)

    payload = _normalizar_payload(dados_brutos)
    # sync_id_tentativa so tem sentido na criacao; o validador pode exigir
    # a chave, entao garantimos um valor sem usa-lo para nada.
    payload.setdefault('sync_id_tentativa', f'edicao-{numero_rad}')

    try:
        rad, erros, alteracoes = editar_rad(
            numero_rad, payload, request.usuario_rad, motivo,
            ids_ocultar=ids_ocultar,
            fotos_intervencao=fotos_intervencao, fotos_acao=fotos_acao, pdfs=pdfs,
        )
    except RadNaoEncontradoError:
        return JsonResponse({'erro': 'RAD nao encontrado.'}, status=404)
    except RadCanceladoError:
        return JsonResponse({'erro': 'RAD cancelado nao pode ser editado.'}, status=409)

    if erros:
        return JsonResponse({'erros': erros}, status=422)

    return JsonResponse(
        {
            'numero_rad': rad.numero_rad,
            'numero_os': rad.numero_os,
            'numero_execucao': rad.numero_execucao,
            'total_alteracoes': len(alteracoes),
            'drive_desatualizado': rad.drive_desatualizado,
            'planilha_desatualizada': rad.planilha_desatualizada,
        }
    )
