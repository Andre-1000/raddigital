"""
Modelos do app usuarios.

Cadastro de logins do sistema RAD, distinto do cadastro de colaboradores
(funcionarios da empresa). Um usuario e quem preenche o RAD.

Referencia: MODELO_LOGICO_BANCO_DE_DADOS_v2.docx, secoes 6.1 a 6.3.
Referencia: ESPECIFICACAO_FUNCIONAL_DETALHADA.docx, secao 3.9 (RG-AUTH)
e secao 4 (Matriz de Permissoes).

30/07/2026: login passou a exigir senha (achado critico de seguranca --
auditoria informal contra OWASP Top 10:2025 encontrou que qualquer login
existente recebia token valido sem provar identidade nenhuma). Ver
`email`, `senha_hash`, `tentativas_login_falhas`, `bloqueado_ate` abaixo
e o model `TokenRedefinicaoSenha`.
"""
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone


class Usuario(models.Model):
    """Cadastro de login do sistema. Distinto de ColaboradorCadastro."""

    login = models.CharField(
        max_length=100,
        unique=True,
        help_text='Login unico.',
    )
    email = models.EmailField(
        null=True,
        blank=True,
        unique=True,
        help_text=(
            '30/07/2026: usado para o fluxo de "Esqueci minha senha". '
            'Pode ficar vazio para usuarios legados ate o Administrador '
            'preencher (Postgres permite varios NULL num campo unique, '
            'entao nao ha conflito entre usuarios sem e-mail ainda).'
        ),
    )
    senha_hash = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text=(
            '30/07/2026: hash da senha (django.contrib.auth.hashers.make_password '
            '-- PBKDF2, nunca texto plano). Vazio = usuario legado que ainda nao '
            'definiu senha; o login bloqueia e orienta a usar "Esqueci minha senha" '
            'nesse caso, que funciona tambem como fluxo de primeira senha.'
        ),
    )
    tentativas_login_falhas = models.PositiveSmallIntegerField(
        default=0,
        help_text='Zerado a cada login correto. Ver bloqueado_ate.',
    )
    bloqueado_ate = models.DateTimeField(
        null=True,
        blank=True,
        help_text='30/07/2026: rate limit contra forca bruta -- ver settings.MAXIMO_TENTATIVAS_LOGIN.',
    )
    ativo = models.BooleanField(
        default=True,
        help_text='Inativo = nao consegue fazer login.',
    )
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'usuarios'
        verbose_name = 'Usuario'
        verbose_name_plural = 'Usuarios'

    def __str__(self):
        return self.login

    def tem_perfil(self, perfil):
        """Verifica se o usuario possui um perfil especifico (PRM-025 a PRM-027)."""
        return self.perfis.filter(perfil=perfil).exists()

    @property
    def lista_perfis(self):
        return list(self.perfis.values_list('perfil', flat=True))

    def definir_senha(self, senha_texto_plano):
        """Faz o hash e atualiza senha_hash em memoria -- quem chama ainda precisa dar .save()."""
        self.senha_hash = make_password(senha_texto_plano)

    def verificar_senha(self, senha_texto_plano):
        """False tambem quando senha_hash esta vazio (usuario legado sem senha definida)."""
        if not self.senha_hash:
            return False
        return check_password(senha_texto_plano, self.senha_hash)


class UsuarioPerfil(models.Model):
    """
    Perfis de acesso de um usuario. Ate 2 perfis simultaneos por login
    (EFD secao 4 - Matriz de Permissoes).
    """

    USUARIO = 'usuario'
    SUPERVISOR = 'supervisor'
    ADMINISTRADOR = 'administrador'

    PERFIL_CHOICES = [
        (USUARIO, 'Usuario'),
        (SUPERVISOR, 'Supervisor'),
        (ADMINISTRADOR, 'Administrador'),
    ]

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='perfis',
        db_column='id_usuario',
    )
    perfil = models.CharField(max_length=20, choices=PERFIL_CHOICES)

    class Meta:
        db_table = 'usuario_perfis'
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfis de Usuario'
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'perfil'], name='uniq_usuario_perfil'
            )
        ]

    def __str__(self):
        return f'{self.usuario.login} - {self.get_perfil_display()}'


class Token(models.Model):
    """
    Token de autenticacao (sessao). Validade de 7 dias (RG-AUTH-003).
    Validado localmente no dispositivo quando offline (RG-AUTH-007).
    """

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='tokens',
        db_column='id_usuario',
    )
    token = models.CharField(max_length=500, unique=True)
    validade = models.DateTimeField(
        help_text='data_criacao + VALIDADE_TOKEN_DIAS (padrao 7 dias).'
    )
    data_criacao = models.DateTimeField(auto_now_add=True)
    dispositivo = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text='Identificacao do dispositivo. Apenas informativo.',
    )

    class Meta:
        db_table = 'tokens'
        verbose_name = 'Token'
        verbose_name_plural = 'Tokens'
        indexes = [
            models.Index(fields=['token'], name='idx_tokens_token'),
            models.Index(fields=['usuario'], name='idx_tokens_id_usuario'),
            models.Index(fields=['validade'], name='idx_tokens_validade'),
        ]

    def __str__(self):
        return f'Token de {self.usuario.login} (expira {self.validade:%d/%m/%Y})'

    @property
    def expirado(self):
        return timezone.now() > self.validade

    @classmethod
    def gerar_para(cls, usuario, dispositivo=None):
        """
        Gera um novo token com validade de VALIDADE_TOKEN_DIAS dias
        (RG-AUTH-003). Valor unico e nao previsivel (Modelo Logico 6.3).
        """
        dias = getattr(settings, 'VALIDADE_TOKEN_DIAS', 7)
        return cls.objects.create(
            usuario=usuario,
            token=secrets.token_urlsafe(48),
            validade=timezone.now() + timedelta(days=dias),
            dispositivo=dispositivo,
        )


class TokenRedefinicaoSenha(models.Model):
    """
    30/07/2026: token de uso unico enviado por e-mail no fluxo "Esqueci
    minha senha". Validade curta (1h, bem menor que o Token de sessao)
    -- e um token de PROVA DE IDENTIDADE via e-mail, nao de sessao.

    Serve tambem como fluxo de "definir minha primeira senha" para
    usuarios legados que nunca tiveram senha (ver Usuario.senha_hash).
    """

    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.CASCADE,
        related_name='tokens_redefinicao',
        db_column='id_usuario',
    )
    token = models.CharField(max_length=255, unique=True)
    criado_em = models.DateTimeField(auto_now_add=True)
    validade = models.DateTimeField()
    usado = models.BooleanField(default=False)

    class Meta:
        db_table = 'tokens_redefinicao_senha'
        verbose_name = 'Token de Redefinição de Senha'
        verbose_name_plural = 'Tokens de Redefinição de Senha'
        indexes = [
            models.Index(fields=['token'], name='idx_token_redef_token'),
        ]

    def __str__(self):
        return f'Redefinicao para {self.usuario.login} (expira {self.validade:%d/%m/%Y %H:%M})'

    @property
    def expirado(self):
        return timezone.now() > self.validade

    @property
    def valido(self):
        return not self.usado and not self.expirado

    @classmethod
    def gerar_para(cls, usuario, horas_validade=1):
        return cls.objects.create(
            usuario=usuario,
            token=secrets.token_urlsafe(48),
            validade=timezone.now() + timedelta(hours=horas_validade),
        )
