"""
Edicao de RAD ja sincronizado pelo Administrador -- 13/10/2026.

Regras de negocio (decididas com o cliente):
- So o Administrador edita (a view aplica @requer_perfil).
- Qualquer campo pode ser editado, inclusive adicionar/ocultar fotos.
- O RAD e editado NO LUGAR (mesmo numero_rad) -- nao vira um RAD novo.
- Todo salvamento exige um MOTIVO e gera uma linha em RadEdicao com o
  antes/depois de cada campo alterado (rastro de auditoria).
- A edicao passa pelas MESMAS validacoes de um RAD novo (inclusive as
  regras de campo obrigatorio/opcional configuradas em Configuracoes).
- Fotos "removidas" sao OCULTADAS (RadAnexo.oculto), nao apagadas.
- Editar NAO reenvia nada sozinho: so marca o Word no Drive e a linha
  da planilha como DESATUALIZADOS (Rad.data_ultima_edicao >
  data_ultimo_envio_drive / data_ultima_sincronizacao_planilha). O
  reenvio e manual (botao no detalhe do RAD e tela Sync BD) -- gerar
  Word com fotos e o passo mais pesado de memoria do servico (512MB) e
  nao deve acontecer dentro da requisicao de edicao.
- Se a OS mudar, o RAD recebe um novo numero de execucao na OS nova
  (maior existente + 1). A OS antiga fica com o "buraco" -- nunca
  renumeramos outros RADs, para nao mudar numeros ja usados em campo.
"""
from django.db import transaction
from django.utils import timezone

from catalogos.models import CatTipoManutencao

from .models import Rad, RadAnexo, RadEdicao
from .regras_negocio import (
    _criar_relacionamentos,
    _limites_de_foto_do_payload,
    _preparar_horarios,
    _salvar_anexos,
    _travar_os,
    montar_dados_rad,
    proxima_execucao_da_os,
)
from .validadores import validar_payload_sincronizacao
from .validadores_arquivos import _erro, _validar_foto_individual, _validar_pdf_individual


class RadNaoEncontradoError(Exception):
    pass


class RadCanceladoError(Exception):
    pass


# ---------------------------------------------------------------------------
# Rad -> formato do formulario (rascunho)
# ---------------------------------------------------------------------------

def _hora(valor):
    return valor.strftime('%H:%M') if valor else ''


def _data(valor):
    return valor.isoformat() if valor else ''


def _texto(valor):
    return '' if valor is None else str(valor)


def _numero_terceiros(valor):
    return '' if valor is None else str(valor)


def _item_canaleta_para_rascunho(item):
    def _dimensao(campo):
        valor = getattr(item, campo)
        if valor is None:
            return '', True
        return str(valor), False

    dimensao = {}
    for campo in (
        'largura_inicial', 'largura_final', 'altura_inicial', 'altura_final', 'comprimento',
    ):
        valor, nao_identificado = _dimensao(campo)
        dimensao[campo] = valor
        dimensao[f'{campo}_nao_identificado'] = nao_identificado
    for campo in ('km_poste_inicial', 'km_poste_final'):
        valor = getattr(item, campo)
        dimensao[campo] = valor or ''
        dimensao[f'{campo}_nao_identificado'] = valor is None

    return {
        'anomalias': [a.anomalia for a in item.anomalias.all()],
        'grau_criticidade': item.grau_criticidade,
        'justificativa': item.justificativa or '',
        'necessita_cautela': 'sim' if item.necessita_cautela else 'nao',
        'lados': [lado.lado for lado in item.lados.all()],
        'dimensao': dimensao,
    }


