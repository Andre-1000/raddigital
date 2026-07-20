"""
Testes de rad/validadores.py — VLD-001 a VLD-022.
"""
from datetime import date, timedelta

import pytest

from catalogos.models import CatMotivoAtraso, CatServico
from rad.validadores import validar_payload_sincronizacao

HOJE = date(2026, 6, 15)


def _payload_valido_base(**overrides):
    """Payload minimo que passa em todas as validacoes, sem AMV."""
    base = {
        'numero_os': 1234,
        'numero_sa': '5678',
        'responsavel_atividade': 'Responsavel Teste',
        'data_preenchimento': HOJE,
        'id_local_inicial': 'BFU',
        'id_local_final': 'LUZ',
        'linhas': ['11'],
        'vias': [1],
        'id_tipo_manutencao': 1,
        '_tipo_manutencao_e_falha': False,
        'numero_falha': None,
        'hora_prog_inicio': '08:00',
        'hora_prog_termino': '12:00',
        'hora_real_inicio': '08:00',
        'hora_real_termino': '12:00',
        'data_hora_prog_inicio': None,
        'data_hora_prog_termino': None,
        'data_hora_real_inicio': None,
        'data_hora_real_termino': None,
        'atraso_inicio': False,
        'atraso_termino': False,
        'id_motivo_atraso_inicio': None,
        'desc_motivo_atraso_inicio': None,
        'id_motivo_atraso_termino': None,
        'desc_motivo_atraso_termino': None,
        'servicos': [1],
        'outros_servico_desc': None,
        'colaboradores': [{'registro_empresa': '111', 'nome': 'Fulano', 'tipo': 'participante'}],
        'amv': None,
    }
    base.update(overrides)
    return base


def _codigos(erros):
    return {e['codigo'] for e in erros}


@pytest.fixture
def servico_inspecao(db):
    return CatServico.objects.create(nome='Inspecao')


@pytest.fixture
def servico_outros(db):
    return CatServico.objects.create(nome='Outros', requer_descricao=True)


@pytest.fixture
def servico_amv(db):
    return CatServico.objects.create(nome='Manutencao em AMV', requer_amv=True)


@pytest.fixture
def motivo_transito(db):
    return CatMotivoAtraso.objects.create(nome='Transito')


@pytest.fixture
def motivo_outros(db):
    return CatMotivoAtraso.objects.create(nome='Outros', requer_descricao=True)


@pytest.mark.django_db
class TestPayloadValidoNaoGeraErros:
    def test_payload_completo_sem_amv_passa(self, servico_inspecao):
        payload = _payload_valido_base(servicos=[servico_inspecao.id])
        assert validar_payload_sincronizacao(payload, hoje=HOJE) == []

    def test_local_inicial_igual_final_nao_bloqueia(self, servico_inspecao):
        """VLD-025."""
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id], id_local_final='BFU'
        )
        assert validar_payload_sincronizacao(payload, hoje=HOJE) == []


@pytest.mark.django_db
class TestValidacoesBasicas:
    def test_vld_001_os_vazia(self, servico_inspecao):
        payload = _payload_valido_base(servicos=[servico_inspecao.id], numero_os=None)
        assert 'VLD-001' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_001_os_negativa(self, servico_inspecao):
        payload = _payload_valido_base(servicos=[servico_inspecao.id], numero_os=-5)
        assert 'VLD-001' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_001_os_acima_de_7_digitos(self, servico_inspecao):
        payload = _payload_valido_base(servicos=[servico_inspecao.id], numero_os=10_000_000)
        assert 'VLD-001' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_os_com_exatamente_7_digitos_e_valida(self, servico_inspecao):
        payload = _payload_valido_base(servicos=[servico_inspecao.id], numero_os=9_999_999)
        assert 'VLD-001' not in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_028_numero_sa_vazio(self, servico_inspecao):
        payload = _payload_valido_base(servicos=[servico_inspecao.id], numero_sa=None)
        assert 'VLD-028' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_028_numero_sa_nao_numerico(self, servico_inspecao):
        payload = _payload_valido_base(servicos=[servico_inspecao.id], numero_sa='ABC123')
        assert 'VLD-028' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_028_numero_sa_acima_de_10_caracteres(self, servico_inspecao):
        payload = _payload_valido_base(servicos=[servico_inspecao.id], numero_sa='12345678901')
        assert 'VLD-028' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_numero_sa_com_10_caracteres_e_valido(self, servico_inspecao):
        payload = _payload_valido_base(servicos=[servico_inspecao.id], numero_sa='1234567890')
        assert validar_payload_sincronizacao(payload, hoje=HOJE) == []

    def test_vld_002_data_futura(self, servico_inspecao):
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id], data_preenchimento=HOJE + timedelta(days=1)
        )
        assert 'VLD-002' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_002_data_ausente(self, servico_inspecao):
        payload = _payload_valido_base(servicos=[servico_inspecao.id], data_preenchimento=None)
        assert 'VLD-002' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_005_local_inicial_vazio(self, servico_inspecao):
        payload = _payload_valido_base(servicos=[servico_inspecao.id], id_local_inicial=None)
        assert 'VLD-005' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_006_local_final_vazio(self, servico_inspecao):
        payload = _payload_valido_base(servicos=[servico_inspecao.id], id_local_final=None)
        assert 'VLD-006' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_007_sem_linha(self, servico_inspecao):
        payload = _payload_valido_base(servicos=[servico_inspecao.id], linhas=[])
        assert 'VLD-007' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_008_sem_via(self, servico_inspecao):
        payload = _payload_valido_base(servicos=[servico_inspecao.id], vias=[])
        assert 'VLD-008' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_009_sem_tipo_manutencao(self, servico_inspecao):
        payload = _payload_valido_base(servicos=[servico_inspecao.id], id_tipo_manutencao=None)
        assert 'VLD-009' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_010_falha_sem_numero(self, servico_inspecao):
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id],
            _tipo_manutencao_e_falha=True,
            numero_falha=None,
        )
        assert 'VLD-010' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_011_horario_obrigatorio_vazio(self, servico_inspecao):
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id], hora_prog_inicio=None
        )
        assert 'VLD-011' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))


