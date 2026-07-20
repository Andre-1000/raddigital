"""
Modelos do app usuarios.

Cadastro de logins do sistema RAD, distinto do cadastro de colaboradores
(funcionarios da empresa). Um usuario e quem preenche o RAD.

Referencia: MODELO_LOGICO_BANCO_DE_DADOS_v2.docx, secoes 6.1 a 6.3.
Referencia: ESPECIFICACAO_FUNCIONAL_DETALHADA.docx, secao 3.9 (RG-AUTH)
e secao 4 (Matriz de Permissoes).
"""
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Usuario(models.Model):
    """Cadastro de login do sistema. Distinto de ColaboradorCadastro."""

    login = models.CharField(
        max_length=100,
        unique=True,
        help_text='Login unico. Usado para autenticacao sem senha (RG-AUTH-001).',
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
        # Combinacao id_usuario + perfil deve ser unica (nota do Modelo Logico 6.2)
        constraints = [
            models.UniqueConstraint(
                fields=['usuario', 'perfil'], name='uniq_usuario_perfil'
            )
        ]

    def __str__(self):
        return f'{self.usuario.login} - {self.get_perfil_display()}'


class Token(models.Model):
    """
    Token de autenticacao sem senha. Validade de 7 dias (RG-AUTH-003).
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