def montar_rascunho(rad):
    """
    Devolve o RAD no MESMO formato do rascunho do formulario de
    preenchimento (rad_form.js::criarRascunhoVazio) -- e o que permite
    reaproveitar o formulario inteiro na tela de edicao: ele carrega
    isto como se fosse um rascunho salvo.
    """
    return {
        'numero_os': rad.numero_os,
        'numero_sa': rad.numero_sa,
        'solicitante_sa': rad.solicitante_sa or '',
        'data_preenchimento': _data(rad.data_preenchimento),
        'data_atividade': _data(rad.data_atividade),
        'id_local_inicial': rad.local_inicial.sigla,
        'id_local_final': rad.local_final.sigla,
        'linhas': [r.linha_id for r in rad.linhas.all()],
        'vias': [r.via_id for r in rad.vias.all()],
        'equipes': [r.equipe_id for r in rad.equipes.all()],
        'km_poste_inicial': rad.km_poste_inicial or '',
        'km_poste_final': rad.km_poste_final or '',
        'tipo_veiculo': rad.tipo_veiculo or '',
        'operador': rad.operador or '',
        'id_tipo_manutencao': rad.tipo_manutencao_id,
        'numero_falha': rad.numero_falha,
        'hora_prog_inicio': _hora(rad.hora_prog_inicio),
        'data_hp_inicio': _data(rad.data_hp_inicio),
        'hora_prog_termino': _hora(rad.hora_prog_termino),
        'data_hp_termino': _data(rad.data_hp_termino),
        'hora_real_inicio': _hora(rad.hora_real_inicio),
        'data_hr_inicio': _data(rad.data_hr_inicio),
        'hora_real_termino': _hora(rad.hora_real_termino),
        'data_hr_termino': _data(rad.data_hr_termino),
        'id_motivo_atraso_termino': rad.motivo_atraso_termino_id,
        'desc_motivo_atraso_termino': rad.desc_motivo_atraso_termino or '',
        'servicos': [r.servico_id for r in rad.servicos.all()],
        'outros_servico_desc': rad.outros_servico_desc or '',
        'desc_foto_1': rad.desc_foto_1 or '',
        'desc_foto_2': rad.desc_foto_2 or '',
        'desc_foto_3': rad.desc_foto_3 or '',
        'desc_foto_4': rad.desc_foto_4 or '',
        'terceiros_num_encarregados': _numero_terceiros(rad.terceiros_num_encarregados),
        'terceiros_num_op_maquina': _numero_terceiros(rad.terceiros_num_op_maquina),
        'terceiros_num_ajudantes': _numero_terceiros(rad.terceiros_num_ajudantes),
        'terceiros_num_motorista': _numero_terceiros(rad.terceiros_num_motorista),
        'terceiros_volume': _numero_terceiros(rad.terceiros_volume),
        'amv_blocos': [
            {
                'id_mch': amv.mch_id,
                'tipos_defeito': [d.tipo_defeito_id for d in amv.defeitos.all()],
                'acoes': [a.acao_id for a in amv.acoes.all()],
                'desc_outros_tipo_defeito': amv.desc_outros_tipo_defeito or '',
                'desc_outros_acao': amv.desc_outros_acao or '',
                'mch_nao_cadastrada': amv.mch_nao_cadastrada,
                'desc_mch_nao_cadastrada': amv.desc_mch_nao_cadastrada or '',
            }
            for amv in rad.amv_blocos.all()
        ],
        'canaleta_itens': [_item_canaleta_para_rascunho(i) for i in rad.canaleta_itens.all()],
        'colaboradores': [
            {'registro_empresa': c.registro_empresa, 'nome': c.nome, 'tipo': c.tipo}
            for c in rad.colaboradores.all()
        ],
        'responsavel_atividade': rad.responsavel_atividade or '',
        'operador_ccm_abertura_nome': rad.operador_ccm_abertura_nome or '',
        'operador_ccm_abertura_hora': _hora(rad.operador_ccm_abertura_hora),
        'operador_ccm_entrega_nome': rad.operador_ccm_entrega_nome or '',
        'operador_ccm_entrega_hora': _hora(rad.operador_ccm_entrega_hora),
        'descricao_tecnica_atividade': rad.descricao_tecnica_atividade or '',
        'materiais_utilizados': rad.materiais_utilizados or '',
        'observacoes_gerais': rad.observacoes_gerais or '',
        'sync_id_tentativa': rad.sync_id_tentativa,
    }