@pytest.mark.django_db
class TestConsistenciaDatetime:
    def test_vld_012_hp_termino_antes_do_inicio(self, servico_inspecao):
        from datetime import datetime

        payload = _payload_valido_base(
            servicos=[servico_inspecao.id],
            data_hora_prog_inicio=datetime(2026, 6, 15, 8, 0),
            data_hora_prog_termino=datetime(2026, 6, 15, 7, 0),
        )
        assert 'VLD-012' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_013_hr_termino_antes_do_inicio(self, servico_inspecao):
        from datetime import datetime

        payload = _payload_valido_base(
            servicos=[servico_inspecao.id],
            data_hora_real_inicio=datetime(2026, 6, 15, 8, 0),
            data_hora_real_termino=datetime(2026, 6, 15, 7, 0),
        )
        assert 'VLD-013' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))


@pytest.mark.django_db
class TestMotivosAtraso:
    def test_vld_014_atraso_inicio_sem_motivo(self, servico_inspecao):
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id], atraso_inicio=True, id_motivo_atraso_inicio=None
        )
        assert 'VLD-014' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_015_atraso_termino_sem_motivo(self, servico_inspecao):
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id], atraso_termino=True, id_motivo_atraso_termino=None
        )
        assert 'VLD-015' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_016_motivo_outros_sem_descricao(self, servico_inspecao, motivo_outros):
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id],
            atraso_inicio=True,
            id_motivo_atraso_inicio=motivo_outros.id,
            desc_motivo_atraso_inicio=None,
        )
        assert 'VLD-016' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_motivo_nao_outros_nao_exige_descricao(self, servico_inspecao, motivo_transito):
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id],
            atraso_inicio=True,
            id_motivo_atraso_inicio=motivo_transito.id,
            desc_motivo_atraso_inicio=None,
        )
        assert validar_payload_sincronizacao(payload, hoje=HOJE) == []


@pytest.mark.django_db
class TestServicosEColaboradores:
    def test_vld_017_sem_servico(self):
        payload = _payload_valido_base(servicos=[])
        assert 'VLD-017' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_018_outros_sem_descricao(self, servico_outros):
        payload = _payload_valido_base(
            servicos=[servico_outros.id], outros_servico_desc=None
        )
        assert 'VLD-018' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_019_sem_colaborador(self, servico_inspecao):
        payload = _payload_valido_base(servicos=[servico_inspecao.id], colaboradores=[])
        assert 'VLD-019' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))


@pytest.mark.django_db
class TestColaboradorNoCadastroOficial:
    def test_vld_027_colaborador_nao_localizado_bloqueia(self, servico_inspecao):
        """RG-RESP-008: tipo='colaborador' exige registro no cadastro oficial."""
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id],
            colaboradores=[
                {'registro_empresa': '00000', 'nome': 'Fantasma', 'tipo': 'colaborador'}
            ],
        )
        assert 'VLD-027' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_colaborador_cadastrado_nao_bloqueia(self, servico_inspecao):
        from colaboradores.models import ColaboradorCadastro

        ColaboradorCadastro.objects.create(registro_empresa='10000', nome='Fulano Real')
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id],
            colaboradores=[
                {'registro_empresa': '10000', 'nome': 'Nome Qualquer', 'tipo': 'colaborador'}
            ],
        )
        assert validar_payload_sincronizacao(payload, hoje=HOJE) == []

    def test_rg_resp_013_participante_nao_exige_cadastro(self, servico_inspecao):
        """Participantes externos nao pertencem ao cadastro oficial (RG-RESP-013)."""
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id],
            colaboradores=[
                {'registro_empresa': None, 'nome': 'Visitante Externo', 'tipo': 'participante'}
            ],
        )
        assert validar_payload_sincronizacao(payload, hoje=HOJE) == []


