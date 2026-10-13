"""
Edicao de RAD x Google Drive / Google Sheets / Consulta (13/10/2026).

Nenhum teste chama a internet: as funcoes do Google sao substituidas
por mocks (o que se testa aqui e a DECISAO -- quem e reenviado, como,
e o que a tela mostra --, nao a API do Google).
"""
import json
from unittest import mock

import pytest
from django.urls import reverse
from django.utils import timezone

from rad.models import Rad
from rad.test_edicao_rad import (  # noqa: F401  (fixtures reutilizadas)
    _auth, _editar, _payload, _sincronizar, admin, catalogo, rad_sincronizado, tecnico,
)


def _editar_e_marcar_envios(client, token, rad, catalogo):
    """Marca o RAD como ja enviado ao Drive e a planilha e entao o edita."""
    antes = timezone.now() - timezone.timedelta(hours=1)
    Rad.objects.filter(pk=rad.pk).update(
        data_ultimo_envio_drive=antes, data_ultima_sincronizacao_planilha=antes
    )
    resposta = _editar(client, token, rad.numero_rad, _payload(catalogo, numero_sa='88888'))
    assert resposta.status_code == 200, resposta.content
    rad.refresh_from_db()
    return rad


# ---------------------------------------------------------------------------
# Drive
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestDrive:
    URL = 'consulta:exportar_docx_drive'

    def _chamar(self, client, token, rad, existe):
        with mock.patch('rad.google_drive.arquivo_existe_no_drive', return_value=existe) as p_existe, \
             mock.patch('rad.google_drive.salvar_docx_no_drive', return_value='link-novo') as p_salvar, \
             mock.patch('rad.google_drive.substituir_docx_no_drive', return_value=('link-trocado', 1)) as p_subst, \
             mock.patch('rad.exportacao_oficial.gerar_docx_oficial_bytes', return_value=b'docx') as p_gerar:
            resposta = client.get(reverse(self.URL, args=[rad.numero_rad]), **_auth(token))
        return resposta, p_salvar, p_subst, p_gerar

    def test_existente_e_em_dia_continua_retornando_409(self, client, rad_sincronizado, admin):
        _, token = admin
        Rad.objects.filter(pk=rad_sincronizado.pk).update(data_ultimo_envio_drive=timezone.now())
        resposta, salvar, substituir, gerar = self._chamar(client, token, rad_sincronizado, existe=True)
        assert resposta.status_code == 409
        salvar.assert_not_called()
        substituir.assert_not_called()
        gerar.assert_not_called()  # nao gasta processamento a toa

    def test_existente_mas_editado_substitui_o_arquivo(self, client, rad_sincronizado, admin, catalogo):  # noqa: F811
        _, token = admin
        rad = _editar_e_marcar_envios(client, token, rad_sincronizado, catalogo)
        assert rad.drive_desatualizado

        resposta, salvar, substituir, gerar = self._chamar(client, token, rad, existe=True)
        assert resposta.status_code == 200
        assert resposta.json() == {'link': 'link-trocado', 'copias_extras': 1}
        substituir.assert_called_once_with(f'{rad.numero_rad}.docx', b'docx')
        salvar.assert_not_called()  # nao cria copia

        rad.refresh_from_db()
        assert not rad.drive_desatualizado  # voltou a ficar em dia

    def test_inexistente_cria_normalmente(self, client, rad_sincronizado, admin):
        _, token = admin
        resposta, salvar, substituir, _ = self._chamar(client, token, rad_sincronizado, existe=False)
        assert resposta.status_code == 200
        assert resposta.json()['link'] == 'link-novo'
        salvar.assert_called_once()
        substituir.assert_not_called()


