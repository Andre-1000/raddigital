"""
Views do app usuarios.

Login com senha (30/07/2026 -- ver nota em models.py e CLAUDE.md sobre
o achado de seguranca corrigido). Gestao de usuarios (EFD secao 4.4).
Supervisor gerencia Usuarios e Supervisores (PRM-015 a PRM-020).
Administrador gerencia todos (PRM-021 a PRM-024).

25/08/2026: endpoint definir_senha_temporaria -- solucao para quando o
envio de e-mail (SMTP) esta fora do ar/mal configurado e "Esqueci minha
senha" nao chega para ninguem. Exclusivo do Administrador. Cada uso
fica registrado em LogSenhaTemporaria (auditoria).
"""
import json
import re
import secrets
import string
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Q
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_http_methods

from .decorators import requer_perfil, requer_token
from .models import (
    LogSenhaTemporaria,
    Token,
    TokenRedefinicaoSenha,
    Usuario,
    UsuarioPerfil,
    hash_token,
)
from .servicos_email import enviar_email_redefinicao_senha
from .validadores_senha import validar_senha

REGEX_LOGIN = re.compile(r'^[a-zA-Z0-9_.@-]{3,100}$')
REGEX_EMAIL_SIMPLES = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


# ---------------------------------------------------------------------------
# Autenticacao
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def login(request):
    """
    POST /usuarios/login/
    Body: {"login": "joao.silva ou joao@email.com", "senha": "...", "dispositivo": "opcional"}

    30/07/2026: login com senha real, substituindo o login "so pelo
    login" (achado critico de seguranca, auditoria informal contra
    OWASP Top 10:2025 -- ver CLAUDE.md). Mudancas:
    - Exige senha, verificada por hash (nunca texto plano armazenado).
    - Bloqueio temporario apos MAXIMO_TENTATIVAS_LOGIN tentativas erradas
      seguidas (rate limit contra forca bruta).
    - Mensagem de erro generica ("login ou senha incorretos") tanto pra
      login inexistente quanto senha errada -- nao da pra descobrir se
      um login existe so pela resposta (evita enumeracao de contas).
    - Usuario legado sem senha definida (senha_hash vazio) recebe erro
      especifico apontando pra "Esqueci minha senha", que funciona tambem
      como fluxo de "definir minha primeira senha".

    30/07/2026 (revisado): o campo "login" do payload aceita tanto a
    matricula/login de sempre QUANTO o e-mail cadastrado -- a pessoa
    pode entrar com qualquer um dos dois, sem campo separado na tela.
    Distincao simples: se o valor contem "@", busca por e-mail; senao,
    busca por login. Email e' unique no model Usuario, entao nao ha
    risco de ambiguidade.
    """
    try:
        dados = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Corpo da requisicao invalido.'}, status=400)

    identificador = (dados.get('login') or '').strip()
    senha_informada = dados.get('senha') or ''

    if not identificador or not senha_informada:
        return JsonResponse({'erro': 'Informe login e senha.'}, status=400)

    if '@' in identificador:
        usuario = Usuario.objects.filter(email__iexact=identificador).first()
    else:
        usuario = Usuario.objects.filter(login=identificador).first()

    mensagem_erro_generica = 'Login ou senha incorretos.'

    if usuario is None:
        return JsonResponse({'erro': mensagem_erro_generica}, status=401)

    if not usuario.ativo:
        return JsonResponse({'erro': 'Usuario inativo.'}, status=401)

    maximo_tentativas = getattr(settings, 'MAXIMO_TENTATIVAS_LOGIN', 5)
    bloqueio_minutos = getattr(settings, 'BLOQUEIO_LOGIN_MINUTOS', 15)

    if usuario.bloqueado_ate and timezone.now() < usuario.bloqueado_ate:
        minutos_restantes = max(1, int((usuario.bloqueado_ate - timezone.now()).total_seconds() // 60) + 1)
        return JsonResponse(
            {'erro': f'Muitas tentativas incorretas. Tente novamente em {minutos_restantes} minuto(s).'},
            status=429,
        )

    if not usuario.senha_hash:
        return JsonResponse(
            {
                'erro': 'Esta conta ainda não tem senha definida. Use "Esqueci minha senha" para criar a primeira senha.',
                'senha_nao_definida': True,
            },
            status=401,
        )

    if not usuario.verificar_senha(senha_informada):
        usuario.tentativas_login_falhas += 1
        if usuario.tentativas_login_falhas >= maximo_tentativas:
            usuario.bloqueado_ate = timezone.now() + timedelta(minutes=bloqueio_minutos)
        usuario.save(update_fields=['tentativas_login_falhas', 'bloqueado_ate'])
        return JsonResponse({'erro': mensagem_erro_generica}, status=401)

    if usuario.tentativas_login_falhas or usuario.bloqueado_ate:
        usuario.tentativas_login_falhas = 0
        usuario.bloqueado_ate = None
        usuario.save(update_fields=['tentativas_login_falhas', 'bloqueado_ate'])

    token = Token.gerar_para(usuario, dispositivo=dados.get('dispositivo'))

    return JsonResponse(
        {
            # 25/08/2026: token.token agora e o HASH gravado no banco --
            # o valor de verdade (o que o cliente deve usar no header
            # Authorization dai em diante) vem de valor_plano, que so
            # existe em memoria neste exato momento (ver
            # usuarios/models.py::Token.gerar_para).
            'token': token.valor_plano,
            'validade': token.validade.isoformat(),
            'login': usuario.login,
            'perfis': usuario.lista_perfis,
        },
        status=200,
    )


@requer_token
def validar_token(request):
    """
    GET /usuarios/validar-token/
    """
    usuario = request.usuario_rad
    return JsonResponse(
        {
            'login': usuario.login,
            'perfis': usuario.lista_perfis,
            'validade': request.token_rad.validade.isoformat(),
        }
    )


@requer_token
def listar_meus_dispositivos(request):
    """
    GET /usuarios/meus-dispositivos/
    30/07/2026. Lista as sessões (tokens) ativas do próprio usuário --
    permite encerrar uma sessão específica (ex.: celular perdido) sem
    precisar derrubar TODAS as sessões válidas de uma vez. Cada token
    já guarda `dispositivo` (User-Agent resumido, capturado no momento
    do login) para a pessoa reconhecer qual é qual.
    """
    usuario = request.usuario_rad
    token_atual = request.token_rad
    tokens = usuario.tokens.filter(validade__gt=timezone.now()).order_by('-data_criacao')
    return JsonResponse(
        {
            'dispositivos': [
                {
                    'id': t.id,
                    'dispositivo': t.dispositivo or 'Dispositivo desconhecido',
                    'criado_em': t.data_criacao.isoformat(),
                    'validade': t.validade.isoformat(),
                    'este_dispositivo': t.id == token_atual.id,
                }
                for t in tokens
            ]
        }
    )


@csrf_exempt
@require_POST
@requer_token
def encerrar_dispositivo(request, id_token):
    """
    POST /usuarios/meus-dispositivos/<id>/encerrar/
    30/07/2026. Remove um token específico do PRÓPRIO usuário --
    obriga aquele dispositivo a fazer login de novo na próxima ação,
    sem afetar os demais dispositivos logados. Não permite encerrar o
    dispositivo atual por aqui (evita a pessoa se derrubar sem querer
    no meio do uso) -- pra isso existe "Sair" no proprio dispositivo.
    """
    usuario = request.usuario_rad
    token_atual = request.token_rad

    if id_token == token_atual.id:
        return JsonResponse(
            {'erro': 'Não é possível encerrar a sessão do dispositivo atual por aqui.'},
            status=400,
        )

    apagados, _ = Token.objects.filter(id=id_token, usuario=usuario).delete()
    if not apagados:
        return JsonResponse({'erro': 'Sessão não encontrada.'}, status=404)

    return JsonResponse({'sucesso': True})


@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def listar_sessoes_ativas(request):
    """
    GET /usuarios/sessoes-ativas/?busca=texto
    21/08/2026. Exclusivo do Administrador -- aba "Sessões" dentro de
    Gerenciar Usuários. Lista TODAS as sessões (tokens) válidas de
    TODOS os usuários do sistema -- diferente de
    listar_meus_dispositivos, que só mostra as sessões do próprio
    solicitante.

    Busca (?busca=) filtra por login/matrícula OU pelo nome cadastrado
    em ColaboradorCadastro (quando o usuário tiver um vínculo -- nem
    todo login vem de um colaborador, ver usuarios/models.py::Usuario).
    """
    termo = (request.GET.get('busca') or '').strip()

    tokens = (
        Token.objects.select_related('usuario')
        .prefetch_related('usuario__colaborador')
        .filter(validade__gt=timezone.now())
        .order_by('-data_criacao')
    )

    if termo:
        tokens = tokens.filter(
            Q(usuario__login__icontains=termo) | Q(usuario__colaborador__nome__icontains=termo)
        )

    token_atual = request.token_rad

    def nome_de(usuario):
        colaborador = getattr(usuario, 'colaborador', None)
        return colaborador.nome if colaborador and colaborador.nome else usuario.login

    return JsonResponse(
        {
            'sessoes': [
                {
                    'id': t.id,
                    'login': t.usuario.login,
                    'nome': nome_de(t.usuario),
                    'dispositivo': t.dispositivo or 'Dispositivo desconhecido',
                    'criado_em': t.data_criacao.isoformat(),
                    'validade': t.validade.isoformat(),
                    'esta_sessao': t.id == token_atual.id,
                }
                for t in tokens
            ]
        }
    )


@csrf_exempt
@require_POST
@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def encerrar_sessao_administrativamente(request, id_token):
    """
    POST /usuarios/sessoes-ativas/<id>/encerrar/
    21/08/2026. Exclusivo do Administrador -- encerra a sessão de
    QUALQUER usuário do sistema (diferente de encerrar_dispositivo,
    que só permite encerrar as próprias sessões). Mesma trava de
    encerrar_dispositivo quanto à sessão atual: não deixa o próprio
    Administrador se derrubar por aqui sem querer -- para isso existe
    "Sair" no próprio dispositivo.
    """
    token_atual = request.token_rad

    if id_token == token_atual.id:
        return JsonResponse(
            {'erro': 'Não é possível encerrar a sessão atual por aqui. Use "Sair".'},
            status=400,
        )

    apagados, _ = Token.objects.filter(id=id_token).delete()
    if not apagados:
        return JsonResponse({'erro': 'Sessão não encontrada.'}, status=404)

    return JsonResponse({'sucesso': True})


@csrf_exempt
@require_POST
@requer_token
def trocar_senha(request):
    """
    POST /usuarios/trocar-senha/
    Body: {"senha_atual": "...", "nova_senha": "..."}
    30/07/2026. Qualquer usuario autenticado troca a propria senha.
    Exige a senha atual correta -- mesmo com o dispositivo ja logado, um
    valor errado em senha_atual bloqueia a troca (protege contra alguem
    pegar o celular destravado de outra pessoa e trocar a senha dela).
    Excecao: se o usuario ainda nao tem senha definida (legado), nao ha
    "senha atual" pra conferir -- esse caso deveria passar pelo fluxo de
    "Esqueci minha senha" em vez deste endpoint, mas por seguranca ainda
    assim permitimos definir aqui sem exigir uma senha_atual que nunca
    existiu.
    """
    usuario = request.usuario_rad
    try:
        dados = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Corpo da requisicao invalido.'}, status=400)

    senha_atual = dados.get('senha_atual') or ''
    nova_senha = dados.get('nova_senha') or ''

    if usuario.senha_hash and not usuario.verificar_senha(senha_atual):
        return JsonResponse({'erro': 'Senha atual incorreta.'}, status=401)

    erros_senha = validar_senha(nova_senha, login=usuario.login)
    if erros_senha:
        return JsonResponse(
            {'erros': [{'campo': 'nova_senha', 'mensagem': m} for m in erros_senha]}, status=422
        )

    usuario.definir_senha(nova_senha)
    usuario.save(update_fields=['senha_hash'])

    return JsonResponse({'sucesso': True})


@csrf_exempt
@require_POST
def solicitar_redefinicao_senha(request):
    """
    POST /usuarios/esqueci-senha/
    Body: {"email": "..."}
    30/07/2026. Publico (sem token) -- por definicao quem esqueceu a
    senha nao esta autenticado. Sempre retorna a MESMA resposta de
    sucesso, exista ou nao o e-mail no cadastro -- evita que alguem
    descubra quais e-mails/usuarios existem testando este endpoint
    (enumeracao de contas).
    """
    try:
        dados = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Corpo da requisicao invalido.'}, status=400)

    email_informado = (dados.get('email') or '').strip().lower()

    resposta_generica = JsonResponse({
        'mensagem': 'Se este e-mail estiver cadastrado, enviamos um link de redefinição de senha.',
    })

    if not email_informado or not REGEX_EMAIL_SIMPLES.match(email_informado):
        return resposta_generica

    usuario = Usuario.objects.filter(email__iexact=email_informado, ativo=True).first()
    if usuario is None:
        return resposta_generica

    # 25/08/2026: limite de solicitacoes por CONTA (nao por IP) numa
    # janela de tempo -- protege quem recebe o e-mail de ser spamado
    # por alguem repetindo este POST, sem precisar identificar quem
    # esta pedindo (o atacante pode trocar de IP, mas o alvo continua
    # sendo o mesmo e-mail). Resposta continua identica -- nao revela
    # se o limite foi atingido, so silenciosamente para de enviar.
    maximo = getattr(settings, 'MAXIMO_SOLICITACOES_REDEFINICAO_SENHA', 3)
    janela_minutos = getattr(settings, 'JANELA_REDEFINICAO_SENHA_MINUTOS', 60)
    solicitacoes_recentes = TokenRedefinicaoSenha.objects.filter(
        usuario=usuario,
        criado_em__gte=timezone.now() - timedelta(minutes=janela_minutos),
    ).count()
    if solicitacoes_recentes >= maximo:
        return resposta_generica

    token = TokenRedefinicaoSenha.gerar_para(usuario)
    try:
        # 25/08/2026: token.token agora e o HASH gravado no banco -- o
        # e-mail precisa do valor de verdade, que so existe em
        # valor_plano (ver usuarios/models.py::TokenRedefinicaoSenha.gerar_para).
        enviar_email_redefinicao_senha(usuario, token.valor_plano)
    except Exception as erro:
        # 30/07/2026: a resposta pro CLIENTE continua generica de
        # proposito (evita enumeracao de contas) -- mas o erro real
        # precisa aparecer no log do Render pra dar pra debugar
        # problema de SMTP (credencial errada, porta bloqueada, etc.).
        # print() garante que aparece no log mesmo sem LOGGING
        # configurado em settings.py.
        print(f'[ERRO] Falha ao enviar e-mail de redefinicao de senha para {usuario.email!r}: {erro!r}')

    return resposta_generica


@csrf_exempt
@require_POST
def confirmar_redefinicao_senha(request):
    """
    POST /usuarios/redefinir-senha/confirmar/
    Body: {"token": "...", "nova_senha": "..."}
    30/07/2026. Publico -- o token de redefinicao (vindo do e-mail) e a
    propria prova de identidade aqui, nao precisa de token de sessao.
    """
    try:
        dados = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Corpo da requisicao invalido.'}, status=400)

    valor_token = (dados.get('token') or '').strip()
    nova_senha = dados.get('nova_senha') or ''

    if not valor_token:
        return JsonResponse({'erro': 'Link inválido.'}, status=400)

    # 25/08/2026: TokenRedefinicaoSenha.token agora guarda o HASH --
    # hasheia o valor recebido do link antes de buscar, mesma tecnica
    # ja usada para o token de sessao (ver usuarios/decorators.py).
    token = TokenRedefinicaoSenha.objects.select_related('usuario').filter(
        token=hash_token(valor_token)
    ).first()
    if token is None or not token.valido:
        return JsonResponse(
            {'erro': 'Este link é inválido ou já expirou. Solicite um novo em "Esqueci minha senha".'},
            status=400,
        )

    erros_senha = validar_senha(nova_senha, login=token.usuario.login)
    if erros_senha:
        return JsonResponse(
            {'erros': [{'campo': 'nova_senha', 'mensagem': m} for m in erros_senha]}, status=422
        )

    usuario = token.usuario
    usuario.definir_senha(nova_senha)
    usuario.tentativas_login_falhas = 0
    usuario.bloqueado_ate = None
    usuario.save(update_fields=['senha_hash', 'tentativas_login_falhas', 'bloqueado_ate'])

    token.usado = True
    token.save(update_fields=['usado'])

    # Invalida qualquer outro token de redefinicao pendente do mesmo
    # usuario -- evita que um link antigo continue valido depois que a
    # senha ja foi trocada por outro caminho.
    TokenRedefinicaoSenha.objects.filter(usuario=usuario, usado=False).exclude(id=token.id).update(usado=True)

    return JsonResponse({'sucesso': True})


def _gerar_senha_temporaria():
    """
    25/08/2026. Gera uma senha aleatoria de 12 caracteres (letras
    maiusculas, minusculas e digitos) -- passa facil nas regras de
    usuarios/validadores_senha.py (minimo 8, nao so numeros, nao
    comum). Usada por definir_senha_temporaria, para o Administrador
    nao precisar (nem poder) escolher a senha de outra pessoa a dedo.
    """
    alfabeto = string.ascii_uppercase + string.ascii_lowercase + string.digits
    while True:
        senha = ''.join(secrets.choice(alfabeto) for _ in range(12))
        if not senha.isdigit():  # praticamente impossivel dar so digito em 12 chars, mas garante
            return senha


@csrf_exempt
@require_POST
@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def definir_senha_temporaria(request, id_usuario):
    """
    POST /usuarios/administrar/<id>/definir-senha-temporaria/
    25/08/2026. Exclusivo do Administrador -- via de emergencia para
    quando "Esqueci minha senha" nao chega (ex.: SMTP mal configurado
    ou fora do ar). Gera uma senha aleatoria de 12 caracteres, define
    ela como a senha da pessoa, e devolve essa senha na resposta UMA
    UNICA VEZ (nunca fica salva em texto puro nem reaparece depois) --
    cabe ao Administrador repassar por um canal fora do sistema
    (telefone, presencial), nunca por e-mail (o mesmo canal que esta
    com problema) ou mensagem sem criptografia.

    Zera tambem tentativas_login_falhas/bloqueado_ate, para a pessoa
    conseguir entrar de primeira com a senha nova, mesmo que estivesse
    bloqueada por tentativas erradas anteriores.

    So Administrador (nao Supervisor): e um bypass direto do fluxo
    normal de prova de identidade (link por e-mail), entao fica restrito
    ao mesmo nivel de quem ja pode gerenciar sessoes/exportacoes
    sensiveis.

    25/08/2026 (revisado): cada uso fica registrado em
    LogSenhaTemporaria -- antes disso, nao havia como saber depois
    quem gerou senha pra quem, nem quando (achado de auditoria de
    seguranca -- ver tela "Sessões" em Gerenciar Usuários, que agora
    mostra esse historico).
    """
    try:
        usuario = Usuario.objects.prefetch_related('perfis').get(id=id_usuario)
    except Usuario.DoesNotExist:
        return JsonResponse({'erro': 'Usuario nao encontrado.'}, status=404)

    solicitante = request.usuario_rad
    if not _pode_gerenciar(usuario, solicitante):
        return JsonResponse(
            {'erro': 'Você não tem permissão para definir a senha deste usuário.'},
            status=403,
        )

    senha_temporaria = _gerar_senha_temporaria()

    usuario.definir_senha(senha_temporaria)
    usuario.tentativas_login_falhas = 0
    usuario.bloqueado_ate = None
    usuario.save(update_fields=['senha_hash', 'tentativas_login_falhas', 'bloqueado_ate'])

    # Invalida qualquer link de "esqueci minha senha" pendente dessa
    # pessoa -- evita que um link antigo (que pode nem ter chegado,
    # dado o motivo de existir esta rota) ainda funcione depois.
    TokenRedefinicaoSenha.objects.filter(usuario=usuario, usado=False).update(usado=True)

    LogSenhaTemporaria.objects.create(
        administrador=solicitante,
        administrador_login_snapshot=solicitante.login,
        usuario_alvo=usuario,
        usuario_alvo_login_snapshot=usuario.login,
    )

    return JsonResponse({
        'login': usuario.login,
        'senha_temporaria': senha_temporaria,
    })


@requer_token
@requer_perfil(UsuarioPerfil.ADMINISTRADOR)
def listar_log_senha_temporaria(request):
    """
    GET /usuarios/administrar/log-senha-temporaria/
    25/08/2026. Exclusivo do Administrador -- historico de auditoria de
    quem gerou senha temporaria pra quem (ver definir_senha_temporaria
    acima). Mostra os 100 mais recentes -- volume esperado e baixo (uso
    de emergencia, nao uma acao do dia a dia).
    """
    entradas = LogSenhaTemporaria.objects.select_related('administrador', 'usuario_alvo')[:100]
    return JsonResponse({
        'entradas': [
            {
                'administrador': entrada.administrador_login_snapshot,
                'usuario_alvo': entrada.usuario_alvo_login_snapshot,
                'criado_em': entrada.criado_em.isoformat(),
            }
            for entrada in entradas
        ]
    })


# ---------------------------------------------------------------------------
# Gestao de usuarios (EFD secao 4.4)
# ---------------------------------------------------------------------------

def _pode_gerenciar(usuario_alvo, usuario_solicitante):
    """
    Supervisor nao pode gerenciar usuarios com perfil EXCLUSIVO de
    Administrador (PRM-016/017). Administrador pode gerenciar todos.
    """
    if usuario_solicitante.tem_perfil(UsuarioPerfil.ADMINISTRADOR):
        return True
    perfis_alvo = set(usuario_alvo.lista_perfis)
    return perfis_alvo != {UsuarioPerfil.ADMINISTRADOR}


def _serializar_usuario(usuario, usuario_solicitante=None):
    dados = {
        'id': usuario.id,
        'login': usuario.login,
        'email': usuario.email,
        'ativo': usuario.ativo,
        'perfis': usuario.lista_perfis,
        'data_criacao': usuario.data_criacao.strftime('%d/%m/%Y'),
        # 30/07/2026: o cliente usa isso pra avisar o Administrador que
        # a pessoa ainda nao consegue entrar no sistema (precisa de
        # e-mail cadastrado + passar pelo fluxo de "Esqueci minha senha").
        'senha_definida': bool(usuario.senha_hash),
    }
    if usuario_solicitante is not None:
        dados['pode_gerenciar'] = _pode_gerenciar(usuario, usuario_solicitante)
    return dados


@requer_token
@requer_perfil(UsuarioPerfil.SUPERVISOR, UsuarioPerfil.ADMINISTRADOR)
def listar(request):
    """
    GET /usuarios/administrar/
    Retorna TODOS os usuarios. O campo pode_gerenciar indica ao cliente
    se o solicitante tem permissao de editar/excluir cada usuario.
    Supervisor ve admins na lista mas nao pode gerencia-los (PRM-016/017).
    """
    solicitante = request.usuario_rad
    usuarios = Usuario.objects.prefetch_related('perfis').order_by('login')
    return JsonResponse({
        'usuarios': [_serializar_usuario(u, solicitante) for u in usuarios]
    })


@csrf_exempt
@require_http_methods(['POST'])
@requer_token
@requer_perfil(UsuarioPerfil.SUPERVISOR, UsuarioPerfil.ADMINISTRADOR)
def criar(request):
    """
    POST /usuarios/administrar/criar/
    Body: {"login": "joao.silva", "perfis": ["usuario"], "email": "opcional"}
    """
    try:
        dados = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Corpo da requisicao invalido.'}, status=400)

    login_novo = (dados.get('login') or '').strip()
    email_novo = (dados.get('email') or '').strip().lower()
    perfis_solicitados = list(set(dados.get('perfis') or []))
    solicitante = request.usuario_rad

    erros = []

    if not login_novo:
        erros.append({'campo': 'login', 'mensagem': 'Informe o login.'})
    elif not REGEX_LOGIN.match(login_novo):
        erros.append({'campo': 'login', 'mensagem': 'Login invalido. Use letras, numeros, pontos, hifens ou underline (minimo 3 caracteres).'})
    elif Usuario.objects.filter(login=login_novo).exists():
        erros.append({'campo': 'login', 'mensagem': 'Este login ja esta em uso.'})

    if email_novo:
        if not REGEX_EMAIL_SIMPLES.match(email_novo):
            erros.append({'campo': 'email', 'mensagem': 'E-mail invalido.'})
        elif Usuario.objects.filter(email__iexact=email_novo).exists():
            erros.append({'campo': 'email', 'mensagem': 'Este e-mail ja esta em uso por outro usuario.'})

    erros_perfil, perfis_validos = _validar_perfis(perfis_solicitados, solicitante)
    erros.extend(erros_perfil)

    if erros:
        return JsonResponse({'erros': erros}, status=422)

    with transaction.atomic():
        usuario = Usuario.objects.create(login=login_novo, email=email_novo or None)
        for p in perfis_validos:
            UsuarioPerfil.objects.create(usuario=usuario, perfil=p)

    return JsonResponse(_serializar_usuario(usuario, solicitante), status=201)


@csrf_exempt
@require_http_methods(['POST'])
@requer_token
@requer_perfil(UsuarioPerfil.SUPERVISOR, UsuarioPerfil.ADMINISTRADOR)
def editar(request, id_usuario):
    """
    POST /usuarios/administrar/<id>/editar/
    Body: {"perfis": [...], "ativo": true, "email": "opcional"}
    Login nao e editavel apos a criacao -- e o identificador de
    autenticacao e alterar causaria confusao operacional.
    30/07/2026: email agora e editavel aqui tambem -- e o que habilita
    a pessoa a usar "Esqueci minha senha" pela primeira vez.
    """
    try:
        usuario = Usuario.objects.prefetch_related('perfis').get(id=id_usuario)
    except Usuario.DoesNotExist:
        return JsonResponse({'erro': 'Usuario nao encontrado.'}, status=404)

    solicitante = request.usuario_rad
    if not _pode_gerenciar(usuario, solicitante):
        return JsonResponse(
            {'erro': 'Voce nao tem permissao para editar este usuario.'},
            status=403,
        )

    try:
        dados = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'erro': 'Corpo da requisicao invalido.'}, status=400)

    erros = []

    email_novo = None
    if 'email' in dados:
        email_novo = (dados.get('email') or '').strip().lower()
        if email_novo:
            if not REGEX_EMAIL_SIMPLES.match(email_novo):
                erros.append({'campo': 'email', 'mensagem': 'E-mail invalido.'})
            elif Usuario.objects.filter(email__iexact=email_novo).exclude(id=usuario.id).exists():
                erros.append({'campo': 'email', 'mensagem': 'Este e-mail ja esta em uso por outro usuario.'})

    perfis_solicitados = list(set(dados.get('perfis', usuario.lista_perfis)))
    erros_perfil, perfis_validos = _validar_perfis(perfis_solicitados, solicitante)
    erros.extend(erros_perfil)

    if erros:
        return JsonResponse({'erros': erros}, status=422)

    with transaction.atomic():
        if 'ativo' in dados:
            usuario.ativo = bool(dados['ativo'])
            usuario.save(update_fields=['ativo'])
        if 'email' in dados:
            usuario.email = email_novo or None
            usuario.save(update_fields=['email'])
        usuario.perfis.all().delete()
        for p in perfis_validos:
            UsuarioPerfil.objects.create(usuario=usuario, perfil=p)

    usuario.refresh_from_db()
    return JsonResponse(_serializar_usuario(usuario, solicitante))


