"""
Modelos do app rad — tabela principal do Sistema RAD e suas tabelas
relacionadas (multipla selecao, bloco AMV, colaboradores, anexos).

Referencia: MODELO_LOGICO_BANCO_DE_DADOS_v2.docx, secao 5 (5.1 a 5.9).
Referencia: ESPECIFICACAO_FUNCIONAL_DETALHADA.docx, secoes 3.1 a 3.13.

Importante: o RAD so chega a este banco apos sincronizacao bem sucedida
(nota do Modelo Logico 5.1). Os status rascunho_local e sincronizando
existem apenas no cliente (IndexedDB) e nao sao modelados aqui.
"""
from django.db import models

from catalogos.models import (
    CatAcaoAmv,
    CatEquipe,
    CatLinha,
    CatLocal,
    CatMch,
    CatMotivoAtraso,
    CatServico,
    CatTipoDefeitoAmv,
    CatTipoManutencao,
    CatVia,
)
from usuarios.models import Usuario


class Rad(models.Model):
    """
    Registro principal do Relatorio de Atividade Diaria. Campos de valor
    unico do formulario (EFD-001 a EFD-019). Campos com multipla selecao
    (linhas, vias, servicos, colaboradores, anexos) ficam em tabelas
    separadas — ver relacionamentos abaixo.
    """

    SINCRONIZADO = 'sincronizado'
    CANCELADO = 'cancelado'
    STATUS_CHOICES = [
        (SINCRONIZADO, 'Sincronizado'),
        (CANCELADO, 'Cancelado'),
    ]

    # --- Identificacao (EFD-001) ---------------------------------------
    id_rad = models.AutoField(primary_key=True)
    numero_rad = models.CharField(
        max_length=10,
        unique=True,
        help_text='ID visivel. Formato R00001. Gerado na sincronizacao.',
    )
    numero_os = models.IntegerField(help_text='OS informada pelo usuario. Pode se repetir.')
    numero_sa = models.CharField(
        max_length=10,
        help_text='N. SA. Numerico, ate 10 caracteres. Campo obrigatorio, independente da OS.',
    )
    numero_execucao = models.IntegerField(
        help_text='Ordem de execucao dentro da mesma OS. Gerado atomicamente (RG-IDENT-008/009).'
    )
    data_preenchimento = models.DateField()

    # --- Localizacao (EFD-005 a EFD-009) --------------------------------
    local_inicial = models.ForeignKey(
        CatLocal,
        on_delete=models.PROTECT,
        related_name='rads_local_inicial',
        db_column='id_local_inicial',
    )
    local_final = models.ForeignKey(
        CatLocal,
        on_delete=models.PROTECT,
        related_name='rads_local_final',
        db_column='id_local_final',
    )
    km_poste = models.CharField(max_length=20, null=True, blank=True)

    # --- Controle operacional (EFD-010, EFD-011) ------------------------
    tipo_manutencao = models.ForeignKey(
        CatTipoManutencao, on_delete=models.PROTECT, db_column='id_tipo_manutencao'
    )
    numero_falha = models.IntegerField(
        null=True, blank=True, help_text='Obrigatorio quando tipo_manutencao = Falha.'
    )

    # --- Horarios (EFD-012 a EFD-017) -----------------------------------
    hora_prog_inicio = models.TimeField()
    data_hp_inicio = models.DateField()
    hora_prog_termino = models.TimeField()
    data_hp_termino = models.DateField()
    hora_real_inicio = models.TimeField()
    data_hr_inicio = models.DateField()
    hora_real_termino = models.TimeField()
    data_hr_termino = models.DateField()

    # DateTime completos, calculados a partir dos pares data+hora acima
    # (RG-HOR-024/025). Usados em todos os calculos de duracao.
    data_hora_prog_inicio = models.DateTimeField()
    data_hora_prog_termino = models.DateTimeField()
    data_hora_real_inicio = models.DateTimeField()
    data_hora_real_termino = models.DateTimeField()

    duracao_programada_min = models.IntegerField()
    duracao_real_min = models.IntegerField()

    # --- Atrasos (EFD-018, EFD-019) --------------------------------------
    atraso_inicio = models.BooleanField(default=False)
    motivo_atraso_inicio = models.ForeignKey(
        CatMotivoAtraso,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='rads_atraso_inicio',
        db_column='id_motivo_atraso_inicio',
    )
    desc_motivo_atraso_inicio = models.TextField(null=True, blank=True)

    atraso_termino = models.BooleanField(default=False)
    motivo_atraso_termino = models.ForeignKey(
        CatMotivoAtraso,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='rads_atraso_termino',
        db_column='id_motivo_atraso_termino',
    )
    desc_motivo_atraso_termino = models.TextField(null=True, blank=True)

    # --- Execucao (EFD-020) ----------------------------------------------
    outros_servico_desc = models.CharField(max_length=500, null=True, blank=True)
    materiais_utilizados = models.TextField(null=True, blank=True)
    observacoes_gerais = models.TextField(null=True, blank=True)

    # --- Responsaveis e detalhes tecnicos (mudanca de negocio 17/07/2026) --
    # Nullable no banco propositalmente: a obrigatoriedade de
    # responsavel_atividade e imposta pela validacao (VLD-029), nao pelo
    # schema -- isso permite que o campo seja desabilitado (ver app
    # configuracoes) sem violar constraint NOT NULL quando o cliente
    # deixa de envia-lo.
    responsavel_atividade = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text='Obrigatorio quando o campo estiver habilitado (VLD-029).',
    )
    operador_ccm = models.CharField(max_length=25, null=True, blank=True)
    descricao_tecnica_atividade = models.TextField(
        null=True, blank=True, help_text='Sem limite de caracteres. Aceita qualquer caractere.'
    )

    # --- Exportacao / Sincronizacao ---------------------------------------
    exportado = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=SINCRONIZADO
    )
    usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        to_field='login',
        db_column='login_usuario',
        related_name='rads_criados',
    )
    data_sincronizacao = models.DateTimeField()
    sync_id_tentativa = models.CharField(
        max_length=100,
        unique=True,
        help_text='ID unico de tentativa. Garante idempotencia em reenvios.',
    )

    # --- Cancelamento ------------------------------------------------------
    justificativa_cancelamento = models.TextField(null=True, blank=True)
    usuario_cancelamento = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        to_field='login',
        db_column='login_cancelamento',
        related_name='rads_cancelados',
        null=True,
        blank=True,
    )
    data_cancelamento = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'rad'
        verbose_name = 'RAD'
        verbose_name_plural = 'RADs'
        indexes = [
            models.Index(fields=['numero_os'], name='idx_rad_numero_os'),
            models.Index(fields=['status'], name='idx_rad_status'),
            models.Index(
                fields=['data_preenchimento'], name='idx_rad_data_preenchimento'
            ),
            models.Index(fields=['usuario'], name='idx_rad_login_usuario'),
        ]

    def __str__(self):
        return self.numero_rad or f'RAD (OS {self.numero_os}, sem numero ainda)'