class _ServicoDriveFalso:
    """Imita o encadeamento files().list().execute() / files().update()."""

    def __init__(self, arquivos):
        self.arquivos = arquivos
        self.chamadas_update = []
        self.chamadas_create = []

    def files(self):
        return self

    def list(self, **kwargs):
        return mock.Mock(execute=lambda: {'files': self.arquivos})

    def update(self, **kwargs):
        self.chamadas_update.append(kwargs)
        return mock.Mock(execute=lambda: {'id': kwargs['fileId'], 'webViewLink': 'https://drive/x'})

    def create(self, **kwargs):
        self.chamadas_create.append(kwargs)
        return mock.Mock(execute=lambda: {'id': 'novo', 'webViewLink': 'https://drive/novo'})


class TestSubstituirDocxNoDrive:
    def _rodar(self, arquivos, monkeypatch):
        from rad import google_drive
        servico = _ServicoDriveFalso(arquivos)
        monkeypatch.setenv('GOOGLE_DRIVE_CREDENTIALS_JSON', '{}')
        monkeypatch.setenv('GOOGLE_DRIVE_FOLDER_ID', 'pasta')
        monkeypatch.setattr(google_drive, '_obter_servico', lambda: servico)
        return servico, google_drive.substituir_docx_no_drive('R00001.docx', b'conteudo')

    def test_atualiza_o_arquivo_mais_antigo_e_nao_apaga_os_outros(self, monkeypatch):
        servico, (link, extras) = self._rodar(
            [{'id': 'antigo', 'createdTime': '1'}, {'id': 'copia', 'createdTime': '2'}], monkeypatch
        )
        assert link == 'https://drive/x'
        assert extras == 1
        assert [c['fileId'] for c in servico.chamadas_update] == ['antigo']
        assert servico.chamadas_create == []

    def test_sem_arquivo_cria_um(self, monkeypatch):
        servico, (link, extras) = self._rodar([], monkeypatch)
        assert link == 'https://drive/novo'
        assert extras == 0
        assert len(servico.chamadas_create) == 1


# ---------------------------------------------------------------------------
# Planilha
# ---------------------------------------------------------------------------

class _ServicoSheetsFalso:
    def __init__(self, coluna_a):
        self.coluna_a = coluna_a
        self.batch = []
        self.appends = []

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, **kwargs):
        return mock.Mock(execute=lambda: {'values': self.coluna_a})

    def batchUpdate(self, **kwargs):
        self.batch.append(kwargs['body'])
        return mock.Mock(execute=lambda: {})

    def append(self, **kwargs):
        self.appends.append(kwargs['body']['values'])
        return mock.Mock(execute=lambda: {})


class TestAtualizarLinhasDaPlanilha:
    def _rodar(self, coluna_a, pares, monkeypatch):
        from rad import google_sheets
        servico = _ServicoSheetsFalso(coluna_a)
        monkeypatch.setenv('GOOGLE_DRIVE_CREDENTIALS_JSON', '{}')
        monkeypatch.setenv('GOOGLE_SHEETS_SPREADSHEET_ID', 'planilha')
        monkeypatch.setenv('GOOGLE_SHEETS_ABA', 'Aba')
        monkeypatch.setattr(google_sheets, '_obter_servico', lambda: servico)
        return servico, google_sheets.atualizar_linhas(pares)

    def test_acha_a_linha_pela_coluna_a_e_atualiza_no_lugar(self, monkeypatch):
        coluna_a = [['Número RAD'], ['R00001'], ['R00002'], ['R00003']]
        servico, resultado = self._rodar(coluna_a, [('R00002', ['R00002', 'novo'])], monkeypatch)
        assert resultado == (1, 0)
        assert servico.batch == [
            {'valueInputOption': 'USER_ENTERED',
             'data': [{'range': "'Aba'!A3", 'values': [['R00002', 'novo']]}]}
        ]
        assert servico.appends == []

    def test_rad_que_nao_esta_na_planilha_e_acrescentado(self, monkeypatch):
        servico, resultado = self._rodar([['Número RAD'], ['R00001']], [('R00009', ['R00009', 'x'])], monkeypatch)
        assert resultado == (0, 1)
        assert servico.batch == []
        assert servico.appends == [[['R00009', 'x']]]

    def test_numero_duplicado_atualiza_a_primeira_ocorrencia(self, monkeypatch):
        coluna_a = [['Número RAD'], ['R00001'], ['R00001']]
        servico, _ = self._rodar(coluna_a, [('R00001', ['R00001', 'y'])], monkeypatch)
        assert servico.batch[0]['data'][0]['range'] == "'Aba'!A2"

    def test_cabecalho_nunca_e_sobrescrito(self, monkeypatch):
        """Mesmo que um RAD tivesse o nome do cabecalho, a linha 1 e ignorada."""
        servico, resultado = self._rodar([['R00001']], [('R00001', ['R00001'])], monkeypatch)
        assert resultado == (0, 1)