def carregar_rad_para_edicao(numero_rad):
    """Busca o RAD com tudo que montar_rascunho/snapshot_legivel precisam."""
    try:
        return Rad.objects.select_related(
            'local_inicial', 'local_final', 'tipo_manutencao', 'motivo_atraso_termino',
        ).prefetch_related(
            'linhas', 'vias__via', 'equipes', 'servicos__servico', 'colaboradores',
            'amv_blocos__mch', 'amv_blocos__defeitos__tipo_defeito', 'amv_blocos__acoes__acao',
            'canaleta_itens__anomalias', 'canaleta_itens__lados', 'anexos',
        ).get(numero_rad=numero_rad)
    except Rad.DoesNotExist:
        raise RadNaoEncontradoError(numero_rad)


# ---------------------------------------------------------------------------
# Snapshot legivel (para o antes/depois do historico)
# ---------------------------------------------------------------------------

def _lista(itens):
    return sorted(str(i) for i in itens)


def _texto_amv(amv):
    if amv.mch_nao_cadastrada:
        ident = f'MCH não cadastrada: {amv.desc_mch_nao_cadastrada or "-"}'
    else:
        ident = f'MCH {amv.mch.identificacao if amv.mch else "-"}'
    defeitos = ', '.join(_lista(d.tipo_defeito.nome for d in amv.defeitos.all())) or '-'
    acoes = ', '.join(_lista(a.acao.nome for a in amv.acoes.all())) or '-'
    partes = [ident, f'defeitos: {defeitos}', f'ações: {acoes}']
    if amv.desc_outros_tipo_defeito:
        partes.append(f'outros defeito: {amv.desc_outros_tipo_defeito}')
    if amv.desc_outros_acao:
        partes.append(f'outros ação: {amv.desc_outros_acao}')
    return ' | '.join(partes)


def _texto_canaleta(item):
    def _v(valor):
        return '-' if valor is None else str(valor)

    return ' | '.join([
        f'criticidade: {item.grau_criticidade}',
        f'cautela: {"sim" if item.necessita_cautela else "não"}',
        f'anomalias: {", ".join(_lista(a.anomalia for a in item.anomalias.all())) or "-"}',
        f'lados: {", ".join(_lista(l.lado for l in item.lados.all())) or "-"}',
        f'justificativa: {item.justificativa or "-"}',
        'dimensões: ' + '/'.join(_v(getattr(item, c)) for c in (
            'largura_inicial', 'largura_final', 'altura_inicial', 'altura_final', 'comprimento',
            'km_poste_inicial', 'km_poste_final',
        )),
    ])


