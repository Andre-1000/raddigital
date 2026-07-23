"""
Regras de negocio criticas do Sistema RAD.

Este modulo implementa RG-IDENT-004 a RG-IDENT-012 (geracao atomica do
Numero de Execucao) e a idempotencia de sincronizacao (PADROES_E_DIRETRIZES
secao 5.2). "Critico" porque um erro aqui gera numeros de execucao
duplicados ou RADs duplicados em produção -- por isso a implementação
foge deliberadamente do pseudo-SQL literal da EFD onde ele é frágil,
com a justificativa documentada abaixo.
"""
from django.db import IntegrityError, connection, transaction
from django.utils import timezone

from catalogos.models import CatLocal, CatMch, CatMotivoAtraso, CatTipoManutencao
from colaboradores.models import ColaboradorCadastro
from usuarios.models import Usuario

from .models import (
    Rad,
    RadAmv,
    RadAmvAcao,
    RadAmvDefeito,
    RadAnexo,
    RadColaborador,
    RadEquipe,
    RadLinha,
    RadServico,
    RadVia,
)
from comum.datas import parse_hora, tornar_aware

from .regras_horario import processar_horarios
from .validadores import validar_payload_sincronizacao
from .validadores_arquivos import validar_anexos

# Namespace para os locks consultivos desta funcionalidade, para nao
# colidir com outros usos de pg_advisory_xact_lock no sistema.
_NAMESPACE_LOCK_OS = "hashtext('sistema_rad:numero_os')"


def _travar_os(numero_os):
    """
    Trava exclusivamente a OS informada para a duracao da transacao atual
    (RG-IDENT-008, passo 2).

    Usa pg_advisory_xact_lock em vez de "SELECT ... FOR UPDATE" sobre as
    linhas existentes da OS, porque a primeira ocorrencia de uma OS nao
    tem nenhuma linha para travar: um SELECT ... FOR UPDATE nesse caso
    nao bloqueia nada e permite corrida entre os dois primeiros RADs
    concorrentes da mesma OS (ambos calculariam quantidade_existente = 0
    e receberiam Numero de Execucao = 1). O lock consultivo trava pelo
    proprio valor da OS, existam ou nao linhas gravadas, e e liberado
    automaticamente no COMMIT/ROLLBACK da transacao (passo 6).
    """
    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT pg_advisory_xact_lock({_NAMESPACE_LOCK_OS}::int, %s)',
            [numero_os],
        )


