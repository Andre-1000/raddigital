"""
Views do app configuracoes.
"""
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from usuarios.decorators import requer_perfil, requer_token
from usuarios.models import UsuarioPerfil

from .models import CampoFormulario


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
