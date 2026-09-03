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
    solicitante_sa = models.TextField(
        null=True, blank=True,
        help_text='Quem solicitou a SA. Texto livre, sem limite de caracteres (22/07/2026).',
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
    tipo_veiculo = models.TextField(
        null=True, blank=True, help_text='Texto livre, sem limite de caracteres.'
    )
    operador = models.TextField(
        null=True, blank=True, help_text='Texto livre, sem limite de caracteres.'
    )

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

    # --- VPM001 (22/07/2026) ------------------------------------------------
    # Preenchidos apenas quando Tipo de Manutencao = VPM001. Uma
    # descricao de texto livre por foto anexada, ate 1000 caracteres
    # cada. Numeracao fixa: 1/2 = Fotos Intervencao Verificada,
    # 3/4 = Fotos Acao Realizada (mesma ordem exibida no formulario).
    desc_foto_1 = models.CharField(max_length=1000, null=True, blank=True)
    desc_foto_2 = models.CharField(max_length=1000, null=True, blank=True)
    desc_foto_3 = models.CharField(max_length=1000, null=True, blank=True)
    desc_foto_4 = models.CharField(max_length=1000, null=True, blank=True)

    # --- Terceiros (22/07/2026) --------------------------------------------
    # Preenchido quando ao menos um servico que exige mao de obra
    # terceirizada e selecionado (Recolhimento de Lixo, Limpeza de
    # Canaleta, Capina Quimica, Rocada/Poda -- ver
    # catalogos.models.CatServico.requer_terceiros). Todos opcionais,
    # numericos, ate 3 digitos -- validado no cliente, armazenado como
    # inteiro.
    terceiros_num_encarregados = models.IntegerField(null=True, blank=True)
    terceiros_num_op_maquina = models.IntegerField(null=True, blank=True)
    terceiros_num_ajudantes = models.IntegerField(null=True, blank=True)
    terceiros_num_motorista = models.IntegerField(null=True, blank=True)
    terceiros_volume = models.IntegerField(null=True, blank=True)

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
    # Operador CCM (30/07/2026): substituido de um unico campo texto
    # por dois pares Nome+Hora -- Abertura e Entrega. A hora tem
    # default '00:00' aplicado no cliente (rad_form.js), entao chega
    # aqui preenchida na pratica; nullable no banco pelo mesmo motivo
    # de responsavel_atividade acima (campo pode ser desabilitado).
    operador_ccm_abertura_nome = models.CharField(max_length=50, null=True, blank=True)
    operador_ccm_abertura_hora = models.TimeField(null=True, blank=True)
    operador_ccm_entrega_nome = models.CharField(max_length=50, null=True, blank=True)
    operador_ccm_entrega_hora = models.TimeField(null=True, blank=True)
    descricao_tecnica_atividade = models.TextField(
        null=True, blank=True, help_text='Sem limite de caracteres. Aceita qualquer caractere.'
    )

    # --- Exportacao / Sincronizacao ---------------------------------------
    # data_ultima_exportacao_excel (21/08/2026): substitui o antigo campo
    # 'exportado' (booleano, nunca usado em nenhum lugar do sistema --
    # confirmado 0 registros com valor True antes da remocao). Guarda
    # QUANDO o RAD foi incluido pela ultima vez numa exportacao Excel,
    # nao so um SIM/NAO -- da historico/auditoria e permite que o
    # endpoint 'Exportar novos para Excel'
    # (consulta/views.py::exportar_excel) filtre automaticamente so o
    # que ainda nao foi exportado (data_ultima_exportacao_excel IS
    # NULL), sem controle manual.
    data_ultima_exportacao_excel = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=SINCRONIZADO
    )

    # --- Dispositivo (22/07/2026) ------------------------------------------
    # Detectado automaticamente a partir do User-Agent no momento da
    # sincronizacao (rad/views.py::_detectar_dispositivo) -- nunca
    # informado pelo cliente, para nao poder ser falsificado a toa.
    DESKTOP = 'desktop'
    MOBILE = 'mobile'
    DESCONHECIDO = 'desconhecido'
    DISPOSITIVO_CHOICES = [
        (DESKTOP, 'Computador'),
        (MOBILE, 'Celular'),
        (DESCONHECIDO, 'Desconhecido'),
    ]
    dispositivo = models.CharField(
        max_length=20,
        choices=DISPOSITIVO_CHOICES,
        default=DESCONHECIDO,
        help_text='Detectado automaticamente pelo navegador usado na sincronizacao.',
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
    Bloco AMV. 30/07/2026: deixou de ser 1-para-1 com o RAD -- um RAD
    pode ter varios blocos AMV (ate 16), um por MCH verificada no dia
    (RG: o mesmo tecnico pode verificar mais de uma MCH na mesma
    atividade, cada uma com seu proprio defeito/acao). UR e Linha nao
    sao editaveis pelo usuario; Modelo, Via e Local sao.

    04/09/2026: `mch` e os campos copiados dela (modelo/via/ur/local/
    linha) passaram a ser opcionais -- criado o par
    mch_nao_cadastrada/desc_mch_nao_cadastrada como via alternativa
    para quando a MCH verificada em campo ainda nao existe no
    catalogo. Regra (CheckConstraint abaixo): OU um bloco tem `mch`
    preenchida e `mch_nao_cadastrada=False`, OU tem
    `mch_nao_cadastrada=True` com `mch` vazia -- nunca os dois ao
    mesmo tempo, nunca nenhum dos dois.
    """

    rad = models.ForeignKey(
        Rad, on_delete=models.CASCADE, related_name='amv_blocos', db_column='id_rad'
    )
    mch = models.ForeignKey(
        CatMch, on_delete=models.PROTECT, db_column='id_mch', null=True, blank=True
    )
    modelo_mch = models.CharField(max_length=100, null=True, blank=True)
    via_mch = models.CharField(max_length=20, null=True, blank=True)
    ur_mch = models.CharField(max_length=50, null=True, blank=True)
    local_mch = models.CharField(max_length=100, null=True, blank=True)
    linha_mch = models.CharField(max_length=10, null=True, blank=True)
    # 04/09/2026: escape hatch para MCH ainda nao cadastrada no
    # catalogo -- ver docstring da classe. desc_mch_nao_cadastrada e
    # texto livre, ate 50 caracteres (mesmo limite de
    # responsavel_atividade), validado em rad/validadores.py::
    # _validar_bloco_amv.
    mch_nao_cadastrada = models.BooleanField(default=False)
    desc_mch_nao_cadastrada = models.CharField(max_length=50, null=True, blank=True)
    # 22/07/2026: preenchidos so quando "Outros" e selecionado em Tipo
    # de Defeito / Acoes (ver catalogos.models.CatTipoDefeitoAmv/
    # CatAcaoAmv.requer_descricao) -- mesmo padrao de outros_servico_desc.
    # Cada bloco AMV tem sua propria descricao, independente dos demais
    # blocos do mesmo RAD.
    desc_outros_tipo_defeito = models.TextField(null=True, blank=True)
    desc_outros_acao = models.TextField(null=True, blank=True)

    class Meta:
        db_table = 'rad_amv'
        verbose_name = 'Bloco AMV'
        verbose_name_plural = 'Blocos AMV'
        ordering = ['id']
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(mch_nao_cadastrada=False, mch__isnull=False)
                    | models.Q(mch_nao_cadastrada=True, mch__isnull=True)
                ),
                name='chk_rad_amv_mch_xor_nao_cadastrada',
            )
        ]

    def __str__(self):
        identificacao = self.mch.identificacao if self.mch else f'não cadastrada: {self.desc_mch_nao_cadastrada}'
        return f'AMV de {self.rad.numero_rad} ({identificacao})'


class RadAmvDefeito(models.Model):
    """
    Tipos de defeito selecionados num bloco AMV especifico (EFD-020-B).
    30/07/2026: passou a apontar para o bloco (RadAmv), nao mais
    diretamente para o RAD -- necessario para nao misturar defeitos de
    MCHs diferentes no mesmo RAD.
    """

    amv = models.ForeignKey(
        RadAmv, on_delete=models.CASCADE, related_name='defeitos', db_column='id_amv'
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
                fields=['amv', 'tipo_defeito'], name='uniq_amv_defeito'
            )
        ]


class RadAmvAcao(models.Model):
    """
    Acoes selecionadas num bloco AMV especifico (EFD-020-C). 30/07/2026:
    mesma mudanca de RadAmvDefeito -- aponta para o bloco (RadAmv), nao
    mais diretamente para o RAD.
    """

    amv = models.ForeignKey(
        RadAmv, on_delete=models.CASCADE, related_name='acoes', db_column='id_amv'
    )
    acao = models.ForeignKey(
        CatAcaoAmv, on_delete=models.PROTECT, db_column='id_acao'
    )

    class Meta:
        db_table = 'rad_amv_acoes'
        verbose_name = 'Acao AMV do RAD'
        verbose_name_plural = 'Acoes AMV do RAD'
        constraints = [
            models.UniqueConstraint(fields=['amv', 'acao'], name='uniq_amv_acao')
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

    As descricoes de foto do VPM001 NAO ficam aqui -- ficam em 4 campos
    fixos no proprio Rad (desc_foto_1 a desc_foto_4), numerados na
    mesma ordem exibida no formulario, e nao vinculadas a um RadAnexo
    especifico. Ver Rad.desc_foto_1..4.
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


class RadCanaleta(models.Model):
    """
    30/07/2026: bloco "Anomalias" -- aberto quando o servico "Inspeção
    de Canaleta" (area infra, CatServico.requer_canaleta) e
    selecionado. Diferente do bloco AMV (que pode se repetir varias
    vezes por RAD, um por MCH), aqui e sempre 1-para-1 com o RAD --
    so existe uma inspecao de canaleta por RAD.

    14/08/2026: ganhou o campo justificativa (texto livre, exigido pela
    validacao -- VLD-045 -- somente quando grau_criticidade e Media,
    Alta ou Critica). As antigas 5 medidas fixas (largura/altura/
    comprimento) saíram daqui e viraram uma lista repetivel -- ver
    RadCanaletaDimensao.
    """

    BAIXA = 'baixa'
    MEDIA = 'media'
    ALTA = 'alta'
    CRITICA = 'critica'
    GRAU_CRITICIDADE_CHOICES = [
        (BAIXA, 'Baixa'),
        (MEDIA, 'Média'),
        (ALTA, 'Alta'),
        (CRITICA, 'Crítica'),
    ]

    rad = models.OneToOneField(
        Rad, on_delete=models.CASCADE, related_name='canaleta', db_column='id_rad'
    )
    grau_criticidade = models.CharField(max_length=10, choices=GRAU_CRITICIDADE_CHOICES)
    justificativa = models.TextField(
        null=True, blank=True,
        help_text=(
            'Obrigatoria (VLD-045) quando grau_criticidade e Media, Alta '
            'ou Critica. Sem limite de caracteres.'
        ),
    )
    necessita_cautela = models.BooleanField()

    class Meta:
        db_table = 'rad_canaleta'
        verbose_name = 'Bloco Anomalias (Canaleta)'
        verbose_name_plural = 'Blocos Anomalias (Canaleta)'

    def __str__(self):
        return f'Canaleta de {self.rad.numero_rad}'


class RadCanaletaDimensao(models.Model):
    """
    14/08/2026: linha de medidas da Canaleta. Ate LIMITE_DIMENSOES (ver
    rad/validadores.py) linhas por bloco Canaleta -- mesmo padrao do
    RadAmv (repete via ForeignKey, nao e 1-para-1), mas aninhado dentro
    do bloco Canaleta em vez de apontar direto pro Rad. 'ordem' guarda a
    posicao em que a linha foi preenchida no formulario, para exibir na
    mesma sequencia depois.
    """

    canaleta = models.ForeignKey(
        RadCanaleta, on_delete=models.CASCADE, related_name='dimensoes', db_column='id_canaleta'
    )
    ordem = models.PositiveSmallIntegerField(default=1)
    largura_inicial = models.DecimalField(max_digits=8, decimal_places=2)
    largura_final = models.DecimalField(max_digits=8, decimal_places=2)
    altura_inicial = models.DecimalField(max_digits=8, decimal_places=2)
    altura_final = models.DecimalField(max_digits=8, decimal_places=2)
    comprimento = models.DecimalField(max_digits=8, decimal_places=2)
    # 14/08/2026: km/poste da linha de medida -- texto livre, mesmo
    # formato/mascara do campo Km/Poste geral do RAD (XX/XX - XX/XX),
    # mas opcional (nao entra em VLD-042): cada linha de Dimensões pode
    # ter seu proprio trecho, sem travar a sincronizacao se a pessoa
    # nao souber o km exato.
    km_poste_inicial = models.CharField(max_length=20, null=True, blank=True)
    km_poste_final = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table = 'rad_canaleta_dimensoes'
        verbose_name = 'Dimensão da Canaleta'
        verbose_name_plural = 'Dimensões da Canaleta'
        ordering = ['ordem', 'id']

    def __str__(self):
        return f'Dimensão {self.ordem} de {self.canaleta.rad.numero_rad}'


class RadCanaletaAnomalia(models.Model):
    """Anomalias selecionadas no bloco Canaleta. Multipla selecao."""

    LIMPA = 'limpa'
    OBSTRUIDA = 'obstruida'
    AUSENTE = 'ausente'
    QUEBRADA = 'quebrada'
    VEGETACAO = 'vegetacao'
    LASTRO = 'lastro'
    LIXO = 'lixo'
    DORMENTES = 'dormentes'
    ENTULHO = 'entulho'
    TERRA = 'terra'
    ANOMALIA_CHOICES = [
        (LIMPA, 'Limpa'),
        (OBSTRUIDA, 'Obstruída'),
        (AUSENTE, 'Ausente'),
        (QUEBRADA, 'Quebrada'),
        (VEGETACAO, 'Vegetação'),
        (LASTRO, 'Lastro'),
        (LIXO, 'Lixo'),
        (DORMENTES, 'Dormentes'),
        (ENTULHO, 'Entulho'),
        (TERRA, 'Terra'),
    ]

    canaleta = models.ForeignKey(
        RadCanaleta, on_delete=models.CASCADE, related_name='anomalias', db_column='id_canaleta'
    )
    anomalia = models.CharField(max_length=20, choices=ANOMALIA_CHOICES)

    class Meta:
        db_table = 'rad_canaleta_anomalias'
        verbose_name = 'Anomalia da Canaleta'
        verbose_name_plural = 'Anomalias da Canaleta'
        constraints = [
            models.UniqueConstraint(fields=['canaleta', 'anomalia'], name='uniq_canaleta_anomalia')
        ]


class RadCanaletaLado(models.Model):
    """Lados selecionados no bloco Canaleta. Multipla selecao."""

    DIREITO = 'direito'
    ESQUERDO = 'esquerdo'
    ENTREVIA = 'entrevia'
    LADO_CHOICES = [
        (DIREITO, 'Direito'),
        (ESQUERDO, 'Esquerdo'),
        (ENTREVIA, 'Entrevia'),
    ]

    canaleta = models.ForeignKey(
        RadCanaleta, on_delete=models.CASCADE, related_name='lados', db_column='id_canaleta'
    )
    lado = models.CharField(max_length=10, choices=LADO_CHOICES)

    class Meta:
        db_table = 'rad_canaleta_lados'
        verbose_name = 'Lado da Canaleta'
        verbose_name_plural = 'Lados da Canaleta'
        constraints = [
            models.UniqueConstraint(fields=['canaleta', 'lado'], name='uniq_canaleta_lado')
        ]