class RadLinha(models.Model):
    """Linhas ferroviarias selecionadas por RAD (EFD-007). Multipla selecao."""

    rad = models.ForeignKey(
        Rad, on_delete=models.CASCADE, related_name='linhas', db_column='id_rad'
    )
    linha = models.ForeignKey(
        CatLinha, on_delete=models.PROTECT, db_column='codigo_linha'
    )

    class Meta:
        db_table = 'rad_linhas'
        verbose_name = 'Linha do RAD'
        verbose_name_plural = 'Linhas do RAD'
        constraints = [
            models.UniqueConstraint(fields=['rad', 'linha'], name='uniq_rad_linha')
        ]


class RadVia(models.Model):
    """Vias selecionadas por RAD (EFD-008). Multipla selecao."""

    rad = models.ForeignKey(
        Rad, on_delete=models.CASCADE, related_name='vias', db_column='id_rad'
    )
    via = models.ForeignKey(CatVia, on_delete=models.PROTECT, db_column='id_via')

    class Meta:
        db_table = 'rad_vias'
        verbose_name = 'Via do RAD'
        verbose_name_plural = 'Vias do RAD'
        constraints = [
            models.UniqueConstraint(fields=['rad', 'via'], name='uniq_rad_via')
        ]


class RadEquipe(models.Model):
    """
    Equipes envolvidas selecionadas por RAD (mudanca de negocio
    17/07/2026). Multipla selecao, de 1 ate todas as opcoes do
    catalogo. A equipe VP e sempre incluida automaticamente na
    persistencia (ver rad/regras_negocio.py::_criar_relacionamentos),
    independente do que o cliente enviar.
    """

    rad = models.ForeignKey(
        Rad, on_delete=models.CASCADE, related_name='equipes', db_column='id_rad'
    )
    equipe = models.ForeignKey(CatEquipe, on_delete=models.PROTECT, db_column='codigo_equipe')

    class Meta:
        db_table = 'rad_equipes'
        verbose_name = 'Equipe do RAD'
        verbose_name_plural = 'Equipes do RAD'
        constraints = [
            models.UniqueConstraint(fields=['rad', 'equipe'], name='uniq_rad_equipe')
        ]


