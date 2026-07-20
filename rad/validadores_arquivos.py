"""
Validacao de anexos (fotos e PDF) — EFD secao 3.11 (RG-ANX) e secao
3.12 "Validacoes de Anexos" (VLD-023/024).

RG-ANX-002: apenas foto e documento PDF sao permitidos.
As fotos sao divididas em dois grupos com tema proprio, no maximo 3 cada
(6 no total, mas nunca misturados sem identificacao): "Intervencao
verificada" e "Acao realizada". RG-ANX-004: no maximo 1 PDF.
RG-ANX-005: 10MB por arquivo.
VLD-023/024: arquivo corrompido ou em formato invalido bloqueia o envio
-- checado de verdade (nao so pela extensao do nome do arquivo), abrindo
o conteudo com Pillow (fotos) e pypdf (PDF).
VLD-026: RAD sem nenhum anexo e permitido (anexos sao opcionais) --
por isso este modulo nunca gera erro por ausencia de arquivos.
"""
from django.conf import settings
from PIL import Image, UnidentifiedImageError
from pypdf import PdfReader
from pypdf.errors import PdfReadError


def _erro(codigo, campo, mensagem):
    return {'codigo': codigo, 'campo': campo, 'mensagem': mensagem}


def _validar_tamanho(arquivo, codigo, campo):
    limite = getattr(settings, 'LIMITE_TAMANHO_ARQUIVO_BYTES', 10 * 1024 * 1024)
    if arquivo.size > limite:
        limite_mb = limite // (1024 * 1024)
        return _erro(
            codigo, campo, f'O arquivo "{arquivo.name}" excede o limite de {limite_mb}MB.'
        )
    return None


def _validar_foto_individual(arquivo, campo):
    """
    VLD-023: tenta abrir e decodificar a imagem de verdade (Pillow).
    Arquivos renomeados para .jpg mas com conteudo invalido, ou
    truncados/corrompidos, falham aqui mesmo com extensao correta.
    """
    erro_tamanho = _validar_tamanho(arquivo, 'VLD-023', campo)
    if erro_tamanho:
        return erro_tamanho

    try:
        arquivo.seek(0)
        imagem = Image.open(arquivo)
        imagem.verify()  # detecta corrupcao sem carregar os pixels inteiros
    except (UnidentifiedImageError, OSError, ValueError):
        return _erro(
            'VLD-023',
            campo,
            f'O arquivo "{arquivo.name}" nao e uma foto valida ou esta corrompido.',
        )
    finally:
        arquivo.seek(0)
    return None


def _validar_pdf_individual(arquivo):
    """
    VLD-024: tenta ler a estrutura do PDF (pypdf). Detecta arquivos
    corrompidos, truncados, ou que nao sao PDF de verdade apesar da
    extensao/content-type declarado pelo cliente.
    """
    erro_tamanho = _validar_tamanho(arquivo, 'VLD-024', 'pdf')
    if erro_tamanho:
        return erro_tamanho

    try:
        arquivo.seek(0)
        leitor = PdfReader(arquivo)
        if len(leitor.pages) == 0:
            raise PdfReadError('PDF sem paginas')
    except (PdfReadError, ValueError, OSError):
        return _erro(
            'VLD-024', 'pdf', f'O arquivo "{arquivo.name}" nao e um PDF valido ou esta corrompido.'
        )
    finally:
        arquivo.seek(0)
    return None


def _validar_grupo_fotos(fotos, campo, codigo_limite, mensagem_limite):
    erros = []
    limite = getattr(settings, 'LIMITE_FOTOS_POR_CATEGORIA', 2)
    if len(fotos) > limite:
        erros.append(_erro(codigo_limite, campo, mensagem_limite))
    for foto in fotos:
        erro = _validar_foto_individual(foto, campo)
        if erro:
            erros.append(erro)
    return erros


def validar_anexos(fotos_intervencao, fotos_acao, pdfs):
    """
    fotos_intervencao: lista de UploadedFile do grupo "Intervencao
    verificada" (request.FILES.getlist('fotos_intervencao_verificada')).
    fotos_acao: lista de UploadedFile do grupo "Acao realizada"
    (request.FILES.getlist('fotos_acao_realizada')).
    pdfs: lista de UploadedFile (normalmente 0 ou 1 item).

    Os dois grupos de foto sao limitados e validados de forma
    independente -- um RAD pode ter 2 fotos de intervencao e 0 de acao,
    por exemplo, sem afetar o limite do outro grupo.

    Retorna a lista completa de erros (RG-VLD-002: nunca para no
    primeiro). Lista vazia = tudo valido, incluindo o caso de nenhum
    anexo enviado (VLD-026).
    """
    limite = getattr(settings, 'LIMITE_FOTOS_POR_CATEGORIA', 2)
    erros = []
    erros += _validar_grupo_fotos(
        fotos_intervencao,
        'fotos_intervencao_verificada',
        'ANX-003',
        f'No maximo {limite} fotos de "Intervenção verificada" sao permitidas por RAD.',
    )
    erros += _validar_grupo_fotos(
        fotos_acao,
        'fotos_acao_realizada',
        'ANX-003',
        f'No maximo {limite} fotos de "Ação realizada" sao permitidas por RAD.',
    )

    if len(pdfs) > getattr(settings, 'LIMITE_PDF_POR_RAD', 1):
        erros.append(
            _erro('ANX-004', 'pdf', 'No maximo 1 PDF e permitido por RAD.')
        )
    for pdf in pdfs:
        erro = _validar_pdf_individual(pdf)
        if erro:
            erros.append(erro)

    return erros
