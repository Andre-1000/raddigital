"""
LOGGING (28/10/2026): erro 500 precisa aparecer nos Logs com o motivo.

1) Simula o caso real do R00459 -- o gerador do Word quebra -- e confere
   que o Django registra o erro em 'django.request' COM o traceback.
2) Num processo separado (como o servidor roda), confere que esse
   registro sai na saida do processo -- que e o que o Render mostra.
"""
import os
import subprocess
import sys
from pathlib import Path
from unittest import mock

import logging

import pytest
from django.urls import reverse

from rad.test_edicao_rad import _auth, admin, rad_sincronizado, tecnico  # noqa: F401
from rad.test_numero_os import catalogo  # noqa: F401


@pytest.mark.django_db
def test_erro_500_e_registrado_com_traceback(client, admin, rad_sincronizado, caplog):  # noqa: F811
    client.raise_request_exception = False
    # 'django.request' nao propaga para a raiz (onde o caplog escuta) --
    # liga o capturador direto nele.
    logging.getLogger('django.request').addHandler(caplog.handler)
    _, token = admin
    with mock.patch(
        'rad.exportacao_oficial.gerar_docx_oficial_bytes',
        side_effect=RuntimeError('falha simulada no Word'),
    ):
        resposta = client.get(
            reverse('consulta:exportar_docx_oficial', args=[rad_sincronizado.numero_rad]), **_auth(token)
        )
    assert resposta.status_code == 500
    logging.getLogger('django.request').removeHandler(caplog.handler)
    registros = [r for r in caplog.records if r.name == 'django.request' and r.levelname == 'ERROR']
    assert registros, 'erro 500 nao foi registrado'
    tipo, erro, _ = registros[0].exc_info
    assert tipo is RuntimeError and str(erro) == 'falha simulada no Word'
    assert token.valor_plano not in caplog.text  # token de acesso nunca vai para o log


def test_registro_sai_na_saida_do_processo():
    script = (
        'import django, logging; django.setup()\n'
        'try:\n'
        '    raise RuntimeError("falha simulada no Word")\n'
        'except RuntimeError:\n'
        '    logging.getLogger("django.request").error("Internal Server Error: /x/", exc_info=True)\n'
    )
    raiz = Path(__file__).resolve().parent.parent
    resultado = subprocess.run(
        [sys.executable, '-c', script], cwd=raiz, capture_output=True, text=True, timeout=60,
        # DEBUG=False como em producao: e justamente o modo em que, sem
        # LOGGING, o Django escondia o erro.
        env={**os.environ, 'DJANGO_SETTINGS_MODULE': 'config.settings', 'DEBUG': 'False',
             'SECRET_KEY': 'teste-logging-nao-usado'},
    )
    saida = resultado.stdout + resultado.stderr
    assert 'ERROR django.request: Internal Server Error: /x/' in saida
    assert 'Traceback' in saida
    assert 'RuntimeError: falha simulada no Word' in saida
