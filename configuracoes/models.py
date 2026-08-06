"""
Modelos do app configuracoes — habilitar/desabilitar campos do
formulario do RAD (mudanca de negocio 17/07/2026) e, desde 22/07/2026,
tornar cada campo obrigatorio ou opcional.

Regra de negocio (habilitado): qualquer campo do formulario pode ser
desabilitado pelo Administrador. Quando desabilitado, o campo deixa de
aparecer para TODOS os usuarios da ferramenta -- inclusive Supervisor e
o proprio Administrador -- ate ser habilitado novamente. Nao existe
visibilidade parcial por perfil: e tudo ou nada.

Regra de negocio (obrigatorio, 22/07/2026): exclusivo do Administrador
-- pode alternar qualquer campo entre obrigatorio e opcional. So tem
efeito para campos que ja estao habilitados (um campo desabilitado nao
aparece, entao obrigatoriedade e irrelevante para ele). Alguns campos
tem regras condicionais proprias (ex.: N. Falha so e exigido quando
Tipo de Manutencao = Falha) -- o toggle aqui funciona como uma
sobreposicao: se marcado obrigatorio=True, o campo passa a ser exigido
sempre, independente da condicao original; se obrigatorio=False, o
campo nunca e exigido, mesmo que a condicao original pedisse.

Efeitos praticos, ja implementados:
- rad/validadores.py: erros de validacao associados a um campo
  desabilitado sao descartados (o campo deixa de ser obrigatorio na
  pratica, porque ninguem consegue preenche-lo); a sobreposicao de
  obrigatoriedade e aplicada por cima das regras hardcoded.
- consulta/views.py: a chave do campo desabilitado e removida das
  respostas de listagem e detalhe do RAD.
- interface: asterisco vermelho nos campos exibido conforme a
  configuracao atual, buscada em /configuracoes/campos/.

O valor gravado no banco (se ja existia antes de desabilitar) NAO e
apagado -- apenas deixa de ser exibido. Reabilitar o campo volta a
mostrar o valor historico normalmente.
"""
from django.db import models

from usuarios.models import Usuario


class CampoFormulario(models.Model):
    chave = models.CharField(
        max_length=100,
        unique=True,
        help_text='Identificador tecnico do campo (ex.: responsavel_atividade).',
    )
    rotulo = models.CharField(
        max_length=200, help_text='Nome exibido ao usuario (ex.: "Responsável Atividade").'
    )
    habilitado = models.BooleanField(default=True)
    obrigatorio = models.BooleanField(
        default=False,
        help_text=(
            'Sobrepoe a regra de obrigatoriedade padrao do campo (22/07/2026). '
            'So tem efeito quando habilitado=True.'
        ),
    )
    atualizado_em = models.DateTimeField(auto_now=True)
    atualizado_por = models.ForeignKey(
        Usuario, null=True, blank=True, on_delete=models.SET_NULL
    )

    class Meta:
        db_table = 'campos_formulario'
        verbose_name = 'Campo do Formulário'
        verbose_name_plural = 'Configuração de Campos do Formulário'
        ordering = ['rotulo']

    def __str__(self):
        estado = 'habilitado' if self.habilitado else 'DESABILITADO'
        obrig = 'obrigatório' if self.obrigatorio else 'opcional'
        return f'{self.rotulo} ({estado}, {obrig})'


class LimiteFotos(models.Model):
    """
    30/07/2026: limite de fotos por categoria, configuravel pelo
    Administrador sem precisar de deploy -- mesma filosofia de
    CampoFormulario, mas para um NUMERO em vez de um interruptor.

    Motivacao: servicos da area "Infra" (Recolhimento de Lixo, Limpeza
    de Canaleta, Capina Quimica, Rocada/Poda -- ver
    catalogos.models.CatServico.area) exigem mais fotos por atividade
    do que o padrao (5 por categoria em vez de 2). Em vez de um numero
    fixo no codigo, cada combinacao categoria+area tem sua propria
    linha aqui, editavel pela tela de Configuracoes.

    'area' aqui usa dois valores apenas: 'padrao' (Geral e qualquer
    area que nao seja Infra) e 'infra'. Se no futuro outra area
    precisar de limite proprio (ex.: Mecanizada), basta adicionar uma
    nova combinacao categoria+area -- o codigo em
    rad/regras_negocio.py cai automaticamente no limite 'padrao' para
    qualquer area sem linha especifica cadastrada.
    """

    CATEGORIA_CHOICES = [
        ('intervencao_verificada', 'Intervenção Verificada'),
        ('acao_realizada', 'Ação Realizada'),
    ]
    AREA_CHOICES = [
        ('padrao', 'Padrão (Geral e demais áreas)'),
        ('infra', 'Infra'),
    ]

    categoria = models.CharField(max_length=30, choices=CATEGORIA_CHOICES)
    area = models.CharField(max_length=10, choices=AREA_CHOICES)
    limite = models.PositiveSmallIntegerField()
    atualizado_em = models.DateTimeField(auto_now=True)
    atualizado_por = models.ForeignKey(
        Usuario, null=True, blank=True, on_delete=models.SET_NULL, related_name='+'
    )

    class Meta:
        db_table = 'configuracoes_limite_fotos'
        verbose_name = 'Limite de Fotos'
        verbose_name_plural = 'Configuração de Limites de Fotos'
        ordering = ['categoria', 'area']
        constraints = [
            models.UniqueConstraint(fields=['categoria', 'area'], name='uniq_categoria_area_limite')
        ]

    def __str__(self):
        return f'{self.get_categoria_display()} ({self.get_area_display()}): {self.limite}'
