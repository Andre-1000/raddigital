"""
Validacoes de bloqueio executadas no momento da sincronizacao do RAD.

Referencia: EFD secao 3.12 (VALIDACOES INTELIGENTES), RG-VLD-001 a 003 e
VLD-001 a VLD-026, mais extensoes de negocio posteriores: VLD-027
(colaborador fora do cadastro oficial) e VLD-028 (novo campo N. SA).

RG-VLD-001/003: estas validacoes rodam exclusivamente quando o usuario
aciona Sincronizar -- nunca durante o preenchimento do rascunho local.
Por isso este modulo e chamado apenas pela view de sincronizacao, nunca
pelo salvamento de rascunho (que nem existe no servidor).

RG-VLD-002: quando ha falha, a view deve retornar TODOS os erros de uma
vez (para o usuario corrigir tudo antes de tentar de novo), nao parar no
primeiro. Por isso cada verificacao abaixo e independente e todas rodam
sempre, acumulando em uma lista.
"""
from catalogos.models import CatMotivoAtraso, CatServico
from colaboradores.models import ColaboradorCadastro

NOME_MOTIVO_OUTROS = 'Outros'
NOME_SERVICO_OUTROS = 'Outros'
NOME_TIPO_MANUTENCAO_FALHA = 'Falha'


def _erro(codigo, campo, mensagem):
    return {'codigo': codigo, 'campo': campo, 'mensagem': mensagem}


def _validar_os(payload, erros):
    """VLD-001: OS vazia ou invalida (deve ser numerica, 1 a 7 digitos, > 0)."""
    numero_os = payload.get('numero_os')
    if numero_os is None or not isinstance(numero_os, int) or numero_os <= 0:
        erros.append(_erro('VLD-001', 'numero_os', 'Informe uma OS com caracteres validos.'))
        return
    if numero_os > 9_999_999:
        erros.append(_erro('VLD-001', 'numero_os', 'A OS deve ter no maximo 7 digitos.'))


def _validar_numero_sa(payload, erros):
    """
    VLD-028: N. SA e obrigatorio, numerico, ate 10 caracteres.
    Campo novo e independente da OS -- mesmo padrao de validacao usado
    para o registro_empresa do cadastro de colaboradores (numerico,
    limite de caracteres), mas com sua propria regra e codigo.
    """
    numero_sa = payload.get('numero_sa')
    if not numero_sa:
        erros.append(_erro('VLD-028', 'numero_sa', 'Informe o N. SA.'))
        return
    numero_sa = str(numero_sa)
    if not numero_sa.isdigit():
        erros.append(_erro('VLD-028', 'numero_sa', 'O N. SA deve conter apenas numeros.'))
        return
    if len(numero_sa) > 10:
        erros.append(_erro('VLD-028', 'numero_sa', 'O N. SA deve ter no maximo 10 caracteres.'))


def _validar_data_preenchimento(payload, erros, hoje):
    """VLD-002: data vazia ou superior a data atual."""
    data = payload.get('data_preenchimento')
    if not data:
        erros.append(_erro('VLD-002', 'data_preenchimento', 'Informe uma data valida.'))
    elif data > hoje:
        erros.append(_erro('VLD-002', 'data_preenchimento', 'Informe uma data valida.'))


def _validar_locais(payload, erros):
    """VLD-005/VLD-006. VLD-025 (local igual) explicitamente NAO bloqueia."""
    if not payload.get('id_local_inicial'):
        erros.append(_erro('VLD-005', 'id_local_inicial', 'Selecione um Local Inicial.'))
    if not payload.get('id_local_final'):
        erros.append(_erro('VLD-006', 'id_local_final', 'Selecione um Local Final.'))


def _validar_linhas_e_vias(payload, erros):
    """VLD-007/VLD-008."""
    if not payload.get('linhas'):
        erros.append(_erro('VLD-007', 'linhas', 'Selecione ao menos uma Linha.'))
    if not payload.get('vias'):
        erros.append(_erro('VLD-008', 'vias', 'Selecione ao menos uma Via.'))