class RadServico(models.Model):
    """Servicos executados selecionados por RAD (EFD-020). Multipla selecao."""

    rad = models.ForeignKey(
        Rad, on_delete=models.CASCADE, related_name='servicos', db_column='id_rad'
    )
    servico = models.ForeignKey(
        CatServico, on_delete=models.PROTECT, db_column='id_servico'
    )

    class Meta:
        db_table = 'rad_servicos'
        verbose_name = 'Servico do RAD'
        verbose_name_plural = 'Servicos do RAD'
        constraints = [
            models.UniqueConstraint(
                fields=['rad', 'servico'], name='uniq_rad_servico'
            )
        ]


class RadAmv(models.Model):
    """
    Bloco AMV. No maximo um registro por RAD (id_rad UNIQUE). Criado
    quando "Manutencao em AMV" e selecionada em EFD-020.
    UR e Linha nao sao editaveis pelo usuario; Modelo, Via e Local sao.
    """

    rad = models.OneToOneField(
        Rad, on_delete=models.CASCADE, related_name='amv', db_column='id_rad'
    )
    mch = models.ForeignKey(CatMch, on_delete=models.PROTECT, db_column='id_mch')
    modelo_mch = models.CharField(max_length=100)
    via_mch = models.CharField(max_length=20)
    ur_mch = models.CharField(max_length=50)
    local_mch = models.CharField(max_length=100)
    linha_mch = models.CharField(max_length=10)

    class Meta:
        db_table = 'rad_amv'
        verbose_name = 'Bloco AMV'
        verbose_name_plural = 'Blocos AMV'

    def __str__(self):
        return f'AMV de {self.rad.numero_rad} ({self.mch.identificacao})'


class RadAmvDefeito(models.Model):
    """Tipos de defeito selecionados no bloco AMV (EFD-020-B)."""

    rad = models.ForeignKey(
        Rad,
        on_delete=models.CASCADE,
        related_name='amv_defeitos',
        db_column='id_rad',
    )
    tipo_defeito = models.ForeignKey(
        CatTipoDefeitoAmv, on_delete=models.PROTECT, db_column='id_tipo_defeito'
    )

    class Meta:
        db_table = 'rad_amv_defeitos'
        verbose_name = 'Defeito AMV do RAD'
        verbose_name_plural = 'Defeitos AMV do RAD'
        constraints = [
            models.UniqueConstraint(
                fields=['rad', 'tipo_defeito'], name='uniq_rad_amv_defeito'
            )
        ]


class RadAmvAcao(models.Model):
    """Acoes selecionadas no bloco AMV (EFD-020-C)."""

    rad = models.ForeignKey(
        Rad, on_delete=models.CASCADE, related_name='amv_acoes', db_column='id_rad'
    )
    acao = models.ForeignKey(
        CatAcaoAmv, on_delete=models.PROTECT, db_column='id_acao'
    )

    class Meta:
        db_table = 'rad_amv_acoes'
        verbose_name = 'Acao AMV do RAD'
        verbose_name_plural = 'Acoes AMV do RAD'
        constraints = [
            models.UniqueConstraint(fields=['rad', 'acao'], name='uniq_rad_amv_acao')
        ]