def snapshot_legivel(rad):
    """
    Foto do RAD em texto legivel, chave = rotulo mostrado no historico.
    Valores sao texto, ou lista de textos nos campos de selecao multipla.
    Dois snapshots (antes/depois) comparados campo a campo dao a lista
    de alteracoes.
    """
    def _t(valor):
        return None if valor in (None, '') else str(valor)

    return {
        'OS': _t(rad.numero_os),
        'Nº de execução': _t(rad.numero_execucao),
        'SA': _t(rad.numero_sa),
        'Solicitante da SA': _t(rad.solicitante_sa),
        'Data de preenchimento': _t(rad.data_preenchimento),
        'Data da atividade': _t(rad.data_atividade),
        'Local inicial': rad.local_inicial.sigla,
        'Local final': rad.local_final.sigla,
        'Km/Poste inicial': _t(rad.km_poste_inicial),
        'Km/Poste final': _t(rad.km_poste_final),
        'Tipo de veículo': _t(rad.tipo_veiculo),
        'Operador': _t(rad.operador),
        'Tipo de manutenção': rad.tipo_manutencao.nome,
        'Nº da falha': _t(rad.numero_falha),
        'Hora programada início': _t(_hora(rad.hora_prog_inicio)),
        'Data programada início': _t(rad.data_hp_inicio),
        'Hora programada término': _t(_hora(rad.hora_prog_termino)),
        'Data programada término': _t(rad.data_hp_termino),
        'Hora real início': _t(_hora(rad.hora_real_inicio)),
        'Data real início': _t(rad.data_hr_inicio),
        'Hora real término': _t(_hora(rad.hora_real_termino)),
        'Data real término': _t(rad.data_hr_termino),
        'Motivo do atraso (término)': rad.motivo_atraso_termino.nome if rad.motivo_atraso_termino else None,
        'Descrição do atraso (término)': _t(rad.desc_motivo_atraso_termino),
        'Linhas': _lista(r.linha_id for r in rad.linhas.all()),
        'Vias': _lista(r.via.nome for r in rad.vias.all()),
        'Equipes': _lista(r.equipe_id for r in rad.equipes.all()),
        'Serviços': _lista(r.servico.nome for r in rad.servicos.all()),
        'Descrição de "Outros" serviço': _t(rad.outros_servico_desc),
        'Comentário foto 1': _t(rad.desc_foto_1),
        'Comentário foto 2': _t(rad.desc_foto_2),
        'Comentário foto 3': _t(rad.desc_foto_3),
        'Comentário foto 4': _t(rad.desc_foto_4),
        'Terceiros - encarregados': _t(rad.terceiros_num_encarregados),
        'Terceiros - op. máquina': _t(rad.terceiros_num_op_maquina),
        'Terceiros - ajudantes': _t(rad.terceiros_num_ajudantes),
        'Terceiros - motorista': _t(rad.terceiros_num_motorista),
        'Terceiros - volume': _t(rad.terceiros_volume),
        'Blocos AMV': [_texto_amv(a) for a in rad.amv_blocos.all()],
        'Anomalias observadas': [_texto_canaleta(i) for i in rad.canaleta_itens.all()],
        'Colaboradores': _lista(
            f'{c.nome} ({c.registro_empresa or c.get_tipo_display()})' for c in rad.colaboradores.all()
        ),
        'Responsável pela atividade': _t(rad.responsavel_atividade),
        'Operador CCM abertura - nome': _t(rad.operador_ccm_abertura_nome),
        'Operador CCM abertura - hora': _t(_hora(rad.operador_ccm_abertura_hora)),
        'Operador CCM entrega - nome': _t(rad.operador_ccm_entrega_nome),
        'Operador CCM entrega - hora': _t(_hora(rad.operador_ccm_entrega_hora)),
        'Descrição técnica': _t(rad.descricao_tecnica_atividade),
        'Materiais utilizados': _t(rad.materiais_utilizados),
        'Observações gerais': _t(rad.observacoes_gerais),
    }


def comparar_snapshots(antes, depois):
    """Lista [{campo, antes, depois}] so com o que mudou, na ordem do snapshot."""
    return [
        {'campo': campo, 'antes': antes[campo], 'depois': depois[campo]}
        for campo in antes
        if antes[campo] != depois[campo]
    ]


# ---------------------------------------------------------------------------
# Validacao de fotos na edicao
# ---------------------------------------------------------------------------