@csrf_exempt
@require_http_methods(['POST'])
@requer_token
@requer_perfil(UsuarioPerfil.SUPERVISOR, UsuarioPerfil.ADMINISTRADOR)
def excluir(request, id_usuario):
    """
    POST /usuarios/administrar/<id>/excluir/
    """
    try:
        usuario = Usuario.objects.prefetch_related('perfis').get(id=id_usuario)
    except Usuario.DoesNotExist:
        return JsonResponse({'erro': 'Usuario nao encontrado.'}, status=404)

    solicitante = request.usuario_rad

    if usuario.id == solicitante.id:
        return JsonResponse(
            {'erro': 'Nao e possivel excluir o proprio usuario.'},
            status=403,
        )

    if not _pode_gerenciar(usuario, solicitante):
        return JsonResponse(
            {'erro': 'Voce nao tem permissao para excluir este usuario.'},
            status=403,
        )

    usuario.delete()
    return JsonResponse({'removido': True})


def _validar_perfis(perfis_solicitados, usuario_solicitante):
    perfis_validos_set = {UsuarioPerfil.USUARIO, UsuarioPerfil.SUPERVISOR, UsuarioPerfil.ADMINISTRADOR}
    erros = []

    for p in perfis_solicitados:
        if p not in perfis_validos_set:
            erros.append({'campo': 'perfis', 'mensagem': f'Perfil invalido: {p}.'})

    if len(perfis_solicitados) > 2:
        erros.append({'campo': 'perfis', 'mensagem': 'Maximo de 2 perfis por usuario.'})

    if not perfis_solicitados:
        erros.append({'campo': 'perfis', 'mensagem': 'Selecione ao menos 1 perfil.'})

    eh_admin = usuario_solicitante.tem_perfil(UsuarioPerfil.ADMINISTRADOR)
    if not eh_admin and UsuarioPerfil.ADMINISTRADOR in perfis_solicitados:
        erros.append({
            'campo': 'perfis',
            'mensagem': 'Supervisor nao pode atribuir o perfil Administrador (PRM-024).',
        })

    return erros, perfis_solicitados
