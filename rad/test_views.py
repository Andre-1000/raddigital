"""
Testes de integracao do endpoint POST /rad/sincronizar/.

Cobre a orquestracao completa: autenticacao por token, validacao,
calculo de horarios, geracao atomica de numeros e persistencia das
tabelas relacionadas (linhas, vias, servicos, colaboradores, AMV).
"""
import json

import pytest
from django.urls import reverse

from catalogos.models import CatEquipe, CatLinha, CatLocal, CatMch, CatServico, CatTipoManutencao, CatVia
from rad.models import Rad
from usuarios.models import Token, Usuario


@pytest.fixture
def usuario_com_token(db):
    usuario = Usuario.objects.create(login='tecnico.view')
    token = Token.gerar_para(usuario)
    return usuario, token


@pytest.fixture
def catalogo_basico(db):
    return {
        'local': CatLocal.objects.create(sigla='BFU', nome='Barra Funda', categoria='estacao'),
        'linha': CatLinha.objects.create(codigo='11', nome='Coral'),
        'via': CatVia.objects.create(nome='Via 1'),
        'tipo_manutencao': CatTipoManutencao.objects.create(nome='Preventiva'),
        'equipe_vp': CatEquipe.objects.get_or_create(codigo='VP', defaults={'nome': 'VP'})[0],
        'servico': CatServico.objects.create(nome='Inspecao'),
    }


def _payload_valido(catalogo, **overrides):
    dados = {
        'numero_os': 4321,
        'numero_sa': '8765',
        'responsavel_atividade': 'Responsavel Teste',
        'data_preenchimento': '2026-06-15',
        'id_local_inicial': catalogo['local'].sigla,
        'id_local_final': catalogo['local'].sigla,
        'linhas': [catalogo['linha'].codigo],
        'vias': [catalogo['via'].id],
        'id_tipo_manutencao': catalogo['tipo_manutencao'].id,
        'numero_falha': None,
        'hora_prog_inicio': '08:00',
        'hora_prog_termino': '12:00',
        'hora_real_inicio': '08:00',
        'hora_real_termino': '12:00',
        'servicos': [catalogo['servico'].id],
        'colaboradores': [{'registro_empresa': '999', 'nome': 'Tecnico Um', 'tipo': 'participante'}],
        'amv': None,
        'sync_id_tentativa': 'view-teste-0001',
    }
    dados.update(overrides)
    return dados


def _autenticar(client, token):
    return {'HTTP_AUTHORIZATION': f'Token {token.token}'}


