"""
Testes do app rad — modelo de dados.

Cobre integridade estrutural (constraints, unicidade, relacionamentos).
A logica de negocio (geracao atomica do numero de execucao, virada de
meia-noite, calculos de duracao) e testada separadamente em
test_regras_negocio.py, junto com o servico que implementa essas regras.
"""
from datetime import date, datetime, time

import pytest
from django.db import IntegrityError
from django.utils import timezone

from catalogos.models import CatLinha, CatLocal, CatMch, CatTipoManutencao, CatVia
from rad.models import Rad, RadAmv, RadColaborador, RadLinha
from usuarios.models import Usuario


@pytest.fixture
def usuario(db):
    return Usuario.objects.create(login='tecnico.teste')


@pytest.fixture
def local_bfu(db):
    return CatLocal.objects.create(sigla='BFU', nome='Barra Funda', categoria='estacao')


@pytest.fixture
def local_luz(db):
    return CatLocal.objects.create(sigla='LUZ', nome='Luz', categoria='estacao')


@pytest.fixture
def tipo_preventiva(db):
    return CatTipoManutencao.objects.create(nome='Preventiva')


def _criar_rad(usuario, local_bfu, local_luz, tipo_preventiva, **overrides):
    """Monta um RAD valido com todos os campos obrigatorios preenchidos."""
    agora = timezone.now()
    dados = dict(
        numero_rad=overrides.pop('numero_rad', 'R00001'),
        numero_os=1234,
        numero_execucao=1,
        data_preenchimento=date(2026, 6, 15),
        local_inicial=local_bfu,
        local_final=local_luz,
        tipo_manutencao=tipo_preventiva,
        hora_prog_inicio=time(8, 0),
        data_hp_inicio=date(2026, 6, 15),
        hora_prog_termino=time(12, 0),
        data_hp_termino=date(2026, 6, 15),
        hora_real_inicio=time(8, 15),
        data_hr_inicio=date(2026, 6, 15),
        hora_real_termino=time(12, 45),
        data_hr_termino=date(2026, 6, 15),
        data_hora_prog_inicio=datetime(2026, 6, 15, 8, 0, tzinfo=agora.tzinfo),
        data_hora_prog_termino=datetime(2026, 6, 15, 12, 0, tzinfo=agora.tzinfo),
        data_hora_real_inicio=datetime(2026, 6, 15, 8, 15, tzinfo=agora.tzinfo),
        data_hora_real_termino=datetime(2026, 6, 15, 12, 45, tzinfo=agora.tzinfo),
        duracao_programada_min=240,
        duracao_real_min=270,
        usuario=usuario,
        data_sincronizacao=agora,
        sync_id_tentativa=overrides.pop('sync_id_tentativa', 'sync-teste-0001'),
    )
    dados.update(overrides)
    return Rad.objects.create(**dados)


@pytest.mark.django_db
class TestRad:
    def test_cria_rad_valido(self, usuario, local_bfu, local_luz, tipo_preventiva):
        rad = _criar_rad(usuario, local_bfu, local_luz, tipo_preventiva)
        assert rad.pk is not None
        assert rad.status == Rad.SINCRONIZADO

    def test_numero_rad_e_unico(self, usuario, local_bfu, local_luz, tipo_preventiva):
        _criar_rad(usuario, local_bfu, local_luz, tipo_preventiva, numero_rad='R00001')
        with pytest.raises(IntegrityError):
            _criar_rad(
                usuario,
                local_bfu,
                local_luz,
                tipo_preventiva,
                numero_rad='R00001',
                sync_id_tentativa='sync-teste-0002',
            )

    def test_sync_id_tentativa_e_unico_garante_idempotencia(
        self, usuario, local_bfu, local_luz, tipo_preventiva
    ):
        """Base para a regra de idempotencia de sincronizacao."""
        _criar_rad(
            usuario,
            local_bfu,
            local_luz,
            tipo_preventiva,
            numero_rad='R00001',
            sync_id_tentativa='sync-repetido',
        )
        with pytest.raises(IntegrityError):
            _criar_rad(
                usuario,
                local_bfu,
                local_luz,
                tipo_preventiva,
                numero_rad='R00002',
                sync_id_tentativa='sync-repetido',
            )

    def test_local_inicial_e_final_podem_ser_iguais(
        self, usuario, local_bfu, tipo_preventiva
    ):
        """RG-LOC-008: local inicial e final podem ser o mesmo."""
        rad = _criar_rad(usuario, local_bfu, local_bfu, tipo_preventiva)
        assert rad.local_inicial == rad.local_final


@pytest.mark.django_db
class TestRadLinha:
    def test_nao_permite_mesma_linha_duas_vezes_no_mesmo_rad(
        self, usuario, local_bfu, local_luz, tipo_preventiva
    ):
        rad = _criar_rad(usuario, local_bfu, local_luz, tipo_preventiva)
        linha = CatLinha.objects.create(codigo='11', nome='Coral')
        RadLinha.objects.create(rad=rad, linha=linha)
        with pytest.raises(IntegrityError):
            RadLinha.objects.create(rad=rad, linha=linha)


