"""
Calculo de horarios do RAD: virada de meia-noite, duracoes e atrasos.

Referencia: EFD secao 3.4 (HORARIOS), regras RG-HOR-001 a RG-HOR-027.

Funcoes puras (sem acesso a banco), para serem testadas exaustivamente e
reutilizadas tanto no endpoint de sincronizacao quanto, futuramente, em
validacoes client-side espelhadas em JS (o mesmo calculo roda offline no
navegador durante o preenchimento).

Fora do escopo deste modulo (tratado na camada de view/serializer):
RG-HOR-016/017/018 — limpar motivo_atraso_* quando o atraso for
desmarcado, e nao persistir campos ocultados pela troca do Tipo de
Manutencao. Este modulo so calcula os valores; quem decide o que
gravar/limpar e a camada que orquestra o salvamento do Rad.
"""
from datetime import datetime, timedelta

TOLERANCIA_ATRASO_INICIO_MIN = 10


def ajustar_data_por_virada_de_meia_noite(data_inicio, hora_inicio, hora_termino):
    """
    RG-HOR-021/022: quando a hora de termino e menor que a hora de
    inicio, a data de termino e ajustada automaticamente para
    data_inicio + 1 dia. O usuario podera editar o resultado depois —
    esta funcao apenas calcula o valor sugerido inicial.
    """
    if hora_termino < hora_inicio:
        return data_inicio + timedelta(days=1)
    return data_inicio


def montar_datetime(data_ref, hora_ref):
    """Junta data + hora em um DateTime completo (RG-HOR-024/025)."""
    return datetime.combine(data_ref, hora_ref)


def calcular_duracao_minutos(datetime_inicio, datetime_termino):
    """RG-HOR-004/005/026/027: duracao em minutos usando DateTime completo."""
    delta = datetime_termino - datetime_inicio
    return int(delta.total_seconds() // 60)


def calcular_atraso_inicio(
    datetime_prog_inicio, datetime_real_inicio, tolerancia_min=TOLERANCIA_ATRASO_INICIO_MIN
):
    """
    RG-HOR-009/010: atraso no inicio, com tolerancia de 10 minutos.
    Diferenca igual ou inferior a tolerancia NAO conta como atraso.
    """
    diferenca_min = (datetime_real_inicio - datetime_prog_inicio).total_seconds() / 60
    return diferenca_min > tolerancia_min


def calcular_atraso_termino(datetime_prog_termino, datetime_real_termino):
    """RG-HOR-011/012: atraso no termino, sem tolerancia operacional."""
    return datetime_real_termino > datetime_prog_termino


def processar_horarios(
    *,
    data_preenchimento,
    hora_prog_inicio,
    hora_prog_termino,
    hora_real_inicio,
    hora_real_termino,
    tipo_manutencao_e_falha,
    data_hp_inicio=None,
    data_hp_termino=None,
    data_hr_inicio=None,
    data_hr_termino=None,
):
    """
    Calcula todos os campos derivados de horario de um RAD (EFD 3.4).

    Os sub-campos de data (data_hp_inicio, data_hr_inicio) sao
    preenchidos por padrao com data_preenchimento (RG conforme EFD-012 a
    EFD-015) quando nao informados explicitamente — cobrindo o caso em
    que o usuario ja os editou manualmente. As datas de termino seguem a
    mesma logica, exceto que, quando nao informadas, sao calculadas
    automaticamente considerando a virada de meia-noite.

    RG-HOR-006/007/019: quando o Tipo de Manutencao e "Falha", os
    controles de atraso permanecem desligados (ocultos na interface).

    Retorna um dict pronto para popular os campos correspondentes do
    modelo Rad.
    """
    data_hp_inicio = data_hp_inicio or data_preenchimento
    data_hr_inicio = data_hr_inicio or data_preenchimento

    data_hp_termino = data_hp_termino or ajustar_data_por_virada_de_meia_noite(
        data_hp_inicio, hora_prog_inicio, hora_prog_termino
    )
    data_hr_termino = data_hr_termino or ajustar_data_por_virada_de_meia_noite(
        data_hr_inicio, hora_real_inicio, hora_real_termino
    )

    dt_prog_inicio = montar_datetime(data_hp_inicio, hora_prog_inicio)
    dt_prog_termino = montar_datetime(data_hp_termino, hora_prog_termino)
    dt_real_inicio = montar_datetime(data_hr_inicio, hora_real_inicio)
    dt_real_termino = montar_datetime(data_hr_termino, hora_real_termino)

    duracao_programada_min = calcular_duracao_minutos(dt_prog_inicio, dt_prog_termino)
    duracao_real_min = calcular_duracao_minutos(dt_real_inicio, dt_real_termino)

    if tipo_manutencao_e_falha:
        atraso_inicio = False
        atraso_termino = False
    else:
        atraso_inicio = calcular_atraso_inicio(dt_prog_inicio, dt_real_inicio)
        atraso_termino = calcular_atraso_termino(dt_prog_termino, dt_real_termino)

    return {
        'data_hp_inicio': data_hp_inicio,
        'data_hp_termino': data_hp_termino,
        'data_hr_inicio': data_hr_inicio,
        'data_hr_termino': data_hr_termino,
        'data_hora_prog_inicio': dt_prog_inicio,
        'data_hora_prog_termino': dt_prog_termino,
        'data_hora_real_inicio': dt_real_inicio,
        'data_hora_real_termino': dt_real_termino,
        'duracao_programada_min': duracao_programada_min,
        'duracao_real_min': duracao_real_min,
        'atraso_inicio': atraso_inicio,
        'atraso_termino': atraso_termino,
    }