def _validar_fotos_da_edicao(rad, ids_ocultar, fotos_intervencao, fotos_acao, pdfs, payload):
    """
    Devolve (erros, anexos_a_ocultar). Considera as fotos que JA existem
    (e continuam visiveis) + as novas: os limites por categoria e a
    exigencia de ao menos 1 foto valem para o resultado FINAL.
    """
    from django.conf import settings

    erros = []
    visiveis = list(rad.anexos.all())  # manager padrao: so os nao ocultos
    por_id = {a.id: a for a in visiveis}

    a_ocultar = []
    for id_anexo in ids_ocultar:
        anexo = por_id.get(id_anexo)
        if anexo is None:
            erros.append(_erro('EDT-005', 'ocultar_anexos', f'Anexo {id_anexo} não encontrado neste RAD.'))
        elif anexo not in a_ocultar:
            a_ocultar.append(anexo)

    restantes = [a for a in visiveis if a not in a_ocultar]
    fotos_int_restantes = [a for a in restantes if a.categoria_foto == RadAnexo.INTERVENCAO_VERIFICADA]
    fotos_acao_restantes = [a for a in restantes if a.categoria_foto == RadAnexo.ACAO_REALIZADA]
    pdfs_restantes = [a for a in restantes if a.tipo_arquivo == RadAnexo.PDF]

    limite_intervencao, limite_acao = _limites_de_foto_do_payload(payload)

    grupos = (
        (fotos_intervencao, fotos_int_restantes, limite_intervencao,
         'fotos_intervencao_verificada', 'Intervenção verificada'),
        (fotos_acao, fotos_acao_restantes, limite_acao,
         'fotos_acao_realizada', 'Ação realizada'),
    )
    for novas, existentes, limite, campo, rotulo in grupos:
        if len(existentes) + len(novas) > limite:
            erros.append(_erro(
                'ANX-003', campo,
                f'No máximo {limite} fotos de "{rotulo}" são permitidas por RAD '
                f'(já há {len(existentes)} mantida(s) e {len(novas)} nova(s)).',
            ))
        for foto in novas:
            erro = _validar_foto_individual(foto, campo)
            if erro:
                erros.append(erro)

    limite_pdf = getattr(settings, 'LIMITE_PDF_POR_RAD', 1)
    if len(pdfs_restantes) + len(pdfs) > limite_pdf:
        erros.append(_erro('ANX-004', 'pdf', 'No máximo 1 PDF é permitido por RAD.'))
    for pdf in pdfs:
        erro = _validar_pdf_individual(pdf)
        if erro:
            erros.append(erro)

    if len(fotos_int_restantes) + len(fotos_acao_restantes) + len(fotos_intervencao) + len(fotos_acao) == 0:
        erros.append(_erro(
            'VLD-032', 'fotos_intervencao_verificada',
            'O RAD precisa ficar com ao menos 1 foto (Intervenção verificada ou Ação realizada).',
        ))

    return erros, a_ocultar


def _descricao_anexo(anexo):
    categoria = anexo.get_categoria_foto_display() if anexo.categoria_foto else 'PDF'
    return f'{anexo.nome_original} ({categoria})'


# ---------------------------------------------------------------------------
# Edicao propriamente dita
# ---------------------------------------------------------------------------

