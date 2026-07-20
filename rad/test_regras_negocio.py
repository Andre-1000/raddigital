"""
Testes das regras de negocio criticas (rad/regras_negocio.py).

O teste de concorrencia usa threads reais com conexoes de banco
independentes e transaction=True para provar RG-IDENT-009 contra o
PostgreSQL de verdade -- nao e uma simulacao.
"""
import threading
from datetime import date, datetime, time

import pytest
from django.db import connection
from django.utils import timezone

from catalogos.models import CatLocal, CatTipoManutencao
from rad.models import Rad
from rad.regras_negocio import (
    gerar_numero_execucao,
    gerar_numero_rad,
    sincronizar_rad,
)
from usuarios.models import Usuario


def _dados_rad_base(usuario, local, tipo_manutencao, numero_os, sync_id):
    agora = timezone.now()
    return dict(
        numero_os=numero_os,
        data_preenchimento=date(2026, 6, 15),
        local_inicial=local,
        local_final=local,
        tipo_manutencao=tipo_manutencao,
        hora_prog_inicio=time(8, 0),
        data_hp_inicio=date(2026, 6, 15),
        hora_prog_termino=time(12, 0),
        data_hp_termino=date(2026, 6, 15),
        hora_real_inicio=time(8, 0),
        data_hr_inicio=date(2026, 6, 15),
        hora_real_termino=time(12, 0),
        data_hr_termino=date(2026, 6, 15),
        data_hora_prog_inicio=datetime(2026, 6, 15, 8, 0, tzinfo=agora.tzinfo),
        data_hora_prog_termino=datetime(2026, 6, 15, 12, 0, tzinfo=agora.tzinfo),
        data_hora_real_inicio=datetime(2026, 6, 15, 8, 0, tzinfo=agora.tzinfo),
        data_hora_real_termino=datetime(2026, 6, 15, 12, 0, tzinfo=agora.tzinfo),
        duracao_programada_min=240,
        duracao_real_min=240,
        usuario=usuario,
        data_sincronizacao=agora,
        sync_id_tentativa=sync_id,
    )


@pytest.mark.django_db
class TestGeracaoNumeroExecucao:
    def test_primeira_execucao_da_sa_recebe_numero_1(self):
        assert gerar_numero_execucao(numero_os=9999) == 1

    def test_numero_rad_segue_formato_r00001(self):
        numero = gerar_numero_rad()
        assert numero.startswith('R')
        assert len(numero) == 6
        assert numero[1:].isdigit()

    def test_numeros_rad_sucessivos_sao_diferentes(self):
        assert gerar_numero_rad() != gerar_numero_rad()


@pytest.mark.django_db
class TestSincronizarRad:
    def test_sincronizacao_gera_numero_execucao_sequencial_por_sa(
        self,
    ):
        usuario = Usuario.objects.create(login='tec.seq')
        local = CatLocal.objects.create(sigla='BAS', nome='Bras', categoria='estacao')
        tipo = CatTipoManutencao.objects.create(nome='Preventiva')

        rad1, criado1 = sincronizar_rad(
            _dados_rad_base(usuario, local, tipo, numero_os=5000, sync_id='seq-1')
        )
        rad2, criado2 = sincronizar_rad(
            _dados_rad_base(usuario, local, tipo, numero_os=5000, sync_id='seq-2')
        )
        rad3, criado3 = sincronizar_rad(
            # SA diferente -> deve comecar do 1 de novo (RG-IDENT-005)
            _dados_rad_base(usuario, local, tipo, numero_os=5001, sync_id='seq-3')
        )

        assert (criado1, criado2, criado3) == (True, True, True)
        assert rad1.numero_execucao == 1
        assert rad2.numero_execucao == 2
        assert rad3.numero_execucao == 1

    def test_reenvio_com_mesmo_sync_id_e_idempotente(self):
        """PADROES_E_DIRETRIZES 5.2: reenvio nao cria RAD duplicado."""
        usuario = Usuario.objects.create(login='tec.idemp')
        local = CatLocal.objects.create(sigla='TAT', nome='Tatuape', categoria='estacao')
        tipo = CatTipoManutencao.objects.create(nome='Corretiva')

        dados = _dados_rad_base(usuario, local, tipo, numero_os=6000, sync_id='mesmo-id')

        rad1, criado1 = sincronizar_rad(dados)
        rad2, criado2 = sincronizar_rad(dados)

        assert criado1 is True
        assert criado2 is False
        assert rad1.pk == rad2.pk
        assert Rad.objects.filter(sync_id_tentativa='mesmo-id').count() == 1


@pytest.mark.django_db(transaction=True)
class TestConcorrenciaNumeroExecucao:
    def test_rg_ident_009_dois_rads_simultaneos_da_mesma_sa_nao_colidem(self):
        """
        Prova RG-IDENT-009: dois RADs da mesma SA sincronizados ao mesmo
        tempo por usuarios diferentes devem receber numeros de execucao
        DIFERENTES. Usa threads com conexoes reais de banco e
        sincronizacao por barreira para maximizar a chance de corrida
        caso o lock nao funcione.
        """
        usuario = Usuario.objects.create(login='tec.concorrencia')
        local = CatLocal.objects.create(
            sigla='ITQ', nome='Itaquera', categoria='estacao'
        )
        tipo = CatTipoManutencao.objects.create(nome='Preditiva')

        numero_os = 7777
        n_threads = 8
        barreira = threading.Barrier(n_threads)
        resultados = []
        erros = []

        def tentar_sincronizar(indice):
            try:
                connection.close()  # forca nova conexao dedicada a esta thread
                barreira.wait()  # maximiza a chance de execucao simultanea
                dados = _dados_rad_base(
                    usuario,
                    local,
                    tipo,
                    numero_os=numero_os,
                    sync_id=f'concorrencia-{indice}',
                )
                rad, _ = sincronizar_rad(dados)
                resultados.append(rad.numero_execucao)
            except Exception as exc:  # pragma: no cover - diagnostico de falha
                erros.append(exc)
            finally:
                connection.close()

        threads = [
            threading.Thread(target=tentar_sincronizar, args=(i,))
            for i in range(n_threads)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not erros, f'Erros durante a concorrencia: {erros}'
        assert len(resultados) == n_threads
        # A prova real de RG-IDENT-009: nenhum numero de execucao repetido.
        assert sorted(resultados) == list(range(1, n_threads + 1))