def _validar_tipo_manutencao(payload, erros):
    """VLD-009/VLD-010."""
    if not payload.get('id_tipo_manutencao'):
        erros.append(
            _erro('VLD-009', 'id_tipo_manutencao', 'Selecione o Tipo de Manutencao.')
        )
        return

    if payload.get('_tipo_manutencao_e_falha') and not payload.get('numero_falha'):
        erros.append(
            _erro(
                'VLD-010',
                'numero_falha',
                'O campo N. Falha e obrigatorio quando o Tipo de Manutencao for Falha.',
            )
        )


def _validar_horarios_obrigatorios(payload, erros):
    """VLD-011: qualquer horario obrigatorio vazio."""
    campos_horario = {
        'hora_prog_inicio': 'Horario Programado de Inicio',
        'hora_prog_termino': 'Horario Programado de Termino',
        'hora_real_inicio': 'Horario Real de Inicio',
        'hora_real_termino': 'Horario Real de Termino',
    }
    for campo, rotulo in campos_horario.items():
        if not payload.get(campo):
            erros.append(_erro('VLD-011', campo, f'Informe um {rotulo.lower()} valido.'))


def _validar_consistencia_datetime(payload, erros):
    """
    VLD-012/VLD-013: DateTime de termino anterior ao de inicio. So dispara
    quando o usuario editou manualmente as datas de forma inconsistente
    -- a virada de meia-noite automatica ja evita isso no fluxo normal.
    Requer que o chamador ja tenha processado os horarios (regras_horario)
    e incluido os campos data_hora_* no payload.
    """
    dt_prog_inicio = payload.get('data_hora_prog_inicio')
    dt_prog_termino = payload.get('data_hora_prog_termino')
    if dt_prog_inicio and dt_prog_termino and dt_prog_termino < dt_prog_inicio:
        erros.append(
            _erro(
                'VLD-012',
                'data_hp_termino',
                'O horario programado de termino nao pode ser anterior ao de inicio.',
            )
        )

    dt_real_inicio = payload.get('data_hora_real_inicio')
    dt_real_termino = payload.get('data_hora_real_termino')
    if dt_real_inicio and dt_real_termino and dt_real_termino < dt_real_inicio:
        erros.append(
            _erro(
                'VLD-013',
                'data_hr_termino',
                'O horario real de termino nao pode ser anterior ao de inicio.',
            )
        )


def _validar_motivos_atraso(payload, erros):
    """VLD-014/VLD-015/VLD-016."""
    if payload.get('atraso_inicio') and not payload.get('id_motivo_atraso_inicio'):
        erros.append(
            _erro(
                'VLD-014',
                'id_motivo_atraso_inicio',
                'Informe o motivo do atraso no inicio.',
            )
        )
    if payload.get('atraso_termino') and not payload.get('id_motivo_atraso_termino'):
        erros.append(
            _erro(
                'VLD-015',
                'id_motivo_atraso_termino',
                'Informe o motivo do atraso no termino.',
            )
        )

    for prefixo, campo_motivo, campo_desc in (
        ('inicio', 'id_motivo_atraso_inicio', 'desc_motivo_atraso_inicio'),
        ('termino', 'id_motivo_atraso_termino', 'desc_motivo_atraso_termino'),
    ):
        id_motivo = payload.get(campo_motivo)
        if id_motivo and not payload.get(campo_desc):
            # So exige descricao se o motivo selecionado for "Outros"
            nome_motivo = CatMotivoAtraso.objects.filter(id=id_motivo).values_list(
                'nome', flat=True
            ).first()
            if nome_motivo == NOME_MOTIVO_OUTROS:
                erros.append(
                    _erro(
                        'VLD-016',
                        campo_desc,
                        f'Informe a descricao do motivo do atraso no {prefixo}.',
                    )
                )