@transaction.atomic
def editar_rad(
    numero_rad, payload, usuario, motivo,
    ids_ocultar=None, fotos_intervencao=None, fotos_acao=None, pdfs=None,
):
    """
    Aplica a edicao do Administrador. `payload` ja vem normalizado
    (datas como date, ver rad/views.py::_normalizar_payload).

    Retorna (rad, erros, alteracoes):
    - erros nao vazio  -> nada foi gravado (nem arquivo, nem banco);
    - erros vazio      -> rad atualizado, `alteracoes` = lista do que mudou.

    Levanta RadNaoEncontradoError / RadCanceladoError (a view traduz
    para 404 / 409).
    """
    fotos_intervencao = fotos_intervencao or []
    fotos_acao = fotos_acao or []
    pdfs = pdfs or []
    ids_ocultar = list(ids_ocultar or [])

    # select_for_update: duas edicoes simultaneas do mesmo RAD esperam uma
    # pela outra em vez de se atropelarem.
    try:
        Rad.objects.select_for_update().get(numero_rad=numero_rad)
    except Rad.DoesNotExist:
        raise RadNaoEncontradoError(numero_rad)
    rad = carregar_rad_para_edicao(numero_rad)

    if rad.status == Rad.CANCELADO:
        raise RadCanceladoError(numero_rad)

    erros = []
    motivo = (motivo or '').strip()
    if not motivo:
        erros.append(_erro('EDT-001', 'motivo_edicao', 'Informe o motivo da edição.'))

    horarios = _preparar_horarios(payload)
    tipo_manutencao = None
    if payload.get('id_tipo_manutencao'):
        tipo_manutencao = CatTipoManutencao.objects.filter(id=payload['id_tipo_manutencao']).first()

    payload_validacao = {
        **payload,
        **horarios,
        '_tipo_manutencao_e_falha': bool(tipo_manutencao and tipo_manutencao.nome == 'Falha'),
        '_tipo_manutencao_e_vpm001': bool(tipo_manutencao and tipo_manutencao.nome == 'VPM001'),
    }
    erros += validar_payload_sincronizacao(payload_validacao, hoje=timezone.localdate())

    erros_fotos, anexos_a_ocultar = _validar_fotos_da_edicao(
        rad, ids_ocultar, fotos_intervencao, fotos_acao, pdfs, payload
    )
    erros += erros_fotos
    if erros:
        return None, erros, []

    antes = snapshot_legivel(rad)
    anexos_antes = _lista(_descricao_anexo(a) for a in rad.anexos.all())
    os_antiga = rad.numero_os

    dados = montar_dados_rad(payload, horarios, tipo_manutencao)
    nova_os = dados['numero_os']
    if nova_os != os_antiga:
        _travar_os(nova_os)
        dados['numero_execucao'] = proxima_execucao_da_os(nova_os, excluindo_id_rad=rad.id_rad)

    for campo, valor in dados.items():
        setattr(rad, campo, valor)

    # Selecao multipla e blocos repetiveis: apaga e recria a partir do
    # payload (mesma funcao de um RAD novo). O cascade leva junto
    # defeitos/acoes do AMV e anomalias/lados da canaleta.
    rad.linhas.all().delete()
    rad.vias.all().delete()
    rad.servicos.all().delete()
    rad.equipes.all().delete()
    rad.colaboradores.all().delete()
    rad.amv_blocos.all().delete()
    rad.canaleta_itens.all().delete()
    _criar_relacionamentos(rad, payload)

    agora = timezone.now()
    rad.data_ultima_edicao = agora
    rad.save()

    rad_atualizado = carregar_rad_para_edicao(numero_rad)
    depois = snapshot_legivel(rad_atualizado)
    alteracoes = comparar_snapshots(antes, depois)

    for anexo in anexos_a_ocultar:
        anexo.oculto = True
        anexo.ocultado_por = usuario
        anexo.data_ocultacao = agora
        anexo.save(update_fields=['oculto', 'ocultado_por', 'data_ocultacao'])

    if fotos_intervencao or fotos_acao or pdfs:
        _salvar_anexos(rad_atualizado, fotos_intervencao, fotos_acao, pdfs)

    anexos_depois = _lista(
        _descricao_anexo(a) for a in RadAnexo.objects.filter(rad=rad_atualizado)
    )
    if anexos_antes != anexos_depois:
        alteracoes.append({'campo': 'Anexos', 'antes': anexos_antes, 'depois': anexos_depois})

    if not alteracoes:
        # Nada mudou de verdade: desfaz tudo (inclusive data_ultima_edicao,
        # para nao marcar Drive/planilha como desatualizados a toa).
        transaction.set_rollback(True)
        return None, [_erro('EDT-002', 'motivo_edicao', 'Nenhuma alteração foi feita no RAD.')], []

    RadEdicao.objects.create(
        rad=rad_atualizado, usuario=usuario, data=agora, motivo=motivo, alteracoes=alteracoes,
    )
    return rad_atualizado, [], alteracoes
