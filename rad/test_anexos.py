"""
Testes de integracao de anexos: upload multipart no /rad/sincronizar/
(dois grupos de foto com categoria propria) e remocao (RG-ANX-011).
"""
import io
import json

import pytest
from django.core.files.storage import default_storage
from django.urls import reverse
from PIL import Image
from pypdf import PdfWriter

from catalogos.models import CatEquipe, CatLinha, CatLocal, CatServico, CatTipoManutencao, CatVia
from rad.models import Rad, RadAnexo
from usuarios.models import Token, Usuario, UsuarioPerfil


def _jpeg_valido(nome='foto.jpg'):
    from django.core.files.uploadedfile import SimpleUploadedFile

    buffer = io.BytesIO()
    Image.new('RGB', (10, 10), color='green').save(buffer, format='JPEG')
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type='image/jpeg')


def _jpeg_corrompido(nome='foto_ruim.jpg'):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(nome, b'nao-e-uma-imagem' * 10, content_type='image/jpeg')


def _pdf_valido(nome='doc.pdf'):
    from django.core.files.uploadedfile import SimpleUploadedFile

    buffer = io.BytesIO()
    escritor = PdfWriter()
    escritor.add_blank_page(width=100, height=100)
    escritor.write(buffer)
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type='application/pdf')


@pytest.fixture
def catalogo(db):
    return {
        'local': CatLocal.objects.create(sigla='BFU', nome='Barra Funda', categoria='estacao'),
        'linha': CatLinha.objects.create(codigo='11', nome='Coral'),
        'via': CatVia.objects.create(nome='Via 1'),
        'tipo_manutencao': CatTipoManutencao.objects.create(nome='Preventiva'),
        'equipe_vp': CatEquipe.objects.get_or_create(codigo='VP', defaults={'nome': 'VP'})[0],
        'servico': CatServico.objects.create(nome='Inspecao'),
    }


@pytest.fixture
def tecnico_com_token(db):
    usuario = Usuario.objects.create(login='tec.anexos')
    return usuario, Token.gerar_para(usuario)


@pytest.fixture
def administrador_com_token(db):
    usuario = Usuario.objects.create(login='admin.anexos')
    UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.ADMINISTRADOR)
    return usuario, Token.gerar_para(usuario)


def _dados_json(catalogo, sync_id):
    return json.dumps(
        {
            'numero_os': 9001,
            'numero_sa': '2468',
            'responsavel_atividade': 'Responsavel Teste',
            'data_preenchimento': '2026-06-15',
            'id_local_inicial': catalogo['local'].sigla,
            'id_local_final': catalogo['local'].sigla,
            'linhas': [catalogo['linha'].codigo],
            'vias': [catalogo['via'].id],
            'id_tipo_manutencao': catalogo['tipo_manutencao'].id,
            'hora_prog_inicio': '08:00',
            'hora_prog_termino': '12:00',
            'hora_real_inicio': '08:00',
            'hora_real_termino': '12:00',
            'servicos': [catalogo['servico'].id],
            'colaboradores': [{'registro_empresa': '1', 'nome': 'Tec', 'tipo': 'participante'}],
            'sync_id_tentativa': sync_id,
        }
    )


