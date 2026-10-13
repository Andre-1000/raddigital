"""
Testes da edicao de RAD ja sincronizado pelo Administrador (13/10/2026).

Autocontido (monta o proprio catalogo e payload), pelo mesmo motivo de
rad/test_numero_os.py: parte da suite antiga esta desatualizada em
relacao aos campos obrigatorios de hoje.
"""
import io
import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from catalogos.models import CatServico
from rad.models import Rad, RadAnexo, RadEdicao
from rad.test_numero_os import _payload, catalogo  # noqa: F401  (fixture reutilizada)
from usuarios.models import Token, Usuario, UsuarioPerfil


def _foto(nome='foto.jpg', cor='green'):
    buffer = io.BytesIO()
    Image.new('RGB', (10, 10), color=cor).save(buffer, format='JPEG')
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type='image/jpeg')


@pytest.fixture
def admin(db):
    usuario = Usuario.objects.create(login='admin.edit')
    UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.ADMINISTRADOR)
    return usuario, Token.gerar_para(usuario)


@pytest.fixture
def tecnico(db):
    usuario = Usuario.objects.create(login='tecnico.edit')
    UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.USUARIO)
    return usuario, Token.gerar_para(usuario)


def _auth(token):
    return {'HTTP_AUTHORIZATION': f'Token {token.valor_plano}'}


def _sincronizar(client, token, payload, fotos=None):
    resposta = client.post(
        reverse('rad:sincronizar'),
        data={
            'dados': json.dumps(payload),
            'fotos_intervencao_verificada': fotos if fotos is not None else [_foto()],
        },
        **_auth(token),
    )
    assert resposta.status_code == 201, resposta.content
    return Rad.objects.get(numero_rad=resposta.json()['numero_rad'])


def _editar(client, token, numero_rad, payload, motivo='Correção solicitada', ocultar=None,
            fotos_intervencao=None, fotos_acao=None):
    dados = {**payload, 'motivo_edicao': motivo, 'ocultar_anexos': ocultar or []}
    data = {'dados': json.dumps(dados)}
    if fotos_intervencao:
        data['fotos_intervencao_verificada'] = fotos_intervencao
    if fotos_acao:
        data['fotos_acao_realizada'] = fotos_acao
    return client.post(reverse('rad:editar', args=[numero_rad]), data=data, **_auth(token))


@pytest.fixture
def rad_sincronizado(client, catalogo, tecnico):  # noqa: F811
    _, token = tecnico
    return _sincronizar(client, token, _payload(catalogo))


def _como_na_tela(rascunho):
    """Mesma conversao de rad_form.js::montarDadosParaEnvio para a canaleta/terceiros."""
    dados = dict(rascunho)
    itens = []
    for item in dados.get('canaleta_itens') or []:
        dim = item['dimensao']
        itens.append({
            'anomalias': item['anomalias'],
            'grau_criticidade': item['grau_criticidade'] or None,
            'justificativa': item['justificativa'] or None,
            'necessita_cautela': {'sim': True, 'nao': False}.get(item['necessita_cautela']),
            'lados': item['lados'],
            'dimensao': {
                **{
                    c: (float(dim[c]) if dim[c] != '' else None)
                    for c in ('largura_inicial', 'largura_final', 'altura_inicial', 'altura_final', 'comprimento')
                },
                **{
                    f'{c}_nao_identificado': bool(dim[f'{c}_nao_identificado'])
                    for c in ('largura_inicial', 'largura_final', 'altura_inicial', 'altura_final', 'comprimento',
                              'km_poste_inicial', 'km_poste_final')
                },
                'km_poste_inicial': dim['km_poste_inicial'] or None,
                'km_poste_final': dim['km_poste_final'] or None,
            },
        })
    dados['canaleta_itens'] = itens
    for c in ('encarregados', 'op_maquina', 'ajudantes', 'motorista'):
        k = f'terceiros_num_{c}'
        dados[k] = int(dados[k]) if dados[k] else None
    dados['terceiros_volume'] = int(dados['terceiros_volume']) if dados['terceiros_volume'] else None
    return dados


