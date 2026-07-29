"""
Exportacao no layout do documento RDA oficial da TRIVIA
(RDA_Relatorio_Trivia_Ajustado_original.docx, fornecido pelo cliente
em 22/07/2026), usado como molde exato (mesmo cabecalho, cores, caixas
de selecao) em vez do layout simples gerado no navegador
(exportar_cliente.js / rad/exportacao.py).

O molde tokenizado fica em rad/templates_export/rda_oficial_template.docx
-- e uma copia do documento original com os valores de exemplo trocados
por marcadores {{TOKEN}}. Esta funcao abre o molde, substitui os
marcadores pelos dados reais do RAD, reconstroi a tabela "Atividades
Executadas" com a lista real de Servicos do RAD Digital (o documento
original tinha uma lista fixa de 19 itens especifica de outro
contexto, que nao existe no cadastro atual -- ver conversa de
22/07/2026) e insere as fotos anexadas nos espacos do "Relatorio
Fotografico".

Limitacoes conhecidas (a resolver com o cliente):
- "RESPONSAVEL RAD" e preenchido automaticamente com o nome de quem
  sincronizou o RAD (consulta.views.nome_de_quem_preencheu) -- decisao
  do cliente em 22/07/2026, substitui o antigo campo digitado
  manualmente "Equipe TRIVIA".
- "Conclusao e Liberacao da Via" nao tem campo correspondente no RAD
  Digital ainda -- fica com um aviso de pendencia no lugar do texto.
- O molde tem espaco para 1 foto de "Intervencao Verificada" e 2 fotos
  de "Acao Realizada" (herdado do documento original). O RAD Digital
  permite ate 2 fotos por categoria -- a 2a foto de "Intervencao
  Verificada", se houver, fica de fora deste layout especifico ate
  o molde ganhar uma linha extra.
"""
import io
import os

from django.conf import settings
from docx import Document
from docx.shared import Cm
from PIL import Image

CAMINHO_TEMPLATE = os.path.join(
    settings.BASE_DIR, 'rad', 'templates_export', 'rda_oficial_template.docx'
)

# Nomes dos servicos, na mesma ordem/regra usada no formulario
# (rad_form.js::ordenarComOutrosPorUltimo): alfabetica, "Outros" por
# ultimo. Buscados do catalogo real a cada chamada -- se um servico
# novo for cadastrado, aparece aqui automaticamente, sem precisar
# tocar neste arquivo.
ITENS_POR_LINHA_CHECKLIST = 4


def _texto_completo_paragrafo(paragrafo):
    return ''.join(run.text for run in paragrafo.runs)


def _substituir_no_paragrafo(paragrafo, de, para):
    """
    Troca 'de' por 'para' no texto de um paragrafo, mesmo quando o
    texto esta fragmentado em varios <w:r> (comum em docx editados no
    Word). Concatena todos os runs, faz a troca, e realoca o resultado
    no primeiro run -- os demais ficam vazios (nao remove os runs para
    nao perder formatacao caso o paragrafo seja reutilizado).
    """
    texto_atual = _texto_completo_paragrafo(paragrafo)
    if de not in texto_atual:
        return False
    novo_texto = texto_atual.replace(de, para)
    if paragrafo.runs:
        paragrafo.runs[0].text = novo_texto
        for run in paragrafo.runs[1:]:
            run.text = ''
    return True


def _substituir_no_documento(doc, de, para):
    """Aplica _substituir_no_paragrafo em todas as celulas de todas as tabelas."""
    encontrado = False
    for tabela in doc.tables:
        for linha in tabela.rows:
            celulas_unicas = []
            ids_vistos = set()
            for celula in linha.cells:
                if id(celula._tc) in ids_vistos:
                    continue
                ids_vistos.add(id(celula._tc))
                celulas_unicas.append(celula)
            for celula in celulas_unicas:
                for paragrafo in celula.paragraphs:
                    if _substituir_no_paragrafo(paragrafo, de, para):
                        encontrado = True
    return encontrado


def _celulas_unicas_da_linha(linha):
    vistas = []
    ids = set()
    for celula in linha.cells:
        if id(celula._tc) in ids:
            continue
        ids.add(id(celula._tc))
        vistas.append(celula)
    return vistas


def _limpar_texto_celula(celula, novo_texto):
    paragrafo = celula.paragraphs[0]
    if paragrafo.runs:
        paragrafo.runs[0].text = novo_texto
        for run in paragrafo.runs[1:]:
            run.text = ''
    else:
        paragrafo.add_run(novo_texto)