def gerar_numero_rad():
    """
    Gera o proximo Numero do RAD (EFD-004, formato R00001) usando uma
    sequence dedicada do Postgres. nextval() e atomico nativamente, sem
    necessidade de lock manual, e nunca repete valor mesmo sob
    concorrencia alta.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval('seq_numero_rad')")
        proximo = cursor.fetchone()[0]
    return f'R{proximo:05d}'


@transaction.atomic
def gerar_numero_execucao(numero_os):
    """
    RG-IDENT-008/009: gera atomica e exclusivamente o proximo Numero de
    Execucao para a OS informada. Deve ser chamada dentro da mesma
    transacao que grava o RAD (ver sincronizar_rad), pois o lock so
    protege ate o fim da transacao atual.
    """
    _travar_os(numero_os)
    quantidade_existente = Rad.objects.filter(numero_os=numero_os).count()
    return quantidade_existente + 1


@transaction.atomic
def sincronizar_rad(dados_rad):
    """
    Ponto unico de entrada para persistir um RAD sincronizado no servidor.

    dados_rad: dict com todos os campos de Rad exceto numero_rad e
    numero_execucao (gerados aqui). Deve conter 'numero_os' e
    'sync_id_tentativa'.

    Idempotencia (PADROES_E_DIRETRIZES 5.2): se o sync_id_tentativa ja
    existir, retorna o RAD ja gravado em vez de criar duplicata --
    cobre o caso de reenvio apos falha de conexao antes do cliente
    receber a confirmacao do servidor.

    Retorna (rad, criado) onde criado=False indica que a chamada foi
    idempotente (RAD ja existia).
    """
    sync_id_tentativa = dados_rad['sync_id_tentativa']

    rad_existente = Rad.objects.filter(sync_id_tentativa=sync_id_tentativa).first()
    if rad_existente is not None:
        return rad_existente, False

    numero_os = dados_rad['numero_os']
    numero_execucao = gerar_numero_execucao(numero_os)
    numero_rad = gerar_numero_rad()

    dados_completos = {**dados_rad, 'numero_rad': numero_rad, 'numero_execucao': numero_execucao}

    try:
        rad = Rad.objects.create(**dados_completos)
    except IntegrityError:
        # Corrida rara: outra requisicao com o mesmo sync_id_tentativa
        # venceu entre o SELECT acima e este INSERT. Trata como
        # idempotente em vez de propagar o erro (RG-IDENT-012 nao se
        # aplica aqui pois nao houve falha real, apenas concorrencia
        # no proprio reenvio).
        rad_existente = Rad.objects.filter(sync_id_tentativa=sync_id_tentativa).first()
        if rad_existente is not None:
            return rad_existente, False
        raise

    return rad, True


def _preparar_horarios(payload):
    """
    Chama regras_horario.processar_horarios quando os campos minimos
    estao presentes. Se algum estiver faltando, retorna campos vazios --
    a validacao (VLD-011) e quem sinaliza o problema ao usuario, esta
    funcao nao deve levantar excecao por dado ausente.
    """
    campos_obrigatorios = [
        payload.get('data_preenchimento'),
        payload.get('hora_prog_inicio'),
        payload.get('hora_prog_termino'),
        payload.get('hora_real_inicio'),
        payload.get('hora_real_termino'),
    ]
    if not all(campos_obrigatorios):
        return {
            'data_hora_prog_inicio': None,
            'data_hora_prog_termino': None,
            'data_hora_real_inicio': None,
            'data_hora_real_termino': None,
            'atraso_inicio': False,
            'atraso_termino': False,
        }

    tipo_manutencao = None
    if payload.get('id_tipo_manutencao'):
        tipo_manutencao = CatTipoManutencao.objects.filter(
            id=payload['id_tipo_manutencao']
        ).first()
    tipo_e_falha = bool(tipo_manutencao and tipo_manutencao.nome == 'Falha')

    resultado = processar_horarios(
        data_preenchimento=payload['data_preenchimento'],
        hora_prog_inicio=parse_hora(payload['hora_prog_inicio']),
        hora_prog_termino=parse_hora(payload['hora_prog_termino']),
        hora_real_inicio=parse_hora(payload['hora_real_inicio']),
        hora_real_termino=parse_hora(payload['hora_real_termino']),
        tipo_manutencao_e_falha=tipo_e_falha,
        data_hp_inicio=payload.get('data_hp_inicio'),
        data_hp_termino=payload.get('data_hp_termino'),
        data_hr_inicio=payload.get('data_hr_inicio'),
        data_hr_termino=payload.get('data_hr_termino'),
    )

    # processar_horarios e uma funcao pura (sem dependencia do Django) e
    # devolve datetimes "naive". Como USE_TZ=True (America/Sao_Paulo),
    # tornamos os quatro DateTime completos timezone-aware aqui, na
    # borda entre a logica pura e a persistencia.
    for campo in (
        'data_hora_prog_inicio',
        'data_hora_prog_termino',
        'data_hora_real_inicio',
        'data_hora_real_termino',
    ):
        resultado[campo] = tornar_aware(resultado[campo])

    return resultado


def _criar_relacionamentos(rad, payload):
    """Cria as linhas, vias, servicos, colaboradores, equipes e bloco AMV de um RAD novo."""
    RadLinha.objects.bulk_create(
        [RadLinha(rad=rad, linha_id=codigo) for codigo in payload.get('linhas', [])]
    )
    RadVia.objects.bulk_create(
        [RadVia(rad=rad, via_id=id_via) for id_via in payload.get('vias', [])]
    )
    RadServico.objects.bulk_create(
        [
            RadServico(rad=rad, servico_id=id_servico)
            for id_servico in payload.get('servicos', [])
        ]
    )

    # Mudanca de negocio (17/07/2026): a equipe VP e sempre incluida
    # automaticamente, independente do que o cliente enviou. Usamos um
    # set para nao tentar criar VP duas vezes caso o cliente ja tenha
    # enviado VP explicitamente.
    codigos_equipes = set(payload.get('equipes', [])) | {'VP'}
    RadEquipe.objects.bulk_create(
        [RadEquipe(rad=rad, equipe_id=codigo) for codigo in codigos_equipes]
    )

    for colaborador in payload.get('colaboradores', []):
        nome = colaborador['nome']
        registro_empresa = colaborador.get('registro_empresa') or None
        if colaborador['tipo'] == 'colaborador' and registro_empresa:
            # RG-RESP-004/005: o nome vem do cadastro oficial, nunca do
            # que o cliente enviou -- o campo nao e editavel manualmente
            # no preenchimento do RAD. validar_payload_sincronizacao ja
            # garantiu (VLD-027) que este registro existe no cadastro.
            cadastro = ColaboradorCadastro.objects.filter(
                registro_empresa=registro_empresa
            ).first()
            if cadastro:
                nome = cadastro.nome
        RadColaborador.objects.create(
            rad=rad,
            registro_empresa=registro_empresa,
            nome=nome,
            tipo=colaborador['tipo'],
        )

    amv = payload.get('amv')
    if amv and amv.get('id_mch'):
        mch = CatMch.objects.get(id=amv['id_mch'])
        RadAmv.objects.create(
            rad=rad,
            mch=mch,
            modelo_mch=mch.modelo,
            via_mch=mch.via,
            ur_mch=mch.ur,
            local_mch=mch.local_amv,
            linha_mch=mch.linha,
        )
        RadAmvDefeito.objects.bulk_create(
            [
                RadAmvDefeito(rad=rad, tipo_defeito_id=id_defeito)
                for id_defeito in amv.get('tipos_defeito', [])
            ]
        )
        RadAmvAcao.objects.bulk_create(
            [RadAmvAcao(rad=rad, acao_id=id_acao) for id_acao in amv.get('acoes', [])]
        )


def _salvar_anexos(rad, fotos_intervencao, fotos_acao, pdfs):
    """
    RG-ANX-007/008: os arquivos vao para o storage de arquivos (local em
    desenvolvimento; a definir em producao -- ver DT-PEND). O banco
    grava apenas a referencia (caminho_servidor), nunca o conteudo do
    arquivo. Chamada somente depois que validar_anexos() ja aprovou
    todos os arquivos -- esta funcao nao valida nada, so persiste.

    Cada foto grava sua categoria (Intervencao verificada / Acao
    realizada) para que os dois grupos nunca fiquem misturados sem
    identificacao.
    """
    from django.core.files.storage import default_storage
    from django.utils import timezone as django_timezone

    grupos_de_foto = (
        (fotos_intervencao, RadAnexo.INTERVENCAO_VERIFICADA),
        (fotos_acao, RadAnexo.ACAO_REALIZADA),
    )
    for fotos, categoria in grupos_de_foto:
        for foto in fotos:
            caminho = default_storage.save(f'anexos/{rad.numero_rad}/{foto.name}', foto)
            RadAnexo.objects.create(
                rad=rad,
                tipo_arquivo=RadAnexo.FOTO,
                categoria_foto=categoria,
                nome_original=foto.name,
                caminho_servidor=caminho,
                tamanho_bytes=foto.size,
                data_upload=django_timezone.now(),
            )

    for pdf in pdfs:
        caminho = default_storage.save(f'anexos/{rad.numero_rad}/{pdf.name}', pdf)
        RadAnexo.objects.create(
            rad=rad,
            tipo_arquivo=RadAnexo.PDF,
            categoria_foto=None,
            nome_original=pdf.name,
            caminho_servidor=caminho,
            tamanho_bytes=pdf.size,
            data_upload=django_timezone.now(),
        )


@transaction.atomic
def processar_sincronizacao(payload, usuario, fotos_intervencao=None, fotos_acao=None, pdfs=None):
    """
    Ponto de entrada da view de sincronizacao. Orquestra, nesta ordem:

    1. Calculo dos horarios derivados (regras_horario) -- necessario
       antes de validar, pois VLD-012/013 dependem dos DateTime
       completos ja calculados.
    2. Validacao completa (RG-VLD-001 a 003, VLD-001 a 027, incluindo
       os anexos). Se houver qualquer erro, nao toca o banco nem o
       storage de arquivos (RG-VLD-002) e retorna (None, erros).
    3. Persistencia atomica do RAD (geracao do numero de execucao e do
       numero do RAD, idempotencia por sync_id_tentativa).
    4. Criacao das tabelas relacionadas e upload dos anexos -- pulada
       quando a chamada foi idempotente (RAD ja existia), para nao
       duplicar linhas nem arquivos.

    fotos_intervencao/fotos_acao/pdfs: listas de UploadedFile
    (request.FILES), opcionais. RAD sem nenhum anexo e valido (VLD-026).

    Retorna (rad, erros). Exatamente um dos dois sera "vazio":
    erros == [] quando rad foi criado/recuperado; rad is None quando ha
    erros de validacao.
    """
    fotos_intervencao = fotos_intervencao or []
    fotos_acao = fotos_acao or []
    pdfs = pdfs or []

    sync_id_tentativa = payload.get('sync_id_tentativa')
    if sync_id_tentativa:
        rad_existente = Rad.objects.filter(sync_id_tentativa=sync_id_tentativa).first()
        if rad_existente is not None:
            # Idempotencia (PADROES_E_DIRETRIZES 5.2): reenvio do mesmo
            # sync_id_tentativa retorna o RAD ja gravado sem revalidar --
            # evita que um reenvio com payload incompleto (ex.: cliente
            # reenviando so o identificador apos timeout) seja rejeitado
            # por engano quando o RAD ja foi persistido com sucesso.
            return rad_existente, []

    horarios = _preparar_horarios(payload)

    tipo_manutencao = None
    if payload.get('id_tipo_manutencao'):
        tipo_manutencao = CatTipoManutencao.objects.filter(
            id=payload['id_tipo_manutencao']
        ).first()

    payload_validacao = {
        **payload,
        **horarios,
        '_tipo_manutencao_e_falha': bool(
            tipo_manutencao and tipo_manutencao.nome == 'Falha'
        ),
    }

    erros = validar_payload_sincronizacao(
        payload_validacao, hoje=timezone.localdate()
    )
    erros += validar_anexos(fotos_intervencao, fotos_acao, pdfs)
    if erros:
        return None, erros

    local_inicial = CatLocal.objects.get(sigla=payload['id_local_inicial'])
    local_final = CatLocal.objects.get(sigla=payload['id_local_final'])
    motivo_inicio = (
        CatMotivoAtraso.objects.filter(id=payload.get('id_motivo_atraso_inicio')).first()
        if payload.get('id_motivo_atraso_inicio')
        else None
    )
    motivo_termino = (
        CatMotivoAtraso.objects.filter(id=payload.get('id_motivo_atraso_termino')).first()
        if payload.get('id_motivo_atraso_termino')
        else None
    )

    dados_rad = {
        'numero_os': payload['numero_os'],
        'numero_sa': str(payload['numero_sa']),
        'data_preenchimento': payload['data_preenchimento'],
        'local_inicial': local_inicial,
        'local_final': local_final,
        'km_poste': payload.get('km_poste') or None,
        'tipo_manutencao': tipo_manutencao,
        'numero_falha': payload.get('numero_falha') or None,
        'hora_prog_inicio': parse_hora(payload['hora_prog_inicio']),
        'hora_prog_termino': parse_hora(payload['hora_prog_termino']),
        'hora_real_inicio': parse_hora(payload['hora_real_inicio']),
        'hora_real_termino': parse_hora(payload['hora_real_termino']),
        # RG-HOR-016/017/018: motivo/descricao so persistem quando o
        # respectivo atraso foi de fato identificado; caso contrario sao
        # limpos aqui, mesmo que tenham vindo preenchidos no payload.
        'atraso_inicio': horarios['atraso_inicio'],
        'motivo_atraso_inicio': motivo_inicio if horarios['atraso_inicio'] else None,
        'desc_motivo_atraso_inicio': (
            payload.get('desc_motivo_atraso_inicio') if horarios['atraso_inicio'] else None
        ),
        'atraso_termino': horarios['atraso_termino'],
        'motivo_atraso_termino': motivo_termino if horarios['atraso_termino'] else None,
        'desc_motivo_atraso_termino': (
            payload.get('desc_motivo_atraso_termino') if horarios['atraso_termino'] else None
        ),
        'outros_servico_desc': payload.get('outros_servico_desc') or None,
        'materiais_utilizados': payload.get('materiais_utilizados') or None,
        'observacoes_gerais': payload.get('observacoes_gerais') or None,
        'responsavel_atividade': payload.get('responsavel_atividade') or None,
        'operador_ccm': payload.get('operador_ccm') or None,
        'descricao_tecnica_atividade': payload.get('descricao_tecnica_atividade') or None,
        'usuario': usuario,
        'dispositivo': payload.get('dispositivo', Rad.DESCONHECIDO),
        'data_sincronizacao': timezone.now(),
        'sync_id_tentativa': payload['sync_id_tentativa'],
        **{k: v for k, v in horarios.items() if k not in ('atraso_inicio', 'atraso_termino')},
    }

    rad, criado = sincronizar_rad(dados_rad)
    if criado:
        _criar_relacionamentos(rad, payload)
        _salvar_anexos(rad, fotos_intervencao, fotos_acao, pdfs)

    return rad, []