@pytest.mark.django_db
class TestColaboradorRegistroDuplicado:
    """
    RG-RESP-009. Bug real encontrado em teste manual (17/07/2026): sem
    esta validacao, um payload com o mesmo registro_empresa duas vezes
    derrubava a sincronizacao com IntegrityError nao tratado (HTTP 500),
    em vez de um 422 normal. Ver rad/test_views.py para o teste de
    integracao que confirma o status HTTP correto tambem.
    """

    def test_vld_031_mesmo_registro_duas_vezes_bloqueia(self, servico_inspecao):
        from colaboradores.models import ColaboradorCadastro

        ColaboradorCadastro.objects.create(registro_empresa='55555', nome='Fulano Duplicado')
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id],
            colaboradores=[
                {'registro_empresa': '55555', 'nome': 'Fulano Duplicado', 'tipo': 'colaborador'},
                {'registro_empresa': '55555', 'nome': 'Fulano Duplicado', 'tipo': 'colaborador'},
            ],
        )
        assert 'VLD-031' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_dois_participantes_sem_registro_nao_conflitam(self, servico_inspecao):
        """Participantes (registro_empresa=None) nao entram na checagem de duplicidade."""
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id],
            colaboradores=[
                {'registro_empresa': None, 'nome': 'Visitante A', 'tipo': 'participante'},
                {'registro_empresa': None, 'nome': 'Visitante B', 'tipo': 'participante'},
            ],
        )
        assert validar_payload_sincronizacao(payload, hoje=HOJE) == []


@pytest.mark.django_db
class TestBlocoAmv:
    def test_vld_020_amv_sem_mch(self, servico_amv):
        payload = _payload_valido_base(servicos=[servico_amv.id], amv={'id_mch': None})
        assert 'VLD-020' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_021_amv_sem_tipo_defeito(self, servico_amv):
        payload = _payload_valido_base(
            servicos=[servico_amv.id], amv={'id_mch': 1, 'tipos_defeito': []}
        )
        assert 'VLD-021' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_022_amv_sem_acoes(self, servico_amv):
        payload = _payload_valido_base(
            servicos=[servico_amv.id],
            amv={'id_mch': 1, 'tipos_defeito': [1], 'acoes': []},
        )
        assert 'VLD-022' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_amv_nao_exigido_quando_servico_nao_requer(self, servico_inspecao):
        payload = _payload_valido_base(servicos=[servico_inspecao.id], amv=None)
        assert validar_payload_sincronizacao(payload, hoje=HOJE) == []


@pytest.mark.django_db
class TestResponsavelAtividade:
    def test_vld_029_vazio_bloqueia(self, servico_inspecao):
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id], responsavel_atividade=None
        )
        assert 'VLD-029' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_vld_029_acima_de_50_caracteres_bloqueia(self, servico_inspecao):
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id], responsavel_atividade='A' * 51
        )
        assert 'VLD-029' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_exatos_50_caracteres_e_valido(self, servico_inspecao):
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id], responsavel_atividade='A' * 50
        )
        assert validar_payload_sincronizacao(payload, hoje=HOJE) == []


@pytest.mark.django_db
class TestOperadorCcm:
    def test_campo_vazio_nao_bloqueia_e_opcional(self, servico_inspecao):
        payload = _payload_valido_base(servicos=[servico_inspecao.id], operador_ccm=None)
        assert validar_payload_sincronizacao(payload, hoje=HOJE) == []

    def test_vld_030_acima_de_25_caracteres_bloqueia(self, servico_inspecao):
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id], operador_ccm='B' * 26
        )
        assert 'VLD-030' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))

    def test_exatos_25_caracteres_e_valido(self, servico_inspecao):
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id], operador_ccm='B' * 25
        )
        assert validar_payload_sincronizacao(payload, hoje=HOJE) == []


@pytest.mark.django_db
class TestCampoDesabilitadoNaValidacao:
    def test_campo_normalmente_obrigatorio_deixa_de_bloquear_quando_desabilitado(
        self, servico_inspecao
    ):
        """
        Mudanca de negocio (17/07/2026): campo desabilitado nao pode ser
        exigido, porque ninguem consegue preenche-lo (nao aparece para
        nenhum usuario). O campo ja existe (populado pela migration de
        dados), entao apenas atualizamos o estado.
        """
        from configuracoes.models import CampoFormulario

        CampoFormulario.objects.filter(chave='responsavel_atividade').update(habilitado=False)
        payload = _payload_valido_base(
            servicos=[servico_inspecao.id], responsavel_atividade=None
        )
        assert validar_payload_sincronizacao(payload, hoje=HOJE) == []

    def test_reabilitar_campo_volta_a_exigir(self, servico_inspecao):
        from configuracoes.models import CampoFormulario

        CampoFormulario.objects.filter(chave='responsavel_atividade').update(habilitado=False)
        CampoFormulario.objects.filter(chave='responsavel_atividade').update(habilitado=True)

        payload = _payload_valido_base(
            servicos=[servico_inspecao.id], responsavel_atividade=None
        )
        assert 'VLD-029' in _codigos(validar_payload_sincronizacao(payload, hoje=HOJE))
