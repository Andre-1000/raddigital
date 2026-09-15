"""
Integracao com Google Drive -- 14/09/2026. Permite salvar o Word
oficial gerado direto numa pasta do Drive da empresa, sem depender de
Word/Office instalado na maquina de quem vai consultar depois -- o
arquivo pode ser aberto direto pelo Google Docs, no navegador.

Configuracao (variaveis de ambiente, nunca no codigo):
  GOOGLE_DRIVE_CREDENTIALS_JSON -- conteudo INTEIRO do arquivo .json
    da conta de servico (o valor JSON em si, colado direto na
    variavel de ambiente -- nao um caminho de arquivo).
  GOOGLE_DRIVE_FOLDER_ID -- ID da pasta do Drive (compartilhada
    previamente com o e-mail da conta de servico, permissao Editor --
    ver client_email dentro do proprio JSON).

Sem essas duas variaveis definidas, a funcionalidade fica
indisponivel de forma controlada -- ver esta_configurado() e
DriveNaoConfiguradoError.

Escopo minimo usado (drive.file): a conta de servico so enxerga e
edita arquivos que ELA MESMA criou -- nunca o resto do Drive da
empresa, mesmo que a pasta pertenca a outra pessoa.
"""
import io
import json
import os

_ESCOPOS = ['https://www.googleapis.com/auth/drive.file']


class DriveNaoConfiguradoError(Exception):
    """As variaveis de ambiente do Drive nao estao configuradas."""


def esta_configurado():
    return bool(
        os.getenv('GOOGLE_DRIVE_CREDENTIALS_JSON') and os.getenv('GOOGLE_DRIVE_FOLDER_ID')
    )


def _obter_servico():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    credenciais_dict = json.loads(os.environ['GOOGLE_DRIVE_CREDENTIALS_JSON'])
    credenciais = service_account.Credentials.from_service_account_info(
        credenciais_dict, scopes=_ESCOPOS
    )
    # cache_discovery=False: evita o googleapiclient tentar escrever
    # cache em disco (nao ha disco persistente no Render) -- sem isso,
    # cada chamada emite um aviso de log inofensivo, mas desnecessario.
    return build('drive', 'v3', credentials=credenciais, cache_discovery=False)


def salvar_docx_no_drive(nome_arquivo, docx_bytes):
    """
    Sobe o arquivo .docx (bytes ja gerados por
    rad/exportacao_oficial.py::gerar_docx_oficial_bytes) para a pasta
    configurada em GOOGLE_DRIVE_FOLDER_ID. Retorna o link (webViewLink)
    do arquivo no Drive -- que ja abre direto no Google Docs.

    Levanta DriveNaoConfiguradoError se as variaveis de ambiente nao
    estiverem definidas -- quem chama deve tratar isso como uma
    funcionalidade indisponivel (503), nao como um erro inesperado.
    """
    if not esta_configurado():
        raise DriveNaoConfiguradoError(
            'Integração com Google Drive não configurada. Contate o Administrador.'
        )

    from googleapiclient.http import MediaIoBaseUpload

    servico = _obter_servico()
    metadados = {
        'name': nome_arquivo,
        'parents': [os.environ['GOOGLE_DRIVE_FOLDER_ID']],
    }
    midia = MediaIoBaseUpload(
        io.BytesIO(docx_bytes),
        mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        resumable=False,
    )
    arquivo = servico.files().create(
        body=metadados, media_body=midia, fields='id, webViewLink'
    ).execute()
    return arquivo.get('webViewLink')