def _reconstruir_checklist_servicos(doc, ids_servicos_selecionados):
    """
    Localiza a tabela de "Atividades Executadas" (unica tabela do
    documento) e substitui as linhas de checklist originais (lista
    fixa de 19 itens que nao existe no RAD Digital) pela lista real de
    Servicos do catalogo, marcando [X] nos que foram selecionados
    neste RAD.
    """
    from catalogos.models import CatServico

    servicos = list(CatServico.objects.filter(ativo=True).order_by('nome'))
    sem_outros = [s for s in servicos if s.nome != 'Outros']
    outros = [s for s in servicos if s.nome == 'Outros']
    servicos_ordenados = sem_outros + outros

    tabela = doc.tables[0]
    linhas_xml = tabela._tbl.findall(
        './/{http://schemas.openxmlformats.org/wordprocessingml/2006/main}tr'
    )

    # Acha o indice da primeira linha do checklist procurando pelo
    # texto de uma das celulas (mais resistente a mudanca de posicao
    # do que um indice fixo, caso o molde seja editado no futuro).
    indice_primeira_linha_checklist = None
    indice_ultima_linha_checklist = None
    for indice, linha in enumerate(tabela.rows):
        texto_linha = linha.cells[0].text
        if texto_linha.startswith('[') and indice_primeira_linha_checklist is None:
            indice_primeira_linha_checklist = indice
        elif indice_primeira_linha_checklist is not None and not texto_linha.startswith('['):
            indice_ultima_linha_checklist = indice - 1
            break

    if indice_primeira_linha_checklist is None:
        # Nao achou o padrao esperado -- nao mexe em nada em vez de
        # arriscar corromper o documento.
        return

    linha_modelo_xml = linhas_xml[indice_primeira_linha_checklist]

    # Gera as novas linhas (clones da linha-modelo, so trocando o
    # texto de cada uma das 4 celulas unicas).
    novas_linhas_xml = []
    for inicio in range(0, len(servicos_ordenados), ITENS_POR_LINHA_CHECKLIST):
        grupo = servicos_ordenados[inicio:inicio + ITENS_POR_LINHA_CHECKLIST]
        nova_linha_xml = copy_element(linha_modelo_xml)
        tabela_temp_row = _TrWrapper(nova_linha_xml, tabela)
        celulas = _celulas_unicas_da_linha(tabela_temp_row)
        for posicao, celula in enumerate(celulas):
            if posicao < len(grupo):
                servico = grupo[posicao]
                marca = 'X' if servico.id in ids_servicos_selecionados else ' '
                _limpar_texto_celula(celula, f'[{marca}] {servico.nome}')
            else:
                _limpar_texto_celula(celula, '')
        novas_linhas_xml.append(nova_linha_xml)

    # Remove as linhas antigas do checklist e insere as novas no
    # mesmo lugar.
    linha_de_referencia = linhas_xml[indice_primeira_linha_checklist]
    for indice in range(indice_ultima_linha_checklist, indice_primeira_linha_checklist - 1, -1):
        linhas_xml[indice].getparent().remove(linhas_xml[indice])

    elemento_pai = linha_de_referencia.getparent()
    ancora = None
    for nova_linha in novas_linhas_xml:
        if ancora is None:
            # a linha de referencia ja foi removida; usa o proximo
            # irmao remanescente como ponto de insercao, ou anexa no
            # fim se nao houver mais linhas depois do checklist.
            elemento_pai.append(nova_linha)
        else:
            ancora.addnext(nova_linha)
        ancora = nova_linha


class _TrWrapper:
    """Wrapper minimo para reaproveitar _celulas_unicas_da_linha em um <w:tr> solto (fora da tabela real)."""

    def __init__(self, tr_element, tabela):
        from docx.table import _Row
        self._linha_docx = _Row(tr_element, tabela)

    @property
    def cells(self):
        return self._linha_docx.cells


def copy_element(elemento):
    import copy as copy_module
    return copy_module.deepcopy(elemento)


def _inserir_foto_na_celula(celula, caminho_arquivo, largura_cm=7):
    """
    Substitui o texto de placeholder por uma imagem de verdade,
    redimensionada para caber na largura da coluna. Mantem o
    paragrafo existente (mesma formatacao/alinhamento centralizado do
    molde) em vez de criar um novo.
    """
    paragrafo = celula.paragraphs[0]
    for run in paragrafo.runs:
        run.text = ''
    # Remove paragrafos extras da celula (algumas tem 2, por causa do
    # texto de instrucao em 2 linhas no molde original).
    for p_extra in celula.paragraphs[1:]:
        p_extra._p.getparent().remove(p_extra._p)

    run = paragrafo.add_run()
    run.add_picture(caminho_arquivo, width=Cm(largura_cm))