@pytest.mark.django_db
class TestPermissao:
    def test_tecnico_nao_edita(self, client, rad_sincronizado, tecnico, catalogo):  # noqa: F811
        _, token = tecnico
        resposta = _editar(client, token, rad_sincronizado.numero_rad, _payload(catalogo, observacoes_gerais='x'))
        assert resposta.status_code == 403
        rad_sincronizado.refresh_from_db()
        assert rad_sincronizado.observacoes_gerais is None

    def test_tecnico_nao_le_dados_de_edicao(self, client, rad_sincronizado, tecnico):
        _, token = tecnico
        resposta = client.get(reverse('rad:dados_edicao', args=[rad_sincronizado.numero_rad]), **_auth(token))
        assert resposta.status_code == 403

    def test_rad_inexistente_404(self, client, admin, catalogo):  # noqa: F811
        _, token = admin
        resposta = _editar(client, token, 'R99999', _payload(catalogo))
        assert resposta.status_code == 404


@pytest.mark.django_db
class TestEdicaoBasica:
    def test_edita_campos_e_registra_historico(self, client, rad_sincronizado, admin, catalogo):  # noqa: F811
        usuario, token = admin
        antigo_numero = rad_sincronizado.numero_rad
        resposta = _editar(
            client, token, antigo_numero,
            _payload(catalogo, numero_sa='99999', observacoes_gerais='texto novo'),
            motivo='SA digitada errada',
        )
        assert resposta.status_code == 200, resposta.content
        corpo = resposta.json()
        assert corpo['numero_rad'] == antigo_numero
        assert corpo['total_alteracoes'] == 2

        rad = Rad.objects.get(numero_rad=antigo_numero)
        assert rad.numero_sa == '99999'
        assert rad.observacoes_gerais == 'texto novo'
        assert rad.data_ultima_edicao is not None
        assert Rad.objects.count() == 1  # editou no lugar, nao criou outro

        edicao = RadEdicao.objects.get()
        assert edicao.usuario_id == usuario.login
        assert edicao.motivo == 'SA digitada errada'
        por_campo = {a['campo']: a for a in edicao.alteracoes}
        assert por_campo['SA'] == {'campo': 'SA', 'antes': '35463', 'depois': '99999'}
        assert por_campo['Observações gerais']['antes'] is None

    def test_motivo_e_obrigatorio_e_nada_e_gravado(self, client, rad_sincronizado, admin, catalogo):  # noqa: F811
        _, token = admin
        resposta = _editar(client, token, rad_sincronizado.numero_rad,
                           _payload(catalogo, numero_sa='11111'), motivo='   ')
        assert resposta.status_code == 422
        assert any(e['codigo'] == 'EDT-001' for e in resposta.json()['erros'])
        rad_sincronizado.refresh_from_db()
        assert rad_sincronizado.numero_sa == '35463'
        assert rad_sincronizado.data_ultima_edicao is None
        assert RadEdicao.objects.count() == 0

    def test_sem_alteracao_nao_grava_nada(self, client, rad_sincronizado, admin, catalogo):  # noqa: F811
        _, token = admin
        resposta = _editar(client, token, rad_sincronizado.numero_rad, _payload(catalogo))
        assert resposta.status_code == 422
        assert any(e['codigo'] == 'EDT-002' for e in resposta.json()['erros'])
        rad_sincronizado.refresh_from_db()
        assert rad_sincronizado.data_ultima_edicao is None
        assert RadEdicao.objects.count() == 0

    def test_usa_as_mesmas_validacoes_do_rad_novo(self, client, rad_sincronizado, admin, catalogo):  # noqa: F811
        _, token = admin
        resposta = _editar(client, token, rad_sincronizado.numero_rad,
                           _payload(catalogo, numero_os=123456789012))  # 12 digitos
        assert resposta.status_code == 422
        assert any(e['campo'] == 'numero_os' for e in resposta.json()['erros'])
        rad_sincronizado.refresh_from_db()
        assert rad_sincronizado.numero_os == 4321

    def test_rad_cancelado_nao_edita(self, client, rad_sincronizado, admin, catalogo):  # noqa: F811
        _, token = admin
        Rad.objects.filter(pk=rad_sincronizado.pk).update(status=Rad.CANCELADO)
        resposta = _editar(client, token, rad_sincronizado.numero_rad,
                           _payload(catalogo, numero_sa='22222'))
        assert resposta.status_code == 409
        dados = client.get(reverse('rad:dados_edicao', args=[rad_sincronizado.numero_rad]), **_auth(token))
        assert dados.status_code == 409