@pytest.mark.django_db
class TestEndpointSincronizar:
    def test_sem_token_retorna_401(self, client, catalogo_basico):
        resposta = client.post(
            reverse('rad:sincronizar'),
            data=json.dumps(_payload_valido(catalogo_basico)),
            content_type='application/json',
        )
        assert resposta.status_code == 401

    def test_corpo_json_invalido_retorna_400(self, client, usuario_com_token):
        _, token = usuario_com_token
        resposta = client.post(
            reverse('rad:sincronizar'),
            data='isto-nao-e-json-valido{{{',
            content_type='application/json',
            **_autenticar(client, token),
        )
        assert resposta.status_code == 400

    def test_campo_dados_invalido_no_multipart_retorna_400(self, client, usuario_com_token):
        _, token = usuario_com_token
        resposta = client.post(
            reverse('rad:sincronizar'),
            data={'dados': 'isto-nao-e-json-valido{{{'},
            **_autenticar(client, token),
        )
        assert resposta.status_code == 400

    def test_sync_id_tentativa_ausente_retorna_400(self, client, usuario_com_token, catalogo_basico):
        _, token = usuario_com_token
        payload = _payload_valido(catalogo_basico)
        del payload['sync_id_tentativa']
        resposta = client.post(
            reverse('rad:sincronizar'),
            data=json.dumps(payload),
            content_type='application/json',
            **_autenticar(client, token),
        )
        assert resposta.status_code == 400

    def test_payload_valido_cria_rad_e_retorna_201(
        self, client, usuario_com_token, catalogo_basico
    ):
        _, token = usuario_com_token
        resposta = client.post(
            reverse('rad:sincronizar'),
            data=json.dumps(_payload_valido(catalogo_basico)),
            content_type='application/json',
            **_autenticar(client, token),
        )

        assert resposta.status_code == 201
        corpo = resposta.json()
        assert corpo['numero_rad'].startswith('R')
        assert corpo['numero_execucao'] == 1
        assert corpo['status'] == 'sincronizado'
        assert corpo['numero_os'] == 4321
        assert corpo['numero_sa'] == '8765'

        rad = Rad.objects.get(numero_rad=corpo['numero_rad'])
        assert rad.numero_sa == '8765'
        assert rad.linhas.count() == 1
        assert rad.vias.count() == 1
        assert rad.servicos.count() == 1
        assert rad.colaboradores.count() == 1

    def test_payload_sem_servico_retorna_422_e_nao_cria_rad(
        self, client, usuario_com_token, catalogo_basico
    ):
        _, token = usuario_com_token
        resposta = client.post(
            reverse('rad:sincronizar'),
            data=json.dumps(_payload_valido(catalogo_basico, servicos=[])),
            content_type='application/json',
            **_autenticar(client, token),
        )

        assert resposta.status_code == 422
        codigos = {e['codigo'] for e in resposta.json()['erros']}
        assert 'VLD-017' in codigos
        assert Rad.objects.count() == 0

    def test_reenvio_com_mesmo_sync_id_e_idempotente(
        self, client, usuario_com_token, catalogo_basico
    ):
        _, token = usuario_com_token
        payload = _payload_valido(catalogo_basico, sync_id_tentativa='repetido-view')

        primeira = client.post(
            reverse('rad:sincronizar'),
            data=json.dumps(payload),
            content_type='application/json',
            **_autenticar(client, token),
        )
        segunda = client.post(
            reverse('rad:sincronizar'),
            data=json.dumps(payload),
            content_type='application/json',
            **_autenticar(client, token),
        )

        assert primeira.status_code == 201
        assert segunda.status_code == 200
        assert primeira.json()['numero_rad'] == segunda.json()['numero_rad']
        assert Rad.objects.filter(sync_id_tentativa='repetido-view').count() == 1

    def test_virada_de_meia_noite_calculada_corretamente(
        self, client, usuario_com_token, catalogo_basico
    ):
        _, token = usuario_com_token
        payload = _payload_valido(
            catalogo_basico,
            hora_prog_inicio='22:00',
            hora_prog_termino='02:00',
            hora_real_inicio='22:00',
            hora_real_termino='02:00',
            sync_id_tentativa='virada-view',
        )
        resposta = client.post(
            reverse('rad:sincronizar'),
            data=json.dumps(payload),
            content_type='application/json',
            **_autenticar(client, token),
        )

        assert resposta.status_code == 201
        rad = Rad.objects.get(numero_rad=resposta.json()['numero_rad'])
        assert rad.duracao_real_min == 240
        assert rad.data_hr_termino == rad.data_hr_inicio.replace(day=rad.data_hr_inicio.day + 1)

    def test_data_hp_inicio_e_data_hr_inicio_editadas_manualmente_sao_respeitadas(
        self, client, usuario_com_token, catalogo_basico
    ):
        """
        Bug de regressao: data_hp_inicio/data_hr_inicio enviados pelo
        cliente estavam sendo ignorados -- o backend sempre usava
        data_preenchimento, mesmo quando o usuario editou essas datas
        manualmente no formulario (campos editaveis desde o Bloco 2 do
        frontend). Corrigido em rad/views.py::_normalizar_payload e
        rad/regras_negocio.py::_preparar_horarios.
        """
        _, token = usuario_com_token
        data_editada = '2026-06-20'  # diferente de data_preenchimento (2026-06-15)
        payload = _payload_valido(
            catalogo_basico,
            data_hp_inicio=data_editada,
            data_hr_inicio=data_editada,
            sync_id_tentativa='data-inicio-editada',
        )
        resposta = client.post(
            reverse('rad:sincronizar'),
            data=json.dumps(payload),
            content_type='application/json',
            **_autenticar(client, token),
        )

        assert resposta.status_code == 201
        rad = Rad.objects.get(numero_rad=resposta.json()['numero_rad'])
        assert str(rad.data_hp_inicio) == data_editada
        assert str(rad.data_hr_inicio) == data_editada

    def test_bloco_amv_e_criado_quando_servico_exige(
        self, client, usuario_com_token, catalogo_basico
    ):
        _, token = usuario_com_token
        servico_amv = CatServico.objects.create(nome='Manutencao em AMV', requer_amv=True)
        mch = CatMch.objects.create(
            identificacao='MCH01A-BFU',
            modelo='M23-E',
            via='3',
            ur='BFU',
            local_amv='BFU',
            linha='11',
        )
        from catalogos.models import CatAcaoAmv, CatTipoDefeitoAmv

        defeito = CatTipoDefeitoAmv.objects.create(nome='DESGASTE')
        acao = CatAcaoAmv.objects.create(nome='LUBRIFICACAO')

        payload = _payload_valido(
            catalogo_basico,
            servicos=[catalogo_basico['servico'].id, servico_amv.id],
            amv={'id_mch': mch.id, 'tipos_defeito': [defeito.id], 'acoes': [acao.id]},
            sync_id_tentativa='amv-view',
        )
        resposta = client.post(
            reverse('rad:sincronizar'),
            data=json.dumps(payload),
            content_type='application/json',
            **_autenticar(client, token),
        )

        assert resposta.status_code == 201
        rad = Rad.objects.get(numero_rad=resposta.json()['numero_rad'])
        assert rad.amv.mch == mch
        assert rad.amv_defeitos.count() == 1
        assert rad.amv_acoes.count() == 1

    def test_amv_sem_mch_bloqueia_com_vld_020(
        self, client, usuario_com_token, catalogo_basico
    ):
        _, token = usuario_com_token
        servico_amv = CatServico.objects.create(nome='Manutencao em AMV', requer_amv=True)
        payload = _payload_valido(
            catalogo_basico,
            servicos=[servico_amv.id],
            amv=None,
            sync_id_tentativa='amv-sem-mch',
        )
        resposta = client.post(
            reverse('rad:sincronizar'),
            data=json.dumps(payload),
            content_type='application/json',
            **_autenticar(client, token),
        )

        assert resposta.status_code == 422
        codigos = {e['codigo'] for e in resposta.json()['erros']}
        assert 'VLD-020' in codigos

    def test_nome_do_colaborador_vem_do_cadastro_oficial_nao_do_payload(
        self, client, usuario_com_token, catalogo_basico
    ):
        """
        RG-RESP-004/005: o nome do colaborador nao e editavel manualmente
        -- mesmo que o cliente envie um nome diferente do cadastro, o
        servidor grava o nome oficial.
        """
        from colaboradores.models import ColaboradorCadastro

        _, token = usuario_com_token
        ColaboradorCadastro.objects.create(registro_empresa='30000', nome='Nome Oficial Correto')

        payload = _payload_valido(
            catalogo_basico,
            colaboradores=[
                {
                    'registro_empresa': '30000',
                    'nome': 'Nome Errado Que O Cliente Mandou',
                    'tipo': 'colaborador',
                }
            ],
            sync_id_tentativa='nome-oficial',
        )
        resposta = client.post(
            reverse('rad:sincronizar'),
            data=json.dumps(payload),
            content_type='application/json',
            **_autenticar(client, token),
        )

        assert resposta.status_code == 201
        rad = Rad.objects.get(numero_rad=resposta.json()['numero_rad'])
        colaborador_gravado = rad.colaboradores.get(registro_empresa='30000')
        assert colaborador_gravado.nome == 'Nome Oficial Correto'

    def test_nome_do_participante_e_preservado_como_enviado(
        self, client, usuario_com_token, catalogo_basico
    ):
        """RG-RESP-013/014: participante externo nao tem cadastro oficial para consultar."""
        _, token = usuario_com_token
        payload = _payload_valido(
            catalogo_basico,
            colaboradores=[
                {'registro_empresa': None, 'nome': 'Visitante da Prefeitura', 'tipo': 'participante'}
            ],
            sync_id_tentativa='participante-preservado',
        )
        resposta = client.post(
            reverse('rad:sincronizar'),
            data=json.dumps(payload),
            content_type='application/json',
            **_autenticar(client, token),
        )

        assert resposta.status_code == 201
        rad = Rad.objects.get(numero_rad=resposta.json()['numero_rad'])
        assert rad.colaboradores.first().nome == 'Visitante da Prefeitura'