@pytest.mark.django_db
class TestRadAmv:
    def test_maximo_um_bloco_amv_por_rad(
        self, usuario, local_bfu, local_luz, tipo_preventiva
    ):
        """id_rad UNIQUE em rad_amv garante no maximo um bloco por RAD."""
        rad = _criar_rad(usuario, local_bfu, local_luz, tipo_preventiva)
        mch = CatMch.objects.create(
            identificacao='MCH01A-BFU',
            modelo='M23-E',
            via='3',
            ur='BFU',
            local_amv='BFU',
            linha='11',
        )
        RadAmv.objects.create(
            rad=rad,
            mch=mch,
            modelo_mch=mch.modelo,
            via_mch=mch.via,
            ur_mch=mch.ur,
            local_mch=mch.local_amv,
            linha_mch=mch.linha,
        )
        with pytest.raises(IntegrityError):
            RadAmv.objects.create(
                rad=rad,
                mch=mch,
                modelo_mch=mch.modelo,
                via_mch=mch.via,
                ur_mch=mch.ur,
                local_mch=mch.local_amv,
                linha_mch=mch.linha,
            )


@pytest.mark.django_db
class TestRadAnexo:
    def test_foto_sem_categoria_e_rejeitada_pelo_banco(
        self, usuario, local_bfu, local_luz, tipo_preventiva
    ):
        """chk_rad_anexo_categoria_coerente_com_tipo: toda foto exige categoria."""
        from rad.models import RadAnexo

        rad = _criar_rad(usuario, local_bfu, local_luz, tipo_preventiva)
        with pytest.raises(IntegrityError):
            RadAnexo.objects.create(
                rad=rad,
                tipo_arquivo=RadAnexo.FOTO,
                categoria_foto=None,
                nome_original='sem_categoria.jpg',
                caminho_servidor='anexos/teste/sem_categoria.jpg',
                tamanho_bytes=1000,
                data_upload=timezone.now(),
            )

    def test_pdf_com_categoria_e_rejeitado_pelo_banco(
        self, usuario, local_bfu, local_luz, tipo_preventiva
    ):
        """PDF nao tem tema -- categoria_foto deve ser nula para tipo_arquivo=pdf."""
        from rad.models import RadAnexo

        rad = _criar_rad(usuario, local_bfu, local_luz, tipo_preventiva)
        with pytest.raises(IntegrityError):
            RadAnexo.objects.create(
                rad=rad,
                tipo_arquivo=RadAnexo.PDF,
                categoria_foto=RadAnexo.ACAO_REALIZADA,
                nome_original='documento.pdf',
                caminho_servidor='anexos/teste/documento.pdf',
                tamanho_bytes=1000,
                data_upload=timezone.now(),
            )

    def test_foto_com_categoria_e_aceita(
        self, usuario, local_bfu, local_luz, tipo_preventiva
    ):
        from rad.models import RadAnexo

        rad = _criar_rad(usuario, local_bfu, local_luz, tipo_preventiva)
        anexo = RadAnexo.objects.create(
            rad=rad,
            tipo_arquivo=RadAnexo.FOTO,
            categoria_foto=RadAnexo.INTERVENCAO_VERIFICADA,
            nome_original='com_categoria.jpg',
            caminho_servidor='anexos/teste/com_categoria.jpg',
            tamanho_bytes=1000,
            data_upload=timezone.now(),
        )
        assert anexo.pk is not None


@pytest.mark.django_db
class TestRadColaborador:
    def test_rg_resp_009_nao_permite_mesmo_colaborador_duas_vezes(
        self, usuario, local_bfu, local_luz, tipo_preventiva
    ):
        rad = _criar_rad(usuario, local_bfu, local_luz, tipo_preventiva)
        RadColaborador.objects.create(
            rad=rad, registro_empresa='12345', nome='Carlos Souza', tipo='colaborador'
        )
        with pytest.raises(IntegrityError):
            RadColaborador.objects.create(
                rad=rad,
                registro_empresa='12345',
                nome='Carlos Souza (duplicado)',
                tipo='colaborador',
            )

    def test_participantes_externos_sem_matricula_nao_sao_bloqueados(
        self, usuario, local_bfu, local_luz, tipo_preventiva
    ):
        """registro_empresa NULL (participante externo) nao entra na constraint de unicidade."""
        rad = _criar_rad(usuario, local_bfu, local_luz, tipo_preventiva)
        RadColaborador.objects.create(
            rad=rad, registro_empresa=None, nome='Visitante A', tipo='participante'
        )
        # Nao deve levantar IntegrityError mesmo com outro registro_empresa=None
        RadColaborador.objects.create(
            rad=rad, registro_empresa=None, nome='Visitante B', tipo='participante'
        )
        assert rad.colaboradores.count() == 2