@pytest.mark.django_db
class TestOsEExecucao:
    def test_mudar_de_os_gera_nova_execucao_na_os_nova_sem_renumerar_as_outras(
        self, client, catalogo, tecnico, admin  # noqa: F811
    ):
        _, token_tec = tecnico
        _, token_adm = admin
        a = _sincronizar(client, token_tec, _payload(catalogo, numero_os=1000, sync_id_tentativa='a'))
        b = _sincronizar(client, token_tec, _payload(catalogo, numero_os=1000, sync_id_tentativa='b'))
        c = _sincronizar(client, token_tec, _payload(catalogo, numero_os=1000, sync_id_tentativa='c'))
        assert (a.numero_execucao, b.numero_execucao, c.numero_execucao) == (1, 2, 3)
        d = _sincronizar(client, token_tec, _payload(catalogo, numero_os=2000, sync_id_tentativa='d'))
        assert d.numero_execucao == 1

        # Move o RAD 'b' (execucao 2) da OS 1000 para a OS 2000.
        resposta = _editar(client, token_adm, b.numero_rad, _payload(catalogo, numero_os=2000))
        assert resposta.status_code == 200, resposta.content
        b.refresh_from_db()
        assert (b.numero_os, b.numero_execucao) == (2000, 2)
        # Os outros RADs da OS antiga mantem os numeros que ja tinham.
        a.refresh_from_db()
        c.refresh_from_db()
        assert (a.numero_execucao, c.numero_execucao) == (1, 3)

        # E o proximo RAD da OS antiga NAO repete o 3 (buraco no 2).
        e = _sincronizar(client, token_tec, _payload(catalogo, numero_os=1000, sync_id_tentativa='e'))
        assert e.numero_execucao == 4

    def test_editar_sem_trocar_a_os_nao_mexe_na_execucao(self, client, catalogo, tecnico, admin):  # noqa: F811
        _, token_tec = tecnico
        _, token_adm = admin
        _sincronizar(client, token_tec, _payload(catalogo, numero_os=1000, sync_id_tentativa='a'))
        b = _sincronizar(client, token_tec, _payload(catalogo, numero_os=1000, sync_id_tentativa='b'))
        _editar(client, token_adm, b.numero_rad, _payload(catalogo, numero_os=1000, numero_sa='555'))
        b.refresh_from_db()
        assert b.numero_execucao == 2


@pytest.mark.django_db
class TestDesatualizacaoDriveEPlanilha:
    def test_edicao_marca_drive_e_planilha_como_desatualizados(
        self, client, rad_sincronizado, admin, catalogo  # noqa: F811
    ):
        _, token = admin
        agora = timezone.now()
        Rad.objects.filter(pk=rad_sincronizado.pk).update(
            data_ultimo_envio_drive=agora, data_ultima_sincronizacao_planilha=agora
        )
        rad_sincronizado.refresh_from_db()
        assert not rad_sincronizado.drive_desatualizado
        assert not rad_sincronizado.planilha_desatualizada

        resposta = _editar(client, token, rad_sincronizado.numero_rad,
                           _payload(catalogo, numero_sa='77777'))
        assert resposta.status_code == 200
        corpo = resposta.json()
        assert corpo['drive_desatualizado'] is True
        assert corpo['planilha_desatualizada'] is True

    def test_rad_nunca_enviado_nao_aparece_como_desatualizado(self, client, rad_sincronizado, admin, catalogo):  # noqa: F811
        """Nunca enviado = pendente (outro estado), nao 'desatualizado'."""
        _, token = admin
        corpo = _editar(client, token, rad_sincronizado.numero_rad,
                        _payload(catalogo, numero_sa='77777')).json()
        assert corpo['drive_desatualizado'] is False
        assert corpo['planilha_desatualizada'] is False