@pytest.mark.django_db
class TestSyncBdComEditados:
    def test_contadores_e_envio_separam_novos_de_editados(self, client, catalogo, tecnico, admin):  # noqa: F811
        _, token_tec = tecnico
        _, token_adm = admin
        novo = _sincronizar(client, token_tec, _payload(catalogo, sync_id_tentativa='novo'))
        editado = _sincronizar(client, token_tec, _payload(catalogo, sync_id_tentativa='editado'))
        em_dia = _sincronizar(client, token_tec, _payload(catalogo, sync_id_tentativa='em-dia'))
        Rad.objects.filter(pk=em_dia.pk).update(data_ultima_sincronizacao_planilha=timezone.now())
        _editar_e_marcar_envios(client, token_adm, editado, catalogo)

        contadores = client.get(reverse('dashboard:sync_bd_dados'), **_auth(token_adm)).json()
        assert contadores == {
            'total_rad_preenchidos': 3,
            'total_rad_sincronizados': 1,
            'total_rad_desatualizados': 1,
            'total_rad_nao_sincronizados': 1,
        }

        with mock.patch('rad.google_sheets.enviar_linhas') as enviar, \
             mock.patch('rad.google_sheets.atualizar_linhas') as atualizar:
            resposta = client.post(
                reverse('dashboard:sync_bd_sincronizar'),
                data=json.dumps({'quantidade': 'restante'}), content_type='application/json',
                **_auth(token_adm),
            )
        corpo = resposta.json()
        assert resposta.status_code == 200, corpo
        assert (corpo['processados'], corpo['atualizados']) == (1, 1)

        (linhas_novas,), _ = enviar.call_args
        assert [l[0] for l in linhas_novas] == [novo.numero_rad]  # so o nunca enviado
        (pares,), _ = atualizar.call_args
        assert [p[0] for p in pares] == [editado.numero_rad]  # o editado vai por atualizacao

        assert corpo['total_rad_desatualizados'] == 0
        assert corpo['total_rad_nao_sincronizados'] == 0
        assert corpo['total_rad_sincronizados'] == 3

    def test_limite_da_quantidade_vale_para_novos_mais_editados(self, client, catalogo, tecnico, admin):  # noqa: F811
        _, token_tec = tecnico
        _, token_adm = admin
        _sincronizar(client, token_tec, _payload(catalogo, sync_id_tentativa='novo'))
        editado = _sincronizar(client, token_tec, _payload(catalogo, sync_id_tentativa='editado'))
        _editar_e_marcar_envios(client, token_adm, editado, catalogo)

        with mock.patch('rad.google_sheets.enviar_linhas') as enviar, \
             mock.patch('rad.google_sheets.atualizar_linhas') as atualizar:
            corpo = client.post(
                reverse('dashboard:sync_bd_sincronizar'),
                data=json.dumps({'quantidade': 1}), content_type='application/json',
                **_auth(token_adm),
            ).json()
        assert (corpo['processados'], corpo['atualizados']) == (1, 0)
        enviar.assert_called_once()
        atualizar.assert_not_called()
        assert corpo['total_rad_desatualizados'] == 1  # fica para o proximo clique

    def test_falha_ao_atualizar_nao_marca_como_em_dia(self, client, catalogo, tecnico, admin):  # noqa: F811
        _, token_tec = tecnico
        _, token_adm = admin
        editado = _sincronizar(client, token_tec, _payload(catalogo))
        _editar_e_marcar_envios(client, token_adm, editado, catalogo)
        with mock.patch('rad.google_sheets.atualizar_linhas', side_effect=RuntimeError('api fora')):
            resposta = client.post(
                reverse('dashboard:sync_bd_sincronizar'),
                data=json.dumps({'quantidade': 'restante'}), content_type='application/json',
                **_auth(token_adm),
            )
        assert resposta.status_code == 502
        editado.refresh_from_db()
        assert editado.planilha_desatualizada  # continua pendente