@pytest.mark.django_db
class TestEquipesEnvolvidas:
    def test_equipe_vp_e_sempre_incluida_mesmo_sem_ser_enviada(
        self, client, usuario_com_token, catalogo_basico
    ):
        _, token = usuario_com_token
        payload = _payload_valido(
            catalogo_basico, equipes=[], sync_id_tentativa='equipe-vp-auto'
        )
        resposta = client.post(
            reverse('rad:sincronizar'),
            data=json.dumps(payload),
            content_type='application/json',
            **_autenticar(client, token),
        )

        assert resposta.status_code == 201
        rad = Rad.objects.get(numero_rad=resposta.json()['numero_rad'])
        assert list(rad.equipes.values_list('equipe_id', flat=True)) == ['VP']

    def test_equipes_enviadas_sao_somadas_a_vp_sem_duplicar(
        self, client, usuario_com_token, catalogo_basico
    ):
        from catalogos.models import CatEquipe

        CatEquipe.objects.get_or_create(codigo='SINAL', defaults={'nome': 'SINAL'})
        CatEquipe.objects.get_or_create(codigo='CIVIL', defaults={'nome': 'CIVIL'})

        _, token = usuario_com_token
        payload = _payload_valido(
            catalogo_basico,
            equipes=['SINAL', 'CIVIL', 'VP'],  # VP enviada explicitamente tambem
            sync_id_tentativa='equipe-soma',
        )
        resposta = client.post(
            reverse('rad:sincronizar'),
            data=json.dumps(payload),
            content_type='application/json',
            **_autenticar(client, token),
        )

        assert resposta.status_code == 201
        rad = Rad.objects.get(numero_rad=resposta.json()['numero_rad'])
        assert set(rad.equipes.values_list('equipe_id', flat=True)) == {'SINAL', 'CIVIL', 'VP'}
        assert rad.equipes.count() == 3  # sem duplicata de VP