@pytest.mark.django_db
class TestFotos:
    def test_ocultar_foto_mantendo_outra(self, client, catalogo, tecnico, admin):  # noqa: F811
        _, token_tec = tecnico
        _, token_adm = admin
        rad = _sincronizar(client, token_tec, _payload(catalogo),
                           fotos=[_foto('a.jpg'), _foto('b.jpg', 'red')])
        ids = list(rad.anexos.order_by('id').values_list('id', flat=True))
        assert len(ids) == 2

        resposta = _editar(client, token_adm, rad.numero_rad, _payload(catalogo), ocultar=[ids[0]])
        assert resposta.status_code == 200, resposta.content

        assert rad.anexos.count() == 1  # a oculta some das leituras normais
        oculto = RadAnexo.todos.get(id=ids[0])
        assert oculto.oculto is True
        assert oculto.ocultado_por_id == 'admin.edit'
        assert oculto.data_ocultacao is not None  # nao foi apagada
        alteracao = RadEdicao.objects.get().alteracoes[0]
        assert alteracao['campo'] == 'Anexos'
        assert len(alteracao['antes']) == 2 and len(alteracao['depois']) == 1

    def test_nao_pode_ficar_sem_nenhuma_foto(self, client, catalogo, tecnico, admin):  # noqa: F811
        _, token_tec = tecnico
        _, token_adm = admin
        rad = _sincronizar(client, token_tec, _payload(catalogo))
        id_unico = rad.anexos.get().id
        resposta = _editar(client, token_adm, rad.numero_rad, _payload(catalogo), ocultar=[id_unico])
        assert resposta.status_code == 422
        assert any(e['codigo'] == 'VLD-032' for e in resposta.json()['erros'])
        assert rad.anexos.count() == 1

    def test_substituir_foto_oculta_a_antiga_e_adiciona_a_nova(self, client, catalogo, tecnico, admin):  # noqa: F811
        _, token_tec = tecnico
        _, token_adm = admin
        rad = _sincronizar(client, token_tec, _payload(catalogo), fotos=[_foto('velha.jpg')])
        id_velha = rad.anexos.get().id
        resposta = _editar(client, token_adm, rad.numero_rad, _payload(catalogo),
                           ocultar=[id_velha], fotos_intervencao=[_foto('nova.jpg', 'blue')])
        assert resposta.status_code == 200, resposta.content
        nomes = list(rad.anexos.values_list('nome_original', flat=True))
        assert nomes == ['nova.jpg']

    def test_respeita_o_limite_de_fotos_considerando_as_que_ficam(self, client, catalogo, tecnico, admin):  # noqa: F811
        _, token_tec = tecnico
        _, token_adm = admin
        rad = _sincronizar(client, token_tec, _payload(catalogo),
                           fotos=[_foto('a.jpg'), _foto('b.jpg')])  # limite padrao: 2
        resposta = _editar(client, token_adm, rad.numero_rad, _payload(catalogo),
                           fotos_intervencao=[_foto('c.jpg')])
        assert resposta.status_code == 422
        assert any(e['codigo'] == 'ANX-003' for e in resposta.json()['erros'])
        assert rad.anexos.count() == 2

    def test_anexo_de_outro_rad_nao_pode_ser_ocultado(self, client, catalogo, tecnico, admin):  # noqa: F811
        _, token_tec = tecnico
        _, token_adm = admin
        rad1 = _sincronizar(client, token_tec, _payload(catalogo, sync_id_tentativa='1'))
        rad2 = _sincronizar(client, token_tec, _payload(catalogo, sync_id_tentativa='2'))
        alheio = rad2.anexos.get().id
        resposta = _editar(client, token_adm, rad1.numero_rad, _payload(catalogo, numero_sa='1'),
                           ocultar=[alheio])
        assert resposta.status_code == 422
        assert RadAnexo.objects.filter(id=alheio).exists()