@pytest.mark.django_db
class TestUploadDeAnexos:
    def test_sincronizacao_com_fotos_dos_dois_grupos_e_pdf(
        self, client, tecnico_com_token, catalogo
    ):
        _, token = tecnico_com_token
        resposta = client.post(
            reverse('rad:sincronizar'),
            data={
                'dados': _dados_json(catalogo, 'anexos-ok'),
                'fotos_intervencao_verificada': [_jpeg_valido('int1.jpg'), _jpeg_valido('int2.jpg')],
                'fotos_acao_realizada': [_jpeg_valido('acao1.jpg')],
                'pdf': [_pdf_valido()],
            },
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )

        assert resposta.status_code == 201
        rad = Rad.objects.get(numero_rad=resposta.json()['numero_rad'])
        assert (
            rad.anexos.filter(categoria_foto=RadAnexo.INTERVENCAO_VERIFICADA).count() == 2
        )
        assert rad.anexos.filter(categoria_foto=RadAnexo.ACAO_REALIZADA).count() == 1
        assert rad.anexos.filter(tipo_arquivo=RadAnexo.PDF).count() == 1
        for anexo in rad.anexos.all():
            assert default_storage.exists(anexo.caminho_servidor)

    def test_foto_corrompida_em_um_grupo_bloqueia_sincronizacao_inteira(
        self, client, tecnico_com_token, catalogo
    ):
        """VLD-023 bloqueia o envio inteiro -- nem o RAD nem os outros anexos sao salvos."""
        _, token = tecnico_com_token
        resposta = client.post(
            reverse('rad:sincronizar'),
            data={
                'dados': _dados_json(catalogo, 'anexos-corrompido'),
                'fotos_intervencao_verificada': [_jpeg_valido('boa.jpg')],
                'fotos_acao_realizada': [_jpeg_corrompido()],
            },
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )

        assert resposta.status_code == 422
        codigos = {e['codigo'] for e in resposta.json()['erros']}
        assert 'VLD-023' in codigos
        assert Rad.objects.filter(sync_id_tentativa='anexos-corrompido').count() == 0
        assert RadAnexo.objects.count() == 0

    def test_sincronizacao_sem_anexos_continua_funcionando(
        self, client, tecnico_com_token, catalogo
    ):
        """VLD-026: RAD sem anexo e permitido."""
        _, token = tecnico_com_token
        resposta = client.post(
            reverse('rad:sincronizar'),
            data=_dados_json(catalogo, 'sem-anexos'),
            content_type='application/json',
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.status_code == 201

    def test_mais_de_2_fotos_em_um_grupo_bloqueia(self, client, tecnico_com_token, catalogo):
        _, token = tecnico_com_token
        resposta = client.post(
            reverse('rad:sincronizar'),
            data={
                'dados': _dados_json(catalogo, 'muitas-fotos'),
                'fotos_intervencao_verificada': [_jpeg_valido(f'f{i}.jpg') for i in range(3)],
            },
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.status_code == 422
        codigos = {e['codigo'] for e in resposta.json()['erros']}
        assert 'ANX-003' in codigos

    def test_2_fotos_em_cada_grupo_nao_bloqueia(self, client, tecnico_com_token, catalogo):
        """Os limites sao por grupo: 2+2=4 no total e valido."""
        _, token = tecnico_com_token
        resposta = client.post(
            reverse('rad:sincronizar'),
            data={
                'dados': _dados_json(catalogo, 'quatro-fotos-dois-grupos'),
                'fotos_intervencao_verificada': [_jpeg_valido(f'i{i}.jpg') for i in range(2)],
                'fotos_acao_realizada': [_jpeg_valido(f'a{i}.jpg') for i in range(2)],
            },
            HTTP_AUTHORIZATION=f'Token {token.token}',
        )
        assert resposta.status_code == 201


@pytest.mark.django_db
class TestRemoverAnexo:
    def _criar_rad_com_anexo(self, client, tecnico_token, catalogo, sync_id):
        resposta = client.post(
            reverse('rad:sincronizar'),
            data={
                'dados': _dados_json(catalogo, sync_id),
                'fotos_intervencao_verificada': [_jpeg_valido()],
            },
            HTTP_AUTHORIZATION=f'Token {tecnico_token.token}',
        )
        assert resposta.status_code == 201
        numero_rad = resposta.json()['numero_rad']
        anexo = Rad.objects.get(numero_rad=numero_rad).anexos.first()
        return numero_rad, anexo

    def test_administrador_remove_anexo_com_sucesso(
        self, client, tecnico_com_token, administrador_com_token, catalogo
    ):
        _, token_tecnico = tecnico_com_token
        _, token_admin = administrador_com_token
        numero_rad, anexo = self._criar_rad_com_anexo(
            client, token_tecnico, catalogo, 'remover-ok'
        )
        caminho = anexo.caminho_servidor

        resposta = client.post(
            reverse('rad:remover_anexo', args=[numero_rad, anexo.id]),
            HTTP_AUTHORIZATION=f'Token {token_admin.token}',
        )

        assert resposta.status_code == 200
        assert not RadAnexo.objects.filter(id=anexo.id).exists()
        assert not default_storage.exists(caminho)

    def test_rg_anx_011_usuario_comum_nao_pode_remover(
        self, client, tecnico_com_token, catalogo
    ):
        _, token_tecnico = tecnico_com_token
        numero_rad, anexo = self._criar_rad_com_anexo(
            client, token_tecnico, catalogo, 'remover-negado'
        )

        resposta = client.post(
            reverse('rad:remover_anexo', args=[numero_rad, anexo.id]),
            HTTP_AUTHORIZATION=f'Token {token_tecnico.token}',
        )

        assert resposta.status_code == 403
        assert RadAnexo.objects.filter(id=anexo.id).exists()

    def test_remover_anexo_inexistente_retorna_404(
        self, client, administrador_com_token, tecnico_com_token, catalogo
    ):
        _, token_admin = administrador_com_token
        _, token_tecnico = tecnico_com_token
        numero_rad, _ = self._criar_rad_com_anexo(
            client, token_tecnico, catalogo, 'remover-404'
        )

        resposta = client.post(
            reverse('rad:remover_anexo', args=[numero_rad, 999999]),
            HTTP_AUTHORIZATION=f'Token {token_admin.token}',
        )
        assert resposta.status_code == 404
