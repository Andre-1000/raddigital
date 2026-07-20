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
        'atualizado_em': campo.atualizado_em.isoformat(),
    }


@requer_token
def listar_campos(request):
    """
    GET /configuracoes/campos/
    Disponivel a qualquer usuario autenticado -- o cliente (formulario
    de preenchimento, tela de consulta) usa esta rota para saber quais
    campos renderizar.
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
    return _alterar_estado(request, chave, habilitado=False)


@csrf_exempt
@require_POST
@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def habilitar_campo(request, chave):
    """POST /configuracoes/campos/<chave>/habilitar/ — exclusivo do Administrador."""
    return _alterar_estado(request, chave, habilitado=True)


def _alterar_estado(request, chave, habilitado):
    try:
        campo = CampoFormulario.objects.get(chave=chave)
    except CampoFormulario.DoesNotExist:
        return JsonResponse({'erro': 'Campo nao encontrado.'}, status=404)

    campo.habilitado = habilitado
    campo.atualizado_por = request.usuario_rad
    campo.atualizado_em = timezone.now()
    campo.save(update_fields=['habilitado', 'atualizado_por', 'atualizado_em'])

    return JsonResponse(_serializar(campo))
