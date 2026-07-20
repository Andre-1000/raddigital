"""
Parsing de data/hora vindos de requisicoes HTTP (JSON/querystring), em
um unico lugar.

Por que este modulo existe: o mesmo bug (DateTimeField recebendo
datetime "naive" com USE_TZ=True) apareceu de forma independente em
rad/regras_negocio.py e consulta/views.py, porque cada arquivo
reimplementava seu proprio parsing. A causa raiz nao era "esquecer
make_aware" uma vez -- era nao ter um unico ponto de conversao. Este
modulo e esse ponto unico; todo o codigo do projeto que precisa
transformar string -> date/time/datetime deve importar daqui, nunca
reimplementar.

Ver tambem pytest.ini: o warning do Django para datetime naive esta
configurado como erro, entao qualquer regressao futura (nova view que
volte a montar datetime "na mao") quebra a suite imediatamente, em vez
de so imprimir um aviso que passa despercebido.
"""
from datetime import datetime, time

from django.utils import timezone as django_timezone


def parse_data(valor):
    """'YYYY-MM-DD' -> datetime.date. Aceita None/vazio -> None."""
    if not valor:
        return None
    return datetime.strptime(valor, '%Y-%m-%d').date()


def parse_hora(valor):
    """'HH:MM' -> datetime.time. Aceita None/vazio -> None."""
    if not valor:
        return None
    horas, minutos = valor.split(':')
    return time(int(horas), int(minutos))


def parse_datetime_aware(valor, formato='%Y-%m-%dT%H:%M'):
    """
    String -> datetime.datetime timezone-aware (America/Sao_Paulo, via
    USE_TZ=True). Aceita None/vazio -> None. Este e o UNICO lugar do
    projeto que deve chamar make_aware -- todo outro codigo que precisa
    de um datetime aware a partir de uma string deve passar por aqui.
    """
    if not valor:
        return None
    ingenuo = datetime.strptime(valor, formato)
    return montar_datetime_aware(ingenuo.date(), ingenuo.time())


def montar_datetime_aware(data_ref, hora_ref):
    """
    date + time -> datetime timezone-aware. Usado para converter a
    saida "naive" de rad.regras_horario.montar_datetime (funcao pura,
    sem dependencia do Django) para o formato que os DateTimeField do
    Django exigem quando USE_TZ=True.
    """
    ingenuo = datetime.combine(data_ref, hora_ref)
    return django_timezone.make_aware(ingenuo)


def tornar_aware(datetime_ingenuo):
    """
    datetime "naive" -> timezone-aware. Mesmo make_aware do Django, mas
    centralizado aqui para que nenhum outro arquivo do projeto precise
    importar django.utils.timezone diretamente so para isso.
    """
    if datetime_ingenuo is None:
        return None
    return django_timezone.make_aware(datetime_ingenuo)
