"""
Integracao com Google Sheets -- 30/09/2026. Envia os dados dos RADs
para uma planilha do Google (1 RAD = 1 linha), pensada como uma base
de dados externa/backup consultavel fora do sistema.

Configuracao (variaveis de ambiente, nunca no codigo):
  GOOGLE_SHEETS_SPREADSHEET_ID -- ID da planilha (o trecho da URL
    entre '/d/' e '/edit'), compartilhada previamente com o e-mail da
    conta de servico, permissao Editor (mesma conta ja usada em
    rad/google_drive.py -- ver client_email dentro do JSON de
    GOOGLE_DRIVE_CREDENTIALS_JSON, reaproveitado aqui tambem).
  GOOGLE_SHEETS_ABA -- nome da aba onde as linhas entram. Opcional,
    default 'Página1' (nome padrao de aba nova do Google Sheets).

Sem GOOGLE_SHEETS_SPREADSHEET_ID definida, a funcionalidade fica
indisponivel de forma controlada -- ver esta_configurado() e
SheetsNaoConfiguradoError. Reaproveita GOOGLE_DRIVE_CREDENTIALS_JSON
(mesma conta de servico do Drive) -- nao precisa de um segundo JSON.

Nao ha checagem de duplicata aqui (ao contrario de
rad/google_drive.py::arquivo_existe_no_drive) -- quem decide quais
RADs mandar e o CHAMADOR (dashboard/views.py::sync_bd_sincronizar),
filtrando por Rad.data_ultima_sincronizacao_planilha antes de chegar
aqui. Este modulo so sabe escrever linhas, nunca decide quais.
"""
import datetime
import json
import os

_ESCOPOS = ['https://www.googleapis.com/auth/spreadsheets']
ABA_PADRAO = 'Página1'


class SheetsNaoConfiguradoError(Exception):
    """As variaveis de ambiente da planilha nao estao configuradas."""


def esta_configurado():
    return bool(
        os.getenv('GOOGLE_DRIVE_CREDENTIALS_JSON') and os.getenv('GOOGLE_SHEETS_SPREADSHEET_ID')
    )


def _obter_servico():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    # Mesmo JSON de credenciais do Drive (rad/google_drive.py) -- e a
    # mesma conta de servico, so pedindo um escopo diferente aqui
    # (spreadsheets em vez de drive.file).
    credenciais_dict = json.loads(os.environ['GOOGLE_DRIVE_CREDENTIALS_JSON'])
    credenciais = service_account.Credentials.from_service_account_info(
        credenciais_dict, scopes=_ESCOPOS
    )
    return build('sheets', 'v4', credentials=credenciais, cache_discovery=False)


def _valor_para_celula(valor):
    """
    A API do Sheets exige valores prontos pra virar JSON -- ao
    contrario do openpyxl (usado no Excel, ver
    rad/exportacao_excel.py), que aceita objetos date/time/datetime
    do Python direto. date/time/datetime viram texto ISO; o resto
    passa direto (numero, string, ja vem formatado como texto pelas
    proprias funcoes de rad/exportacao_excel.py).
    """
    if valor is None or valor == '':
        return ''
    if isinstance(valor, (datetime.datetime, datetime.date, datetime.time)):
        return valor.isoformat()
    return valor


def montar_linha(rad):
    """
    Monta uma linha (lista de valores, na ordem das colunas) para UM
    RAD, reaproveitando a MESMA fonte de dados do Excel
    (rad.exportacao_excel.COLUNAS/_linha_para_rad) -- e o que garante
    que a planilha sempre tenha "todas as informacoes inseridas no
    RAD": e o mesmo lugar que ja precisa ser atualizado sempre que um
    campo novo for adicionado ao formulario, entao a planilha ganha a
    coluna nova junto, sem duplicar essa logica em dois lugares.

    IMPORTANTE: ao adicionar/remover uma coluna em COLUNAS, a
    PLANILHA tambem precisa ganhar essa coluna no cabecalho (linha 1),
    na mesma posicao -- isso NAO e automatico, o Google Sheets nao
    reorganiza colunas sozinho.

    `rad` deve vir com select_related/prefetch_related ja aplicados
    pelo chamador (mesma exigencia de gerar_excel_bytes).
    """
    from rad.exportacao_excel import COLUNAS, _linha_para_rad

    dados = _linha_para_rad(rad)
    return [_valor_para_celula(dados.get(chave)) for chave, _ in COLUNAS]


