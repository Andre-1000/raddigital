"""
Views do app configuracoes.
"""
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from usuarios.decorators import requer_perfil, requer_token
from usuarios.models import UsuarioPerfil

from .models import CampoFormulario, LimiteFotos


def _serializar(campo):
    return {
        'chave': campo.chave,
        'rotulo': campo.rotulo,
        'habilitado': campo.habilitado,
        'obrigatorio': campo.obrigatorio,
        'atualizado_em': campo.atualizado_em.isoformat(),
    }


@requer_token
def listar_campos(request):
    """
    GET /configuracoes/campos/
    Disponivel a qualquer usuario autenticado -- o cliente (formulario
    de preenchimento, tela de consulta) usa esta rota para saber quais
    campos renderizar e quais sao obrigatorios agora.
    """
    campos = CampoFormulario.objects.all()
    return JsonResponse({'campos': [_serializar(c) for c in campos]})


@csrf_exempt
@require_POST
@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def desabilitar_campo(request, chave):
    """
    POST /configuracoes/campos/<chave>/desabilitar/
    Exclusivo do Administrador. O campo deixa de aparecer para
    qualquer usuario -- inclusive Supervisor e outros Administradores
    -- ate ser habilitado novamente.
    """
    return _alterar_estado(request, chave, campos={'habilitado': False})


@csrf_exempt
@require_POST
@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def habilitar_campo(request, chave):
    """POST /configuracoes/campos/<chave>/habilitar/ — exclusivo do Administrador."""
    return _alterar_estado(request, chave, campos={'habilitado': True})


@csrf_exempt
@require_POST
@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def tornar_obrigatorio(request, chave):
    """
    POST /configuracoes/campos/<chave>/tornar-obrigatorio/
    Exclusivo do Administrador (22/07/2026). O campo passa a ser
    exigido na sincronizacao, sobrepondo a regra padrao.
    """
    return _alterar_estado(request, chave, campos={'obrigatorio': True})


@csrf_exempt
@require_POST
@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def tornar_opcional(request, chave):
    """POST /configuracoes/campos/<chave>/tornar-opcional/ — exclusivo do Administrador."""
    return _alterar_estado(request, chave, campos={'obrigatorio': False})


def _alterar_estado(request, chave, campos):
    try:
        campo = CampoFormulario.objects.get(chave=chave)
    except CampoFormulario.DoesNotExist:
        return JsonResponse({'erro': 'Campo nao encontrado.'}, status=404)

    for atributo, valor in campos.items():
        setattr(campo, atributo, valor)
    campo.atualizado_por = request.usuario_rad
    campo.atualizado_em = timezone.now()
    campo.save(update_fields=[*campos.keys(), 'atualizado_por', 'atualizado_em'])

    return JsonResponse(_serializar(campo))


def _serializar_limite(item):
    return {
        'id': item.id,
        'categoria': item.categoria,
        'categoria_rotulo': item.get_categoria_display(),
        'area': item.area,
        'area_rotulo': item.get_area_display(),
        'limite': item.limite,
        'atualizado_em': item.atualizado_em.isoformat(),
    }


@requer_token
def listar_limites_fotos(request):
    """
    GET /configuracoes/limites-fotos/
    30/07/2026. Disponivel a qualquer usuario autenticado -- o
    formulario usa esta rota (via /catalogos/todos/, que reexporta os
    mesmos dados para cache offline) pra saber quantas fotos permitir
    por categoria, dependendo da area do(s) servico(s) selecionado(s).
    """
    limites = LimiteFotos.objects.all()
    return JsonResponse({'limites': [_serializar_limite(item) for item in limites]})


@csrf_exempt
@require_POST
@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def atualizar_limite_foto(request, id_limite):
    """
    POST /configuracoes/limites-fotos/<id_limite>/atualizar/
    Body: {"limite": 10}
    Exclusivo do Administrador. Numero minimo de 1 (nunca permite
    "0 fotos" -- se a intencao for esconder a categoria inteira, isso
    e um caso de CampoFormulario/habilitado, nao deste mecanismo).
    """
    import json

    try:
        limite_obj = LimiteFotos.objects.get(id=id_limite)
    except LimiteFotos.DoesNotExist:
        return JsonResponse({'erro': 'Configuração de limite não encontrada.'}, status=404)

    try:
        corpo = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Corpo da requisição inválido.'}, status=400)

    novo_limite = corpo.get('limite')
    if not isinstance(novo_limite, int) or novo_limite < 1:
        return JsonResponse({'erro': 'Informe um limite numérico de pelo menos 1.'}, status=422)
    if novo_limite > 50:
        return JsonResponse({'erro': 'Limite máximo permitido é 50 por categoria.'}, status=422)

    limite_obj.limite = novo_limite
    limite_obj.atualizado_por = request.usuario_rad
    limite_obj.save(update_fields=['limite', 'atualizado_por', 'atualizado_em'])

    return JsonResponse(_serializar_limite(limite_obj))
