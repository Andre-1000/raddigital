"""
Modelos de catalogo do Sistema RAD.

Listas de referencia usadas no preenchimento do formulario RAD. Sao
armazenadas em cache local (IndexedDB) pelo cliente e atualizadas na
abertura da ferramenta quando ha conexao (RG conforme EFD secao 6 -
Catalogos em cache).

Referencia: MODELO_LOGICO_BANCO_DE_DADOS_v2.docx, secao 7 (7.1 a 7.9).
Os nomes de tabela e coluna seguem exatamente os arquivos seed_cat_*.sql
para que os seeds rodem sem qualquer adaptacao.
"""
from django.db import models


class CatLinha(models.Model):
    """CAT: linhas ferroviarias (11-Coral, 12-Safira, 13-Jade)."""

    codigo = models.CharField(max_length=5, primary_key=True)
    nome = models.CharField(max_length=100)

    class Meta:
        db_table = 'cat_linhas'
        verbose_name = 'Linha'
        verbose_name_plural = 'Catalogo: Linhas'
        ordering = ['codigo']

    def __str__(self):
        return f'{self.codigo} - {self.nome}'


class CatLocal(models.Model):
    """CAT-002: locais (estacoes, patios, cabines, subestacoes, etc)."""

    CATEGORIA_CHOICES = [
        ('estacao', 'Estacao'),
        ('patio', 'Patio'),
        ('cabine', 'Cabine'),
        ('subestacao', 'Subestacao'),
        ('terminal', 'Terminal'),
        ('vse', 'VSE'),
        ('almox', 'Almoxarifado'),
    ]

    sigla = models.CharField(max_length=20, primary_key=True)
    nome = models.CharField(max_length=200)
    categoria = models.CharField(max_length=50, choices=CATEGORIA_CHOICES)

    class Meta:
        db_table = 'cat_locais'
        verbose_name = 'Local'
        verbose_name_plural = 'Catalogo: Locais'
        ordering = ['sigla']

    def __str__(self):
        return f'{self.sigla} - {self.nome}'


class CatEquipe(models.Model):
    """Equipes envolvidas na atividade: RA, VP, CIVIL, RESTAB, SINAL, MRO."""

    codigo = models.CharField(max_length=10, primary_key=True)
    nome = models.CharField(max_length=100)

    class Meta:
        db_table = 'cat_equipes'
        verbose_name = 'Equipe'
        verbose_name_plural = 'Catalogo: Equipes'
        ordering = ['codigo']

    def __str__(self):
        return f'{self.codigo} - {self.nome}'


class CatTipoManutencao(models.Model):
    """Falha, Preventiva, Corretiva, Preditiva (EFD-010)."""

    nome = models.CharField(max_length=50, unique=True)

    class Meta:
        db_table = 'cat_tipos_manutencao'
        verbose_name = 'Tipo de Manutencao'
        verbose_name_plural = 'Catalogo: Tipos de Manutencao'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class CatVia(models.Model):
    """Via 1 a 4, Patio (EFD-008)."""

    nome = models.CharField(max_length=20, unique=True)

    class Meta:
        db_table = 'cat_vias'
        verbose_name = 'Via'
        verbose_name_plural = 'Catalogo: Vias'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class CatServico(models.Model):
    """CAT-003: 13 servicos executados. requer_amv abre o bloco AMV."""

    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(
        null=True, blank=True, help_text='Texto exibido no botao de ajuda (?).'
    )
    requer_amv = models.BooleanField(
        default=False, help_text='TRUE somente para Manutencao em AMV.'
    )
    requer_descricao = models.BooleanField(
        default=False, help_text='TRUE somente para Outros.'
    )
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = 'cat_servicos'
        verbose_name = 'Servico'
        verbose_name_plural = 'Catalogo: Servicos'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class CatMotivoAtraso(models.Model):
    """Comunicacao com CCO, Transito, Clima, Outros (EFD-018-A/019-A)."""

    nome = models.CharField(max_length=100, unique=True)
    requer_descricao = models.BooleanField(default=False)

    class Meta:
        db_table = 'cat_motivos_atraso'
        verbose_name = 'Motivo de Atraso'
        verbose_name_plural = 'Catalogo: Motivos de Atraso'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class CatMch(models.Model):
    """
    238 MCHs com dados de preenchimento automatico do bloco AMV.
    Ao selecionar a MCH, o sistema preenche modelo/via/ur/local_amv/linha
    (ur e linha nao editaveis; modelo/via/local_amv editaveis).
    """

    identificacao = models.CharField(max_length=50, unique=True)
    modelo = models.CharField(max_length=100)
    via = models.CharField(
        max_length=20,
        blank=True,
        help_text='MCH29U-BFU esta pendente de preenchimento (DT-PEND / EXP-PEND-001).',
    )
    ur = models.CharField(max_length=50)
    local_amv = models.CharField(max_length=100)
    linha = models.CharField(max_length=10)

    class Meta:
        db_table = 'cat_mch'
        verbose_name = 'MCH'
        verbose_name_plural = 'Catalogo: MCHs'
        ordering = ['identificacao']

    def __str__(self):
        return self.identificacao


class CatTipoDefeitoAmv(models.Model):
    """17 tipos de defeito do AMV (EFD-020-B)."""

    nome = models.CharField(max_length=100, unique=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = 'cat_tipos_defeito_amv'
        verbose_name = 'Tipo de Defeito AMV'
        verbose_name_plural = 'Catalogo: Tipos de Defeito AMV'
        ordering = ['nome']

    def __str__(self):
        return self.nome


class CatAcaoAmv(models.Model):
    """7 acoes do AMV (EFD-020-C)."""

    nome = models.CharField(max_length=100, unique=True)
    ativo = models.BooleanField(default=True)

    class Meta:
        db_table = 'cat_acoes_amv'
        verbose_name = 'Acao AMV'
        verbose_name_plural = 'Catalogo: Acoes AMV'
        ordering = ['nome']

    def __str__(self):
        return self.nome