def enviar_linhas(linhas):
    """
    Envia um LOTE de linhas (lista de listas, cada uma ja no formato
    de montar_linha) para a planilha, numa unica chamada a API
    (values().append()) -- o Google encontra sozinho a proxima linha
    vazia da aba, sem precisar calcular isso aqui.

    Levanta SheetsNaoConfiguradoError se as variaveis de ambiente nao
    estiverem definidas. Nao faz nada (nao levanta erro) se `linhas`
    vier vazia -- evita uma chamada a API a toa.
    """
    if not linhas:
        return

    if not esta_configurado():
        raise SheetsNaoConfiguradoError(
            'Integração com Google Sheets não configurada. Contate o Administrador.'
        )

    aba = os.getenv('GOOGLE_SHEETS_ABA') or ABA_PADRAO
    servico = _obter_servico()
    servico.spreadsheets().values().append(
        spreadsheetId=os.environ['GOOGLE_SHEETS_SPREADSHEET_ID'],
        range=f"'{aba}'!A1",
        valueInputOption='USER_ENTERED',
        insertDataOption='INSERT_ROWS',
        body={'values': linhas},
    ).execute()


def atualizar_linhas(pares):
    """
    13/10/2026: atualiza, na planilha, as linhas de RADs que JA foram
    enviados antes e depois foram editados pelo Administrador.

    pares: lista de (numero_rad, linha) -- `linha` no formato de
    montar_linha. A coluna A da planilha e o "Número RAD" (primeira
    coluna de rad.exportacao_excel.COLUNAS) e e por ela que a linha e
    localizada: le a coluna A inteira numa unica chamada e acha a
    posicao de cada RAD. Se um RAD nao for encontrado (linha apagada a
    mao na planilha, por exemplo), ele e ACRESCENTADO no fim em vez de
    ser ignorado -- assim a planilha nunca fica sem o RAD. Se o mesmo
    numero aparecer em mais de uma linha (envio duplicado antigo),
    atualiza a PRIMEIRA ocorrencia.

    Retorna (atualizadas, acrescentadas). Levanta
    SheetsNaoConfiguradoError se nao estiver configurado.
    """
    if not pares:
        return 0, 0

    if not esta_configurado():
        raise SheetsNaoConfiguradoError(
            'Integração com Google Sheets não configurada. Contate o Administrador.'
        )

    aba = os.getenv('GOOGLE_SHEETS_ABA') or ABA_PADRAO
    id_planilha = os.environ['GOOGLE_SHEETS_SPREADSHEET_ID']
    servico = _obter_servico()

    coluna_a = servico.spreadsheets().values().get(
        spreadsheetId=id_planilha, range=f"'{aba}'!A:A",
    ).execute().get('values', [])

    posicao_por_rad = {}
    for indice, linha_a in enumerate(coluna_a, start=1):
        if linha_a and indice > 1:  # linha 1 e o cabecalho
            posicao_por_rad.setdefault(str(linha_a[0]).strip(), indice)

    atualizacoes = []
    novas = []
    for numero_rad, linha in pares:
        posicao = posicao_por_rad.get(numero_rad)
        if posicao is None:
            novas.append(linha)
        else:
            atualizacoes.append({'range': f"'{aba}'!A{posicao}", 'values': [linha]})

    if atualizacoes:
        servico.spreadsheets().values().batchUpdate(
            spreadsheetId=id_planilha,
            body={'valueInputOption': 'USER_ENTERED', 'data': atualizacoes},
        ).execute()
    if novas:
        enviar_linhas(novas)

    return len(atualizacoes), len(novas)
