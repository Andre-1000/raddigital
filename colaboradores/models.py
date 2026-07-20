"""
Modelo do app colaboradores — cadastro oficial de funcionarios da
empresa (Modelo Logico secao 6.4).

Distinto de Usuario (quem faz login no sistema) e de RadColaborador
(a copia historica gravada em cada RAD no momento da inclusao — ver
RG-RESP-010/011). Este e o cadastro-fonte, gerenciado pelo
Administrador (RG-RESP-012).
"""
from django.db import models


class ColaboradorCadastro(models.Model):
    registro_empresa = models.CharField(
        max_length=10,
        unique=True,
        help_text='Matricula. Apenas numeros (RG-RESP-002).',
    )
    nome = models.CharField(max_length=200)
    ativo = models.BooleanField(
        default=True, help_text='Inativo = nao aparece na pesquisa (RG-RESP-003).'
    )
    data_criacao = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'colaboradores_cadastro'
        verbose_name = 'Colaborador'
        verbose_name_plural = 'Cadastro de Colaboradores'
        ordering = ['nome']

    def __str__(self):
        return f'{self.registro_empresa} - {self.nome}'
