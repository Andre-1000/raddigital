"""
Modelo do app configuracoes — habilitar/desabilitar campos do
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