@pytest.mark.django_db
class TestDadosParaEdicao:
    def test_rascunho_devolvido_e_aceito_de_volta_como_esta(self, client, rad_sincronizado, admin):
        """
        O round-trip e o teste mais importante: o que a tela de edicao
        carrega, quando devolvido sem mexer em nada, precisa ser aceito
        pelas validacoes e resultar em 'nenhuma alteracao' (422/EDT-002) --
        nunca em outro erro de validacao.
        """
        _, token = admin
        dados = client.get(reverse('rad:dados_edicao', args=[rad_sincronizado.numero_rad]), **_auth(token)).json()
        assert [a['nome_original'] for a in dados['anexos']] == ['foto.jpg']
        payload = _como_na_tela(dados['rascunho'])
        resposta = _editar(client, token, rad_sincronizado.numero_rad, payload)
        assert resposta.status_code == 422
        assert [e['codigo'] for e in resposta.json()['erros']] == ['EDT-002'], resposta.json()

    def test_round_trip_com_canaleta_e_terceiros(self, client, catalogo, tecnico, admin):  # noqa: F811
        _, token_tec = tecnico
        _, token_adm = admin
        servico = CatServico.objects.create(nome='Inspeção de Canaleta X', requer_canaleta=True)
        item = {
            'anomalias': ['quebrada'], 'grau_criticidade': 'media', 'justificativa': 'trinca',
            'necessita_cautela': True, 'lados': ['direito'],
            'dimensao': {
                'largura_inicial': 1.5, 'largura_inicial_nao_identificado': False,
                'largura_final': None, 'largura_final_nao_identificado': True,
                'altura_inicial': 2, 'altura_inicial_nao_identificado': False,
                'altura_final': 2, 'altura_final_nao_identificado': False,
                'comprimento': 10, 'comprimento_nao_identificado': False,
                'km_poste_inicial': '12/03', 'km_poste_inicial_nao_identificado': False,
                'km_poste_final': None, 'km_poste_final_nao_identificado': True,
            },
        }
        rad = _sincronizar(client, token_tec, _payload(
            catalogo, servicos=[servico.id], canaleta_itens=[item], terceiros_num_ajudantes=3,
        ))
        dados = client.get(reverse('rad:dados_edicao', args=[rad.numero_rad]), **_auth(token_adm)).json()
        payload = _como_na_tela(dados['rascunho'])
        resposta = _editar(client, token_adm, rad.numero_rad, payload)
        assert [e['codigo'] for e in resposta.json()['erros']] == ['EDT-002'], resposta.json()

        # E uma alteracao real dentro do item da canaleta e detectada.
        payload['canaleta_itens'][0]['grau_criticidade'] = 'alta'
        resposta = _editar(client, token_adm, rad.numero_rad, payload)
        assert resposta.status_code == 200, resposta.content
        assert rad.canaleta_itens.get().grau_criticidade == 'alta'
        campos = [a['campo'] for a in RadEdicao.objects.get().alteracoes]
        assert campos == ['Anomalias observadas']

    def test_colaboradores_e_selecoes_sao_recriados_sem_duplicar(self, client, rad_sincronizado, admin, catalogo):  # noqa: F811
        _, token = admin
        payload = _payload(catalogo, colaboradores=[
            {'registro_empresa': None, 'nome': 'Outro Participante', 'tipo': 'participante'},
        ])
        resposta = _editar(client, token, rad_sincronizado.numero_rad, payload)
        assert resposta.status_code == 200, resposta.content
        assert list(rad_sincronizado.colaboradores.values_list('nome', flat=True)) == ['Outro Participante']
        assert rad_sincronizado.linhas.count() == 1
        assert rad_sincronizado.equipes.count() == 1  # VP automatica