def _validar_servicos(payload, erros):
    """VLD-017/VLD-018."""
    servicos_ids = payload.get('servicos') or []
    if not servicos_ids:
        erros.append(_erro('VLD-017', 'servicos', 'Selecione ao menos um Servico Executado.'))
        return

    servico_outros_selecionado = CatServico.objects.filter(
        id__in=servicos_ids, nome=NOME_SERVICO_OUTROS
    ).exists()
    if servico_outros_selecionado and not payload.get('outros_servico_desc'):
        erros.append(
            _erro(
                'VLD-018',
                'outros_servico_desc',
                'Descreva o servico executado quando Outros for selecionado.',
            )
        )


def _validar_colaboradores(payload, erros):
    """VLD-019: minimo de 1 colaborador/participante."""
    if not payload.get('colaboradores'):
        erros.append(
            _erro('VLD-019', 'colaboradores', 'Adicione ao menos um colaborador ou participante.')
        )


def _validar_responsavel_atividade(payload, erros):
    """VLD-029: obrigatorio, no maximo 50 caracteres."""
    valor = payload.get('responsavel_atividade')
    if not valor or not str(valor).strip():
        erros.append(
            _erro('VLD-029', 'responsavel_atividade', 'Informe o Responsável Atividade.')
        )
        return
    if len(str(valor)) > 50:
        erros.append(
            _erro(
                'VLD-029',
                'responsavel_atividade',
                'O Responsável Atividade deve ter no máximo 50 caracteres.',
            )
        )


def _validar_operador_ccm(payload, erros):
    """
    VLD-030: campo opcional (nao ha regra de obrigatoriedade
    especificada), mas quando informado nao pode passar de 25 caracteres.
    """
    valor = payload.get('operador_ccm')
    if valor and len(str(valor)) > 25:
        erros.append(
            _erro('VLD-030', 'operador_ccm', 'O Operador CCM deve ter no máximo 25 caracteres.')
        )


def _validar_colaboradores_no_cadastro_oficial(payload, erros):
    """
    RG-RESP-008: colaboradores (tipo='colaborador', distinto de
    'participante') devem existir no cadastro oficial pelo
    registro_empresa informado. Participantes externos (RG-RESP-013)
    nao passam por esta checagem -- por definicao nao pertencem ao
    cadastro oficial.
    """
    for colaborador in payload.get('colaboradores') or []:
        if colaborador.get('tipo') != 'colaborador':
            continue
        registro = colaborador.get('registro_empresa')
        if not registro:
            continue  # cai em outra validacao de schema, nao e responsabilidade daqui
        if not ColaboradorCadastro.objects.filter(registro_empresa=registro).exists():
            erros.append(
                _erro(
                    'VLD-027',
                    'colaboradores',
                    f'Colaborador nao localizado (registro {registro}).',
                )
            )


def _validar_colaboradores_sem_registro_duplicado(payload, erros):
    """
    RG-RESP-009: o mesmo Registro da Empresa nao pode ser adicionado
    mais de uma vez no mesmo RAD.

    Bug real encontrado em teste manual (17/07/2026): esta regra so
    estava sendo garantida pela constraint unica do banco
    (uniq_rad_colaborador_registro), que gera um IntegrityError nao
    tratado -- ou seja, um payload com registro duplicado derrubava a
    sincronizacao inteira com erro 500 em vez de um 422 normal. Esta
    validacao intercepta o problema antes de chegar no banco.
    """
    vistos = set()
    duplicados = set()
    for colaborador in payload.get('colaboradores') or []:
        registro = colaborador.get('registro_empresa')
        if not registro:
            continue  # participantes (sem registro) nao entram nesta regra
        if registro in vistos:
            duplicados.add(registro)
        vistos.add(registro)

    for registro in sorted(duplicados):
        erros.append(
            _erro(
                'VLD-031',
                'colaboradores',
                f'O colaborador de registro {registro} foi adicionado mais de uma vez.',
            )
        )