class RadColaborador(models.Model):
    """
    Snapshot dos colaboradores/participantes vinculados ao RAD. Dados
    copiados no momento da inclusao — independentes de futuras alteracoes
    no cadastro oficial (colaboradores_cadastro).
    """

    COLABORADOR = 'colaborador'
    PARTICIPANTE = 'participante'
    TIPO_CHOICES = [
        (COLABORADOR, 'Colaborador'),
        (PARTICIPANTE, 'Participante'),
    ]

    rad = models.ForeignKey(
        Rad,
        on_delete=models.CASCADE,
        related_name='colaboradores',
        db_column='id_rad',
    )
    registro_empresa = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text='Matricula. NULL para participantes externos.',
    )
    nome = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)

    class Meta:
        db_table = 'rad_colaboradores'
        verbose_name = 'Colaborador do RAD'
        verbose_name_plural = 'Colaboradores do RAD'
        constraints = [
            # RG-RESP-009: o mesmo colaborador nao pode aparecer duas vezes
            # no mesmo RAD. Nao se aplica a participantes (registro_empresa NULL).
            models.UniqueConstraint(
                fields=['rad', 'registro_empresa'],
                name='uniq_rad_colaborador_registro',
                condition=models.Q(registro_empresa__isnull=False),
            )
        ]

    def __str__(self):
        return f'{self.nome} ({self.get_tipo_display()})'


class RadAnexo(models.Model):
    """
    Referencias aos arquivos anexados (fotos e PDF). Arquivos ficam no
    servidor de arquivos, separado do banco (DT/arquitetura).

    Fotos sao divididas em dois grupos com tema proprio, ate 2 cada:
    "Intervencao verificada" (situacao encontrada antes da execucao) e
    "Acao realizada" (evidencia do servico apos a execucao). PDF nao
    tem categoria -- e um unico documento, sem distincao tematica.
    """

    FOTO = 'foto'
    PDF = 'pdf'
    TIPO_ARQUIVO_CHOICES = [
        (FOTO, 'Foto'),
        (PDF, 'PDF'),
    ]

    INTERVENCAO_VERIFICADA = 'intervencao_verificada'
    ACAO_REALIZADA = 'acao_realizada'
    CATEGORIA_FOTO_CHOICES = [
        (INTERVENCAO_VERIFICADA, 'Intervenção verificada'),
        (ACAO_REALIZADA, 'Ação realizada'),
    ]

    LIMITE_TAMANHO_BYTES = 10_485_760  # 10 MB
    LIMITE_FOTOS_POR_CATEGORIA = 2
    LIMITE_FOTOS = 4  # LIMITE_FOTOS_POR_CATEGORIA * 2 categorias
    LIMITE_PDF = 1

    rad = models.ForeignKey(
        Rad, on_delete=models.CASCADE, related_name='anexos', db_column='id_rad'
    )
    tipo_arquivo = models.CharField(max_length=10, choices=TIPO_ARQUIVO_CHOICES)
    categoria_foto = models.CharField(
        max_length=30,
        choices=CATEGORIA_FOTO_CHOICES,
        null=True,
        blank=True,
        help_text='Obrigatorio quando tipo_arquivo=foto. Nulo para PDF.',
    )
    nome_original = models.CharField(max_length=255)
    caminho_servidor = models.CharField(max_length=500)
    tamanho_bytes = models.IntegerField()
    data_upload = models.DateTimeField()

    class Meta:
        db_table = 'rad_anexos'
        verbose_name = 'Anexo do RAD'
        verbose_name_plural = 'Anexos do RAD'
        constraints = [
            # Toda foto tem categoria; nenhum PDF tem categoria.
            models.CheckConstraint(
                condition=(
                    models.Q(tipo_arquivo='foto', categoria_foto__isnull=False)
                    | models.Q(tipo_arquivo='pdf', categoria_foto__isnull=True)
                ),
                name='chk_rad_anexo_categoria_coerente_com_tipo',
            )
        ]

    def __str__(self):
        if self.categoria_foto:
            return f'{self.nome_original} ({self.get_categoria_foto_display()}) — {self.rad.numero_rad}'
        return f'{self.nome_original} ({self.rad.numero_rad})'
