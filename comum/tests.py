"""
Testes de comum/datas.py.

Ponto central de conversao string -> date/time/datetime. Testado
isoladamente para que qualquer novo uso no projeto possa confiar nele
sem reescrever a logica.
"""
from datetime import date, time

import pytest

from comum.datas import montar_datetime_aware, parse_data, parse_datetime_aware, parse_hora, tornar_aware


class TestParseData:
    def test_converte_string_para_date(self):
        assert parse_data('2026-06-15') == date(2026, 6, 15)

    def test_vazio_retorna_none(self):
        assert parse_data('') is None
        assert parse_data(None) is None


class TestParseHora:
    def test_converte_string_para_time(self):
        assert parse_hora('08:30') == time(8, 30)

    def test_vazio_retorna_none(self):
        assert parse_hora('') is None
        assert parse_hora(None) is None


@pytest.mark.django_db
class TestDatetimeAware:
    def test_parse_datetime_aware_e_timezone_aware(self):
        """
        Se esta funcao regredir para devolver datetime "naive", QUALQUER
        teste do projeto que grave um Rad usando este valor vai falhar
        -- pytest.ini transforma o RuntimeWarning do Django (naive
        datetime com USE_TZ=True) em erro. Esta e a garantia permanente
        contra a reintroducao do bug, nao apenas este teste isolado.
        """
        resultado = parse_datetime_aware('2026-06-15T08:00')
        assert resultado.tzinfo is not None

    def test_parse_datetime_aware_vazio_retorna_none(self):
        assert parse_datetime_aware('') is None
        assert parse_datetime_aware(None) is None

    def test_montar_datetime_aware_e_timezone_aware(self):
        resultado = montar_datetime_aware(date(2026, 6, 15), time(8, 0))
        assert resultado.tzinfo is not None
        assert resultado.year == 2026 and resultado.hour == 8

    def test_tornar_aware_converte_naive_para_aware(self):
        from datetime import datetime as dt_cls

        naive = dt_cls(2026, 6, 15, 8, 0)
        resultado = tornar_aware(naive)
        assert resultado.tzinfo is not None

    def test_tornar_aware_aceita_none(self):
        assert tornar_aware(None) is None