def _validar_bloco_amv(payload, erros):
    """VLD-020/VLD-021/VLD-022: exigidos somente quando Manutencao em AMV foi selecionada."""
    servicos_ids = payload.get('servicos') or []
    amv_selecionado = CatServico.objects.filter(
        id__in=servicos_ids, requer_amv=True
    ).exists()
    if not amv_selecionado:
        return

    amv = payload.get('amv') or {}
    if not amv.get('id_mch'):
        erros.append(_erro('VLD-020', 'amv.id_mch', 'Selecione a Identificacao MCH.'))
    if not amv.get('tipos_defeito'):
        erros.append(_erro('VLD-021', 'amv.tipos_defeito', 'Selecione ao menos um Tipo de Defeito.'))
    if not amv.get('acoes'):
        erros.append(_erro('VLD-022', 'amv.acoes', 'Selecione ao menos uma Acao.'))


def _remover_erros_de_campos_desabilitados(erros):
    """
    Regra de negocio (17/07/2026): campo desabilitado pelo Administrador
    nao aparece para nenhum usuario -- portanto nao pode ser exigido na
    sincronizacao. Filtro generico: qualquer erro cujo 'campo' (ou o
    prefixo antes de '.', para casos como 'amv.id_mch') esteja
    desabilitado e descartado. Aplica-se automaticamente a QUALQUER
    validacao futura, sem precisar tocar em cada funcao _validar_*.
    """
    from configuracoes.servicos import campos_desabilitados

    desabilitados = campos_desabilitados()
    if not desabilitados:
        return erros
    return [
        e
        for e in erros
        if e['campo'] not in desabilitados and e['campo'].split('.')[0] not in desabilitados
    ]


def validar_payload_sincronizacao(payload, *, hoje):
    """
    Executa todas as validacoes de bloqueio da sincronizacao (VLD-001 a
    VLD-030, exceto VLD-023/024 que exigem os arquivos de anexo, ver
    rad.validadores_arquivos).

    payload deve conter, alem dos campos brutos do formulario, os campos
    ja calculados por rad.regras_horario.processar_horarios (
    data_hora_prog_inicio, data_hora_prog_termino, data_hora_real_inicio,
    data_hora_real_termino, atraso_inicio, atraso_termino) e a flag
    interna '_tipo_manutencao_e_falha'.

    hoje: date atual, injetada pelo chamador para facilitar testes
    deterministicos (RG-VLD independe de fuso, mas evita usar
    date.today() implicito dentro da funcao).

    Retorna uma lista de erros (vazia se tudo valido). RG-VLD-002: todos
    os erros sao retornados de uma vez, nao apenas o primeiro. Erros de
    campos desabilitados pelo Administrador sao removidos no final (ver
    _remover_erros_de_campos_desabilitados).
    """
    erros = []
    _validar_os(payload, erros)
    _validar_numero_sa(payload, erros)
    _validar_data_preenchimento(payload, erros, hoje)
    _validar_locais(payload, erros)
    _validar_linhas_e_vias(payload, erros)
    _validar_tipo_manutencao(payload, erros)
    _validar_horarios_obrigatorios(payload, erros)
    _validar_consistencia_datetime(payload, erros)
    _validar_motivos_atraso(payload, erros)
    _validar_servicos(payload, erros)
    _validar_colaboradores(payload, erros)
    _validar_colaboradores_no_cadastro_oficial(payload, erros)
    _validar_colaboradores_sem_registro_duplicado(payload, erros)
    _validar_bloco_amv(payload, erros)
    _validar_responsavel_atividade(payload, erros)
    _validar_operador_ccm(payload, erros)
    return _remover_erros_de_campos_desabilitados(erros)