# ---------------------------------------------------------------------------
# Consulta
# ---------------------------------------------------------------------------

@pytest.mark.django_db
class TestConsultaDeRadEditado:
    def test_detalhe_para_admin_e_para_o_tecnico(self, client, rad_sincronizado, tecnico, admin, catalogo):  # noqa: F811
        _, token_tec = tecnico
        _, token_adm = admin
        _editar_e_marcar_envios(client, token_adm, rad_sincronizado, catalogo)

        url = reverse('consulta:detalhe_rad', args=[rad_sincronizado.numero_rad])
        do_admin = client.get(url, **_auth(token_adm)).json()
        assert do_admin['pode_editar'] is True
        assert do_admin['editado_por'] == 'admin.edit'
        assert do_admin['drive_desatualizado'] is True
        assert do_admin['enviado_drive'] is False  # velho = conta como pendente
        assert do_admin['edicoes'][0]['motivo'] == 'Correção solicitada'

        do_tecnico = client.get(url, **_auth(token_tec)).json()
        assert do_tecnico['pode_editar'] is False
        assert do_tecnico['editado_por'] == 'admin.edit'  # sabe que foi alterado...
        assert do_tecnico['edicoes'] == []                # ...mas nao ve o historico

    def test_filtro_nao_enviado_drive_inclui_os_editados(self, client, catalogo, tecnico, admin):  # noqa: F811
        _, token_tec = tecnico
        _, token_adm = admin
        editado = _sincronizar(client, token_tec, _payload(catalogo, sync_id_tentativa='a'))
        em_dia = _sincronizar(client, token_tec, _payload(catalogo, sync_id_tentativa='b'))
        Rad.objects.filter(pk=em_dia.pk).update(data_ultimo_envio_drive=timezone.now())
        _editar_e_marcar_envios(client, token_adm, editado, catalogo)

        resposta = client.get(reverse('consulta:listar_rads'), {'status': 'nao_enviado_drive'}, **_auth(token_adm))
        numeros = [r['numero_rad'] for r in resposta.json()['resultados']]
        assert numeros == [editado.numero_rad]

    def test_foto_ocultada_some_do_detalhe(self, client, catalogo, tecnico, admin):  # noqa: F811
        from rad.test_edicao_rad import _foto
        _, token_tec = tecnico
        _, token_adm = admin
        rad = _sincronizar(client, token_tec, _payload(catalogo), fotos=[_foto('a.jpg'), _foto('b.jpg')])
        id_a = rad.anexos.order_by('id').first().id
        _editar(client, token_adm, rad.numero_rad, _payload(catalogo), ocultar=[id_a])
        detalhe = client.get(reverse('consulta:detalhe_rad', args=[rad.numero_rad]), **_auth(token_adm)).json()
        assert [a['nome_original'] for a in detalhe['anexos']] == ['b.jpg']
        resposta = client.get(
            reverse('consulta:visualizar_anexo', args=[rad.numero_rad, id_a]), **_auth(token_adm)
        )
        assert resposta.status_code == 404