def gerar_docx_oficial_bytes(rad):
    """
    Gera o .docx no layout oficial da TRIVIA para um RAD ja
    sincronizado. Retorna os bytes prontos para download.
    """
    from django.core.files.storage import default_storage

    from consulta.views import nome_de_quem_preencheu

    doc = Document(CAMINHO_TEMPLATE)

    def na(valor):
        return valor if valor not in (None, '') else 'N/A'

    substituicoes = {
        '{{ATIVIDADE}}': na(rad.descricao_tecnica_atividade)[:200],
        '{{OS}}': str(rad.numero_os),
        '{{LOCAL}}': f'{rad.local_inicial.sigla} / {rad.local_final.sigla}',
        '{{RESP_ATIVIDADE}}': na(rad.responsavel_atividade),
        '{{DATA}}': rad.data_preenchimento.strftime('%d/%m/%Y'),
        '{{SA}}': rad.numero_sa,
        '{{SOLICITANTE_SA}}': na(rad.solicitante_sa),
        '{{OPERADOR_CCM}}': na(rad.operador_ccm),
        '{{RESPONSAVEL_RAD}}': nome_de_quem_preencheu(rad),
        '{{H_PROGRAMADO}}': f'{rad.hora_prog_inicio.strftime("%H:%M")} às {rad.hora_prog_termino.strftime("%H:%M")}',
        '{{H_EXECUTADO}}': f'{rad.hora_real_inicio.strftime("%H:%M")} às {rad.hora_real_termino.strftime("%H:%M")}',
        '{{DESCRICAO_TECNICA}}': na(rad.descricao_tecnica_atividade),
        '{{CONCLUSAO}}': (
            'Não há um campo "Conclusão e Liberação da Via" no RAD Digital ainda. '
            'Consulte as Observações Gerais abaixo, se preenchidas.'
        ),
        '{{OBSERVACOES_FOTOS}}': na(rad.observacoes_gerais),
    }

    vias_selecionadas = set(rad.vias.values_list('via__nome', flat=True))
    for numero in (1, 2, 3, 4):
        marcado = f'Via {numero}' in vias_selecionadas
        substituicoes[f'{{{{CB_VIA{numero}}}}}'] = '[X]' if marcado else '[  ]'

    linhas_selecionadas = set(rad.linhas.values_list('linha_id', flat=True))
    for codigo in ('11', '12', '13'):
        marcado = codigo in linhas_selecionadas
        substituicoes[f'{{{{CB_LINHA{codigo}}}}}'] = '[X]' if marcado else '[  ]'

    equipes_selecionadas = set(rad.equipes.values_list('equipe_id', flat=True))
    for codigo, token in (('RA', 'CB_RA'), ('VP', 'CB_VP'), ('CIVIL', 'CB_CIVIL'), ('RESTAB', 'CB_RESTAB')):
        marcado = codigo in equipes_selecionadas
        substituicoes[f'{{{{{token}}}}}'] = '[X]' if marcado else '[  ]'

    colaboradores = list(rad.colaboradores.all())
    substituicoes['{{NOMES_COLABORADORES}}'] = (
        ' / '.join(c.nome for c in colaboradores) if colaboradores else 'N/A'
    )
    substituicoes['{{MATRICULAS_COLABORADORES}}'] = (
        ' / '.join(c.registro_empresa or 'Participante' for c in colaboradores)
        if colaboradores else 'N/A'
    )

    for token, valor in substituicoes.items():
        _substituir_no_documento(doc, token, valor)

    ids_servicos_selecionados = set(rad.servicos.values_list('servico_id', flat=True))
    _reconstruir_checklist_servicos(doc, ids_servicos_selecionados)

    # Fotos: mapeia para os 3 espacos que o molde original tem
    # (1 Intervencao Verificada + 2 Acao Realizada -- ver limitacao no
    # docstring do modulo).
    anexos_intervencao = [a for a in rad.anexos.all() if a.categoria_foto == 'intervencao_verificada']
    anexos_acao = [a for a in rad.anexos.all() if a.categoria_foto == 'acao_realizada']

    tabela = doc.tables[0]
    for linha in tabela.rows:
        celulas = _celulas_unicas_da_linha(linha)
        for celula in celulas:
            if 'FOTO 1' in celula.text and anexos_intervencao:
                with default_storage.open(anexos_intervencao[0].caminho_servidor, 'rb') as arquivo:
                    _inserir_foto_temp(celula, arquivo)
            elif 'FOTO 2' in celula.text and anexos_acao:
                with default_storage.open(anexos_acao[0].caminho_servidor, 'rb') as arquivo:
                    _inserir_foto_temp(celula, arquivo)
            elif 'FOTO 4' in celula.text and len(anexos_acao) > 1:
                with default_storage.open(anexos_acao[1].caminho_servidor, 'rb') as arquivo:
                    _inserir_foto_temp(celula, arquivo)

    buffer_saida = io.BytesIO()
    doc.save(buffer_saida)
    return buffer_saida.getvalue()


def _inserir_foto_temp(celula, arquivo_django):
    """
    python-docx precisa de um caminho de arquivo ou objeto tipo-arquivo
    seekable; grava em um buffer de memoria para nao depender do tipo
    exato de storage configurado (local em dev, outro em producao).
    """
    conteudo = arquivo_django.read()
    buffer_imagem = io.BytesIO(conteudo)
    try:
        imagem = Image.open(buffer_imagem)
        imagem.verify()
    except Exception:
        return  # arquivo corrompido -- nao trava a exportacao inteira por causa de 1 foto
    buffer_imagem.seek(0)
    _inserir_foto_na_celula(celula, buffer_imagem)
