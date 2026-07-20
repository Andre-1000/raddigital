"""
Testes de rad/validadores_arquivos.py — VLD-023/024 e RG-ANX-003/004/005.

Os arquivos "validos" sao gerados de verdade em memoria (Pillow/pypdf),
e os "corrompidos" sao bytes aleatorios com extensao enganosa --
provando que a validacao olha o CONTEUDO, nao so o nome do arquivo.

As fotos sao dois grupos independentes: "Intervencao verificada" e
"Acao realizada", cada um limitado a 2 fotos (4 no total).
"""
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from pypdf import PdfWriter

from rad.validadores_arquivos import validar_anexos


def _jpeg_valido(nome='foto.jpg'):
    buffer = io.BytesIO()
    Image.new('RGB', (10, 10), color='red').save(buffer, format='JPEG')
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type='image/jpeg')


def _jpeg_corrompido(nome='foto_corrompida.jpg'):
    """Bytes aleatorios com extensao .jpg -- nao e uma imagem de verdade."""
    return SimpleUploadedFile(nome, b'isto-nao-e-uma-imagem-de-verdade' * 10, content_type='image/jpeg')


def _pdf_valido(nome='documento.pdf'):
    buffer = io.BytesIO()
    escritor = PdfWriter()
    escritor.add_blank_page(width=200, height=200)
    escritor.write(buffer)
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type='application/pdf')


def _pdf_corrompido(nome='documento_corrompido.pdf'):
    return SimpleUploadedFile(nome, b'isto-nao-e-um-pdf-de-verdade' * 10, content_type='application/pdf')


def _pdf_sem_paginas(nome='documento_vazio.pdf'):
    """PDF com estrutura valida (pypdf le sem erro), mas zero paginas."""
    buffer = io.BytesIO()
    PdfWriter().write(buffer)
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type='application/pdf')


def _arquivo_grande(nome='foto_grande.jpg', tamanho_bytes=11 * 1024 * 1024):
    return SimpleUploadedFile(nome, b'0' * tamanho_bytes, content_type='image/jpeg')


def _pdf_grande(nome='documento_grande.pdf', tamanho_bytes=11 * 1024 * 1024):
    return SimpleUploadedFile(nome, b'%PDF-1.4' + b'0' * tamanho_bytes, content_type='application/pdf')


class TestFotosValidas:
    def test_foto_valida_de_intervencao_nao_gera_erro(self):
        assert validar_anexos([_jpeg_valido()], [], []) == []

    def test_foto_valida_de_acao_nao_gera_erro(self):
        assert validar_anexos([], [_jpeg_valido()], []) == []

    def test_ate_2_fotos_por_grupo_nao_gera_erro(self):
        intervencao = [_jpeg_valido(f'int{i}.jpg') for i in range(2)]
        acao = [_jpeg_valido(f'acao{i}.jpg') for i in range(2)]
        assert validar_anexos(intervencao, acao, []) == []

    def test_2_de_cada_grupo_totalizando_4_e_valido(self):
        """Os grupos sao independentes: 2+2=4 no total, sem violar limite nenhum."""
        intervencao = [_jpeg_valido(f'int{i}.jpg') for i in range(2)]
        acao = [_jpeg_valido(f'acao{i}.jpg') for i in range(2)]
        assert validar_anexos(intervencao, acao, []) == []


class TestFotosInvalidas:
    def test_vld_023_foto_corrompida_de_intervencao_bloqueia(self):
        erros = validar_anexos([_jpeg_corrompido()], [], [])
        assert any(e['codigo'] == 'VLD-023' for e in erros)

    def test_vld_023_foto_corrompida_de_acao_bloqueia(self):
        erros = validar_anexos([], [_jpeg_corrompido()], [])
        assert any(e['codigo'] == 'VLD-023' for e in erros)

    def test_anx_003_mais_de_2_fotos_de_intervencao_bloqueia(self):
        fotos = [_jpeg_valido(f'int{i}.jpg') for i in range(3)]
        erros = validar_anexos(fotos, [], [])
        assert any(
            e['codigo'] == 'ANX-003' and e['campo'] == 'fotos_intervencao_verificada'
            for e in erros
        )

    def test_anx_003_mais_de_2_fotos_de_acao_bloqueia(self):
        fotos = [_jpeg_valido(f'acao{i}.jpg') for i in range(3)]
        erros = validar_anexos([], fotos, [])
        assert any(
            e['codigo'] == 'ANX-003' and e['campo'] == 'fotos_acao_realizada' for e in erros
        )

    def test_grupo_intervencao_cheio_nao_afeta_limite_do_grupo_acao(self):
        """Os limites sao independentes por grupo -- 2 de intervencao + 2 de acao nao bloqueia."""
        intervencao = [_jpeg_valido(f'int{i}.jpg') for i in range(2)]
        acao = [_jpeg_valido(f'acao{i}.jpg') for i in range(2)]
        assert validar_anexos(intervencao, acao, []) == []

    def test_foto_acima_de_10mb_bloqueia(self):
        erros = validar_anexos([_arquivo_grande()], [], [])
        assert any(e['codigo'] == 'VLD-023' for e in erros)


class TestPdfValido:
    def test_pdf_valido_nao_gera_erro(self):
        assert validar_anexos([], [], [_pdf_valido()]) == []


class TestPdfInvalido:
    def test_vld_024_pdf_corrompido_bloqueia(self):
        erros = validar_anexos([], [], [_pdf_corrompido()])
        assert any(e['codigo'] == 'VLD-024' for e in erros)

    def test_anx_004_mais_de_1_pdf_bloqueia(self):
        erros = validar_anexos([], [], [_pdf_valido('a.pdf'), _pdf_valido('b.pdf')])
        assert any(e['codigo'] == 'ANX-004' for e in erros)

    def test_imagem_renomeada_para_pdf_e_detectada_como_invalida(self):
        """Prova que a validacao olha o conteudo, nao a extensao do nome."""
        buffer = io.BytesIO()
        Image.new('RGB', (10, 10), color='blue').save(buffer, format='JPEG')
        arquivo_disfarcado = SimpleUploadedFile(
            'na_verdade_e_foto.pdf', buffer.getvalue(), content_type='application/pdf'
        )
        erros = validar_anexos([], [], [arquivo_disfarcado])
        assert any(e['codigo'] == 'VLD-024' for e in erros)

    def test_vld_024_pdf_acima_de_10mb_bloqueia(self):
        erros = validar_anexos([], [], [_pdf_grande()])
        assert any(e['codigo'] == 'VLD-024' for e in erros)

    def test_vld_024_pdf_sem_paginas_bloqueia(self):
        """
        Um PDF pode ter estrutura tecnicamente valida (pypdf le sem
        levantar excecao) mas zero paginas -- efetivamente um anexo
        vazio/inutil. Precisa ser rejeitado tambem, nao so PDFs
        corrompidos de verdade.
        """
        erros = validar_anexos([], [], [_pdf_sem_paginas()])
        assert any(e['codigo'] == 'VLD-024' for e in erros)


class TestSemAnexos:
    def test_vld_026_rad_sem_anexo_nao_bloqueia(self):
        assert validar_anexos([], [], []) == []
