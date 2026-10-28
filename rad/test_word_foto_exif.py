"""
Word oficial com foto de EXIF defeituoso (28/10/2026, bug real R00459).

O Pillow abre a foto (passa na sincronizacao), mas o python-docx le o
EXIF sozinho e quebrava com UnexpectedEndOfFileError -> erro 500 ao
baixar o Word. Agora a foto e regravada limpa antes de entrar no Word.
"""
import io
import struct
import zipfile

import pytest
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from rad.exportacao_oficial import CAMINHO_TEMPLATE, LADO_MAXIMO_FOTO_PX, gerar_docx_oficial_bytes
from rad.test_edicao_rad import _sincronizar, tecnico  # noqa: F401
from rad.test_numero_os import _payload, catalogo  # noqa: F401


def _jpeg_com_exif_defeituoso(tamanho=(400, 300), orientacao=None):
    """JPEG valido para o Pillow, com um campo do EXIF apontando para fora do arquivo."""
    exif = Image.Exif()
    exif[0x010F] = 'FabricanteTesteLongo'  # texto > 4 bytes: fica guardado por "endereco"
    if orientacao:
        exif[0x0112] = orientacao
    buffer = io.BytesIO()
    Image.new('RGB', tamanho, 'green').save(buffer, 'JPEG', exif=exif.tobytes())
    dados = bytearray(buffer.getvalue())
    inicio = dados.find(b'Exif\x00\x00') + 6
    ordem = '<' if dados[inicio:inicio + 2] == b'II' else '>'
    ifd = inicio + struct.unpack(ordem + 'I', dados[inicio + 4:inicio + 8])[0]
    for k in range(struct.unpack(ordem + 'H', dados[ifd:ifd + 2])[0]):
        entrada = ifd + 2 + 12 * k
        if struct.unpack(ordem + 'H', dados[entrada:entrada + 2])[0] == 0x010F:
            dados[entrada + 8:entrada + 12] = struct.pack(ordem + 'I', 60000)
    return bytes(dados)


def _midias(z):
    return {z.read(n) for n in z.namelist() if n.startswith('word/media/')}


def _imagens_do_docx(docx_bytes):
    """So as fotos do RAD -- ignora as imagens que ja vem no molde (logo)."""
    with zipfile.ZipFile(CAMINHO_TEMPLATE) as molde:
        do_molde = _midias(molde)
    with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
        return [m for m in _midias(z) if m not in do_molde]


def _sincronizar_com_foto(client, catalogo, tecnico, conteudo, sync_id):  # noqa: F811
    _, token = tecnico
    foto = SimpleUploadedFile('foto.jpg', conteudo, content_type='image/jpeg')
    return _sincronizar(client, token, _payload(catalogo, sync_id_tentativa=sync_id), fotos=[foto])


@pytest.mark.django_db
class TestFotoNoWord:
    def test_foto_com_exif_defeituoso_nao_derruba_o_word(self, client, catalogo, tecnico):  # noqa: F811
        rad = _sincronizar_com_foto(client, catalogo, tecnico, _jpeg_com_exif_defeituoso(), 'exif-1')
        imagens = _imagens_do_docx(gerar_docx_oficial_bytes(rad))
        assert len(imagens) == 1
        assert Image.open(io.BytesIO(imagens[0])).format == 'JPEG'

    def test_foto_grande_e_reduzida(self, client, catalogo, tecnico):  # noqa: F811
        rad = _sincronizar_com_foto(
            client, catalogo, tecnico, _jpeg_com_exif_defeituoso(tamanho=(4000, 3000)), 'exif-2'
        )
        imagem = Image.open(io.BytesIO(_imagens_do_docx(gerar_docx_oficial_bytes(rad))[0]))
        assert max(imagem.size) <= LADO_MAXIMO_FOTO_PX

    def test_rotacao_do_celular_e_respeitada(self, client, catalogo, tecnico):  # noqa: F811
        # Orientacao 6 = celular de pe: a foto gravada "deitada" deve sair em pe.
        buffer = io.BytesIO()
        exif = Image.Exif()
        exif[0x0112] = 6
        Image.new('RGB', (400, 300), 'green').save(buffer, 'JPEG', exif=exif.tobytes())
        rad = _sincronizar_com_foto(client, catalogo, tecnico, buffer.getvalue(), 'exif-3')
        largura, altura = Image.open(io.BytesIO(_imagens_do_docx(gerar_docx_oficial_bytes(rad))[0])).size
        assert altura > largura

    def test_arquivo_ilegivel_vira_aviso_e_o_word_sai(self, client, catalogo, tecnico):  # noqa: F811
        rad = _sincronizar_com_foto(client, catalogo, tecnico, _jpeg_com_exif_defeituoso(), 'exif-4')
        anexo = rad.anexos.first()
        default_storage.delete(anexo.caminho_servidor)
        default_storage.save(anexo.caminho_servidor, io.BytesIO(b'isto nao e uma imagem'))
        docx_bytes = gerar_docx_oficial_bytes(rad)
        assert _imagens_do_docx(docx_bytes) == []
        with zipfile.ZipFile(io.BytesIO(docx_bytes)) as z:
            assert 'Foto não pôde ser inserida' in z.read('word/document.xml').decode('utf-8')