@pytest.mark.django_db
class TestDescricaoTecnicaAtividade:
    def test_aceita_texto_longo_com_caracteres_especiais_e_numeros(
        self, client, usuario_com_token, catalogo_basico
    ):
        _, token = usuario_com_token
        texto_livre = (
            'Trilho km 12+300 apresentou desgaste de 4,5mm (limite: 3mm) — '
            'ação: substituição imediata! Temp.: -2°C. ' + ('Detalhe adicional. ' * 100)
        )
        payload = _payload_valido(
            catalogo_basico,
            descricao_tecnica_atividade=texto_livre,
            sync_id_tentativa='descricao-tecnica-livre',
        )
        resposta = client.post(
            reverse('rad:sincronizar'),
            data=json.dumps(payload),
            content_type='application/json',
            **_autenticar(client, token),
        )

        assert resposta.status_code == 201
        rad = Rad.objects.get(numero_rad=resposta.json()['numero_rad'])
        assert rad.descricao_tecnica_atividade == texto_livre


@pytest.mark.django_db
class TestCampoDesabilitadoEndToEnd:
    def test_sincronizacao_funciona_sem_campo_obrigatorio_quando_desabilitado(
        self, client, usuario_com_token, catalogo_basico
    ):
        from configuracoes.models import CampoFormulario

        CampoFormulario.objects.filter(chave='responsavel_atividade').update(habilitado=False)
        try:
            _, token = usuario_com_token
            payload = _payload_valido(
                catalogo_basico,
                responsavel_atividade=None,
                sync_id_tentativa='campo-desabilitado-sync',
            )
            resposta = client.post(
                reverse('rad:sincronizar'),
                data=json.dumps(payload),
                content_type='application/json',
                **_autenticar(client, token),
            )
            assert resposta.status_code == 201
        finally:
            CampoFormulario.objects.filter(chave='responsavel_atividade').update(habilitado=True)


@pytest.mark.django_db
class TestColaboradorDuplicadoNaoDerrubaOServidor:
    """
    Bug real encontrado em teste manual (17/07/2026): um payload com o
    mesmo colaborador duas vezes derrubava o endpoint com HTTP 500
    (IntegrityError nao tratado vindo direto do banco). Corrigido com
    VLD-031 em rad/validadores.py. Este teste prova o comportamento
    correto na camada HTTP real, nao so na funcao de validacao isolada.
    """

    def test_colaborador_duplicado_retorna_422_nao_500(
        self, client, usuario_com_token, catalogo_basico
    ):
        from colaboradores.models import ColaboradorCadastro

        ColaboradorCadastro.objects.create(registro_empresa='77777', nome='Fulano Teste')
        _, token = usuario_com_token
        payload = _payload_valido(
            catalogo_basico,
            colaboradores=[
                {'registro_empresa': '77777', 'nome': 'Fulano Teste', 'tipo': 'colaborador'},
                {'registro_empresa': '77777', 'nome': 'Fulano Teste', 'tipo': 'colaborador'},
            ],
            sync_id_tentativa='colaborador-duplicado-http',
        )
        resposta = client.post(
            reverse('rad:sincronizar'),
            data=json.dumps(payload),
            content_type='application/json',
            **_autenticar(client, token),
        )

        assert resposta.status_code == 422
        codigos = {e['codigo'] for e in resposta.json()['erros']}
        assert 'VLD-031' in codigos
        assert Rad.objects.filter(sync_id_tentativa='colaborador-duplicado-http').count() == 0
