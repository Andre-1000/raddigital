"""
Testes de rad/regras_horario.py — RG-HOR-001 a RG-HOR-027.
"""
from datetime import date, time

from rad.regras_horario import (
    TOLERANCIA_ATRASO_INICIO_MIN,
    ajustar_data_por_virada_de_meia_noite,
    calcular_atraso_inicio,
    calcular_atraso_termino,
    calcular_duracao_minutos,
    montar_datetime,
    processar_horarios,
)


class TestAjusteViradaMeiaNoite:
    def test_sem_virada_quando_termino_maior_que_inicio(self):
        data = date(2026, 6, 15)
        resultado = ajustar_data_por_virada_de_meia_noite(data, time(8, 0), time(12, 0))
        assert resultado == data

    def test_com_virada_quando_termino_menor_que_inicio(self):
        """RG-HOR-021/022: hora_termino < hora_inicio -> +1 dia."""
        data = date(2026, 6, 15)
        resultado = ajustar_data_por_virada_de_meia_noite(data, time(22, 0), time(2, 0))
        assert resultado == date(2026, 6, 16)

    def test_horarios_iguais_nao_e_virada(self):
        data = date(2026, 6, 15)
        resultado = ajustar_data_por_virada_de_meia_noite(data, time(8, 0), time(8, 0))
        assert resultado == data


class TestCalculoDuracao:
    def test_duracao_simples_no_mesmo_dia(self):
        inicio = montar_datetime(date(2026, 6, 15), time(8, 0))
        termino = montar_datetime(date(2026, 6, 15), time(12, 0))
        assert calcular_duracao_minutos(inicio, termino) == 240  # 4h00

    def test_exemplo_oficial_da_efd_virada_meia_noite(self):
        """
        Exemplo da EFD (secao 3.4): 15/06/2026 22:00 -> 16/06/2026 02:00
        deve resultar em 4h00 (240 minutos), nao um valor negativo.
        """
        data_inicio = date(2026, 6, 15)
        hora_inicio = time(22, 0)
        hora_termino = time(2, 0)

        data_termino = ajustar_data_por_virada_de_meia_noite(
            data_inicio, hora_inicio, hora_termino
        )
        inicio = montar_datetime(data_inicio, hora_inicio)
        termino = montar_datetime(data_termino, hora_termino)

        assert data_termino == date(2026, 6, 16)
        assert calcular_duracao_minutos(inicio, termino) == 240


class TestAtrasoInicio:
    def test_sem_atraso_dentro_da_tolerancia(self):
        prog = montar_datetime(date(2026, 6, 15), time(8, 0))
        real = montar_datetime(date(2026, 6, 15), time(8, 10))  # exatos 10 min
        assert calcular_atraso_inicio(prog, real) is False

    def test_atraso_um_minuto_alem_da_tolerancia(self):
        prog = montar_datetime(date(2026, 6, 15), time(8, 0))
        real = montar_datetime(date(2026, 6, 15), time(8, 11))
        assert calcular_atraso_inicio(prog, real) is True

    def test_chegada_adiantada_nao_e_atraso(self):
        prog = montar_datetime(date(2026, 6, 15), time(8, 0))
        real = montar_datetime(date(2026, 6, 15), time(7, 50))
        assert calcular_atraso_inicio(prog, real) is False

    def test_tolerancia_padrao_e_10_minutos(self):
        assert TOLERANCIA_ATRASO_INICIO_MIN == 10


class TestAtrasoTermino:
    def test_sem_tolerancia_um_minuto_ja_e_atraso(self):
        """RG-HOR-011: para o termino nao ha tolerancia operacional."""
        prog = montar_datetime(date(2026, 6, 15), time(12, 0))
        real = montar_datetime(date(2026, 6, 15), time(12, 1))
        assert calcular_atraso_termino(prog, real) is True

    def test_termino_no_horario_exato_nao_e_atraso(self):
        prog = montar_datetime(date(2026, 6, 15), time(12, 0))
        real = montar_datetime(date(2026, 6, 15), time(12, 0))
        assert calcular_atraso_termino(prog, real) is False

    def test_termino_adiantado_nao_e_atraso(self):
        prog = montar_datetime(date(2026, 6, 15), time(12, 0))
        real = montar_datetime(date(2026, 6, 15), time(11, 50))
        assert calcular_atraso_termino(prog, real) is False


class TestProcessarHorarios:
    def test_caso_completo_sem_virada_sem_atraso(self):
        resultado = processar_horarios(
            data_preenchimento=date(2026, 6, 15),
            hora_prog_inicio=time(8, 0),
            hora_prog_termino=time(12, 0),
            hora_real_inicio=time(8, 0),
            hora_real_termino=time(12, 0),
            tipo_manutencao_e_falha=False,
        )
        assert resultado['duracao_programada_min'] == 240
        assert resultado['duracao_real_min'] == 240
        assert resultado['atraso_inicio'] is False
        assert resultado['atraso_termino'] is False
        assert resultado['data_hp_termino'] == date(2026, 6, 15)

    def test_caso_com_virada_de_meia_noite_e_atraso(self):
        resultado = processar_horarios(
            data_preenchimento=date(2026, 6, 15),
            hora_prog_inicio=time(22, 0),
            hora_prog_termino=time(2, 0),
            hora_real_inicio=time(22, 20),  # 20 min de atraso no inicio
            hora_real_termino=time(2, 30),  # atraso no termino tambem
            tipo_manutencao_e_falha=False,
        )
        assert resultado['data_hp_termino'] == date(2026, 6, 16)
        assert resultado['data_hr_termino'] == date(2026, 6, 16)
        assert resultado['duracao_programada_min'] == 240
        assert resultado['duracao_real_min'] == 250
        assert resultado['atraso_inicio'] is True
        assert resultado['atraso_termino'] is True

    def test_tipo_falha_desliga_controles_de_atraso(self):
        """RG-HOR-006/007/019: com Tipo de Manutencao = Falha, atrasos ficam False."""
        resultado = processar_horarios(
            data_preenchimento=date(2026, 6, 15),
            hora_prog_inicio=time(8, 0),
            hora_prog_termino=time(12, 0),
            hora_real_inicio=time(9, 0),  # 1h de atraso real
            hora_real_termino=time(13, 0),
            tipo_manutencao_e_falha=True,
        )
        assert resultado['atraso_inicio'] is False
        assert resultado['atraso_termino'] is False
        # Duracoes continuam sendo calculadas normalmente (RG-HOR-004/005
        # nao dependem do tipo de manutencao)
        assert resultado['duracao_real_min'] == 240

    def test_datas_editadas_manualmente_sao_preservadas(self):
        """
        Quando o usuario ja editou data_hp_termino/data_hr_termino
        manualmente, a funcao nao deve sobrescrever com o calculo
        automatico de virada (RG-HOR-022: usuario pode editar o
        resultado).
        """
        resultado = processar_horarios(
            data_preenchimento=date(2026, 6, 15),
            hora_prog_inicio=time(22, 0),
            hora_prog_termino=time(2, 0),
            hora_real_inicio=time(22, 0),
            hora_real_termino=time(2, 0),
            tipo_manutencao_e_falha=False,
            data_hp_termino=date(2026, 6, 20),  # editado manualmente
        )
        assert resultado['data_hp_termino'] == date(2026, 6, 20)
