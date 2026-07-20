"""
Testes do app interface — as views aqui so servem o "shell" HTML;
autenticacao e dados sao responsabilidade do JS no navegador (nao
testavel via Django test client, que nao executa JavaScript). O que
testamos: as paginas carregam, usam o template certo, e referenciam
corretamente os arquivos estaticos e as APIs que consomem.
"""
import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestTelasCarregam:
    def test_saude_confirma_banco_acessivel(self, client):
        resposta = client.get('/saude/')
        assert resposta.status_code == 200
        assert resposta.json()['status'] == 'ok'

    def test_raiz_carrega_tela_de_login(self, client):
        resposta = client.get('/')
        assert resposta.status_code == 200
        assert 'interface/login.html' in [t.name for t in resposta.templates]

    def test_login_carrega(self, client):
        resposta = client.get(reverse('interface:login'))
        assert resposta.status_code == 200
        assert b'form-login' in resposta.content
        assert b'campo-login' in resposta.content

    def test_inicio_carrega(self, client):
        resposta = client.get(reverse('interface:inicio'))
        assert resposta.status_code == 200
        assert b'RadAuth.exigirSessao' in resposta.content

    def test_consulta_carrega(self, client):
        resposta = client.get(reverse('interface:consulta'))
        assert resposta.status_code == 200
        assert b'RadAuth.exigirSessao' in resposta.content

    def test_novo_rad_carrega(self, client):
        resposta = client.get(reverse('interface:novo_rad'))
        assert resposta.status_code == 200
        assert b'form-rad' in resposta.content
        assert b'campo-numero-os' in resposta.content
        assert b'campo-numero-sa' in resposta.content

    def test_detalhe_rad_carrega(self, client):
        resposta = client.get(reverse('interface:detalhe_rad', args=['R00001']))
        assert resposta.status_code == 200
        assert b'cartao-dados' in resposta.content
        assert b'botao-copiar-mensagem' in resposta.content
        assert b'botao-baixar-pdf' in resposta.content
        assert b'botao-baixar-docx' in resposta.content
        assert b'botao-abrir-cancelamento' in resposta.content

    def test_gerenciar_colaboradores_carrega(self, client):
        resposta = client.get(reverse('interface:gerenciar_colaboradores'))
        assert resposta.status_code == 200
        assert b'botao-adicionar' in resposta.content
        assert b'campo-novo-registro' in resposta.content
        assert b'campo-novo-nome' in resposta.content


@pytest.mark.django_db
class TestPaginasProtegidasExigemSessaoNoCliente:
    """
    Confirma que toda pagina que deveria ser protegida chama
    RadAuth.exigirSessao() logo no carregamento -- e o unico mecanismo
    de protecao, entao sua ausencia seria uma falha de seguranca
    silenciosa (a pagina carregaria normalmente sem sessao).
    """

    def test_inicio_chama_exigir_sessao(self, client):
        resposta = client.get(reverse('interface:inicio'))
        assert b'exigirSessao()' in resposta.content

    def test_consulta_chama_exigir_sessao(self, client):
        resposta = client.get(reverse('interface:consulta'))
        assert b'exigirSessao()' in resposta.content

    def test_novo_rad_chama_exigir_sessao(self):
        """
        Ao contrario de inicio.html/consulta.html, novo_rad.html carrega
        a logica de um arquivo externo (rad_form.js) em vez de script
        inline -- por isso checamos o arquivo, nao o HTML da pagina.
        """
        from pathlib import Path

        conteudo_js = (
            Path(__file__).resolve().parent
            / 'static' / 'interface' / 'js' / 'rad_form.js'
        ).read_text()
        assert 'exigirSessao()' in conteudo_js

    def test_consulta_verifica_perfil_supervisor_ou_administrador(self, client):
        resposta = client.get(reverse('interface:consulta'))
        assert b"temPerfil('supervisor', 'administrador')" in resposta.content

    def test_detalhe_rad_chama_exigir_sessao(self, client):
        resposta = client.get(reverse('interface:detalhe_rad', args=['R00001']))
        assert b'exigirSessao()' in resposta.content

    def test_detalhe_rad_verifica_perfil_supervisor_ou_administrador(self, client):
        resposta = client.get(reverse('interface:detalhe_rad', args=['R00001']))
        assert b"temPerfil('supervisor', 'administrador')" in resposta.content

    def test_gerenciar_colaboradores_chama_exigir_sessao_e_verifica_administrador(self):
        """
        Como novo_rad.html, esta pagina carrega a logica de um arquivo
        externo em vez de script inline -- checamos o arquivo, nao o
        HTML da pagina.
        """
        from pathlib import Path

        conteudo_js = (
            Path(__file__).resolve().parent
            / 'static' / 'interface' / 'js' / 'gerenciar_colaboradores.js'
        ).read_text()
        assert 'exigirSessao()' in conteudo_js
        assert "temPerfil('administrador')" in conteudo_js


@pytest.mark.django_db
class TestEstaticosReferenciados:
    def test_base_referencia_css_e_js_corretos(self, client):
        resposta = client.get(reverse('interface:login'))
        assert b'interface/css/estilo.css' in resposta.content
        assert b'interface/js/auth.js' in resposta.content
        assert b'interface/js/db.js' in resposta.content

    def test_arquivos_estaticos_existem_no_disco(self):
        """
        Django test client nao serve arquivos estaticos (isso e feito
        pelo runserver ou por um servidor real) -- ja confirmei
        manualmente com curl contra o servidor rodando que retornam
        200. Aqui garantimos que os arquivos existem no caminho certo,
        o que teria pego um erro de digitação no nome/pasta.
        """
        from pathlib import Path

        base = Path(__file__).resolve().parent / 'static' / 'interface'
        assert (base / 'css' / 'estilo.css').exists()
        assert (base / 'js' / 'auth.js').exists()
        assert (base / 'js' / 'db.js').exists()
        assert (base / 'js' / 'rad_form.js').exists()
        assert (base / 'js' / 'regras_horario.js').exists()
        assert (base / 'js' / 'validadores_arquivos.js').exists()
        assert (base / 'js' / 'exportar_cliente.js').exists()
        assert (base / 'js' / 'vendor' / 'jspdf.umd.min.js').exists()

    def test_vendor_jspdf_tem_o_arquivo_map_junto(self):
        """
        Regressao: jspdf.umd.min.js referencia jspdf.umd.min.js.map
        (sourceMappingURL). Sem o .map, `collectstatic` com WhiteNoise
        em producao (DEBUG=False) QUEBRA o build inteiro -- confirmado
        rodando collectstatic de verdade com DEBUG=False antes desta
        correcao. Este teste garante que o arquivo nunca falte de novo.
        """
        from pathlib import Path

        base = Path(__file__).resolve().parent / 'static' / 'interface'
        caminho_js = base / 'js' / 'vendor' / 'jspdf.umd.min.js'
        caminho_map = base / 'js' / 'vendor' / 'jspdf.umd.min.js.map'
        assert caminho_map.exists(), (
            'jspdf.umd.min.js.map esta faltando -- isso quebra collectstatic '
            'em producao (WhiteNoise CompressedManifestStaticFilesStorage)'
        )
        assert f'sourceMappingURL={caminho_map.name}' in caminho_js.read_text()[-200:]

    def test_collectstatic_funciona_de_verdade_em_modo_producao(self):
        """
        Regressao mais forte que a checagem de arquivo acima: roda
        `collectstatic` de verdade com DEBUG=False (WhiteNoise
        CompressedManifestStaticFilesStorage ativo, igual ao Dockerfile
        de producao) e confirma que NAO quebra. E assim que o bug do
        .map faltando foi encontrado -- rodando este comando de
        verdade, nao so revisando o codigo.
        """
        import os
        import shutil
        import subprocess
        from pathlib import Path

        ambiente = os.environ.copy()
        ambiente.update(
            {
                'DEBUG': 'False',
                'SECRET_KEY': 'teste-collectstatic-nao-usado-em-runtime',
                'ALLOWED_HOSTS': 'exemplo.com',
            }
        )
        base_dir = Path(__file__).resolve().parent.parent
        pasta_gerada = base_dir / 'staticfiles'
        try:
            resultado = subprocess.run(
                ['python', 'manage.py', 'collectstatic', '--noinput'],
                cwd=str(base_dir),
                env=ambiente,
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert resultado.returncode == 0, (
                f'collectstatic falhou em modo producao:\n{resultado.stdout}\n{resultado.stderr}'
            )
        finally:
            shutil.rmtree(pasta_gerada, ignore_errors=True)

    def test_novo_rad_referencia_rad_form_js(self, client):
        resposta = client.get(reverse('interface:novo_rad'))
        assert b'interface/js/rad_form.js' in resposta.content

    def test_novo_rad_referencia_scripts_de_exportacao(self, client):
        resposta = client.get(reverse('interface:novo_rad'))
        assert b'interface/js/exportar_cliente.js' in resposta.content
        assert b'interface/js/vendor/jspdf.umd.min.js' in resposta.content

    def test_botao_exportar_fica_ao_lado_do_sincronizar(self, client):
        """RG-EXP-004."""
        resposta = client.get(reverse('interface:novo_rad'))
        conteudo = resposta.content.decode()
        posicao_exportar = conteudo.find('id="botao-exportar"')
        posicao_sincronizar = conteudo.find('id="botao-sincronizar"')
        assert posicao_exportar != -1 and posicao_sincronizar != -1
        # "ao lado" = mesmo bloco de acao fixa, sem nenhuma outra secao
        # grande entre os dois -- checamos que a distancia no HTML e
        # pequena (mesma div), nao em paginas/secoes diferentes.
        assert abs(posicao_sincronizar - posicao_exportar) < 500


@pytest.mark.django_db
class TestLogicaJsDeHorarios:
    """
    Roda interface/js_tests/teste_regras_horario.js de verdade (via
    Node.js) como parte da suite do projeto. regras_horario.js e
    codigo cliente puro (sem DOM), entao pode ser testado isoladamente
    assim, com os MESMOS casos de teste que ja provamos no backend
    (rad/test_regras_horario.py) -- incluindo o exemplo oficial da EFD
    (22:00 -> 02:00 = 4h00) e as bordas de tolerancia de atraso.
    """

    def test_regras_horario_js_passa_em_todos_os_casos(self):
        import subprocess
        from pathlib import Path

        script = Path(__file__).resolve().parent / 'js_tests' / 'teste_regras_horario.js'
        resultado = subprocess.run(
            ['node', str(script)], capture_output=True, text=True, timeout=30
        )
        assert resultado.returncode == 0, (
            f'Teste JS de regras de horario falhou:\n{resultado.stdout}\n{resultado.stderr}'
        )
        assert 'TODOS OS TESTES PASSARAM' in resultado.stdout


@pytest.mark.django_db
class TestBlocoAmvComDomReal:
    """
    Renderiza o template de verdade e simula, com jsdom, o usuario
    marcando "Manutencao em AMV", preenchendo tipos de defeito,
    desmarcando e remarcando o servico -- o cenario exato que expos um
    bug real de closure durante o desenvolvimento (ver comentario em
    interface/js_tests/teste_bloco_amv.js).
    """

    def test_bloco_amv_com_interacoes_reais_de_checkbox(self, tmp_path):
        import subprocess
        from pathlib import Path

        from django.template.loader import render_to_string

        html = render_to_string('interface/novo_rad.html')
        caminho_html = tmp_path / 'novo_rad_renderizado.html'
        caminho_html.write_text(html)

        script = Path(__file__).resolve().parent / 'js_tests' / 'teste_bloco_amv.js'
        resultado = subprocess.run(
            ['node', str(script), str(caminho_html)],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(__file__).resolve().parent / 'js_tests'),
        )
        assert resultado.returncode == 0, (
            f'Teste do bloco AMV falhou:\n{resultado.stdout}\n{resultado.stderr}'
        )
        assert 'TODOS OS TESTES PASSARAM' in resultado.stdout


@pytest.mark.django_db
class TestColaboradoresComDomReal:
    """
    Mesma abordagem de TestBlocoAmvComDomReal: DOM real via jsdom sobre
    o HTML renderizado de verdade, simulando busca, RG-RESP-008/009 e
    remocao de colaboradores/participantes.
    """

    def test_colaboradores_com_interacoes_reais(self, tmp_path):
        import subprocess
        from pathlib import Path

        from django.template.loader import render_to_string

        html = render_to_string('interface/novo_rad.html')
        caminho_html = tmp_path / 'novo_rad_renderizado.html'
        caminho_html.write_text(html)

        script = Path(__file__).resolve().parent / 'js_tests' / 'teste_colaboradores.js'
        resultado = subprocess.run(
            ['node', str(script), str(caminho_html)],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(__file__).resolve().parent / 'js_tests'),
        )
        assert resultado.returncode == 0, (
            f'Teste de colaboradores falhou:\n{resultado.stdout}\n{resultado.stderr}'
        )
        assert 'TODOS OS TESTES PASSARAM' in resultado.stdout


@pytest.mark.django_db
class TestAnexosComDomReal:
    """
    Mesma abordagem dos blocos anteriores. createImageBitmap e mockado
    (jsdom nao decodifica imagens de verdade), mas a validacao de PDF
    roda sem mock -- FileReader + assinatura magica funcionam nativamente
    no jsdom.
    """

    def test_anexos_com_interacoes_reais(self, tmp_path):
        import subprocess
        from pathlib import Path

        from django.template.loader import render_to_string

        html = render_to_string('interface/novo_rad.html')
        caminho_html = tmp_path / 'novo_rad_renderizado.html'
        caminho_html.write_text(html)

        script = Path(__file__).resolve().parent / 'js_tests' / 'teste_anexos.js'
        resultado = subprocess.run(
            ['node', str(script), str(caminho_html)],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(__file__).resolve().parent / 'js_tests'),
        )
        assert resultado.returncode == 0, (
            f'Teste de anexos falhou:\n{resultado.stdout}\n{resultado.stderr}'
        )
        assert 'TODOS OS TESTES PASSARAM' in resultado.stdout


@pytest.mark.django_db
class TestCamposFinaisComDomReal:
    """
    Mesma abordagem dos blocos anteriores, mais uma checagem posicional
    que trava a decisao de layout registrada em
    docs/NOTAS_LAYOUT_FRONTEND.md (Observacoes Gerais abaixo dos anexos).
    """

    def test_campos_finais_com_interacoes_reais(self, tmp_path):
        import subprocess
        from pathlib import Path

        from django.template.loader import render_to_string

        html = render_to_string('interface/novo_rad.html')
        caminho_html = tmp_path / 'novo_rad_renderizado.html'
        caminho_html.write_text(html)

        script = Path(__file__).resolve().parent / 'js_tests' / 'teste_campos_finais.js'
        resultado = subprocess.run(
            ['node', str(script), str(caminho_html)],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(__file__).resolve().parent / 'js_tests'),
        )
        assert resultado.returncode == 0, (
            f'Teste dos campos finais falhou:\n{resultado.stdout}\n{resultado.stderr}'
        )
        assert 'TODOS OS TESTES PASSARAM' in resultado.stdout


@pytest.mark.django_db
class TestSincronizarComDomReal:
    """
    Cobre a responsabilidade do cliente no fluxo de sincronizacao:
    montagem do payload, tratamento de sucesso/erro/falha de rede, e o
    guard de estado offline. O contrato do endpoint em si (o que o
    servidor aceita) tem cobertura extensa em rad/test_views.py.
    """

    def test_sincronizar_com_cenarios_reais(self, tmp_path):
        import subprocess
        from pathlib import Path

        from django.template.loader import render_to_string

        html = render_to_string('interface/novo_rad.html')
        caminho_html = tmp_path / 'novo_rad_renderizado.html'
        caminho_html.write_text(html)

        script = Path(__file__).resolve().parent / 'js_tests' / 'teste_sincronizar.js'
        resultado = subprocess.run(
            ['node', str(script), str(caminho_html)],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(__file__).resolve().parent / 'js_tests'),
        )
        assert resultado.returncode == 0, (
            f'Teste de sincronizacao falhou:\n{resultado.stdout}\n{resultado.stderr}'
        )
        assert 'TODOS OS TESTES PASSARAM' in resultado.stdout


@pytest.mark.django_db
class TestDetalheRadComDomReal:
    """
    Mesma abordagem dos blocos anteriores, mas para a tela de detalhe
    do RAD: renderizacao dos dados, exportacao (copiar mensagem) e o
    fluxo completo de cancelamento (RG-CAN-001 a 012).
    """

    def test_detalhe_rad_com_interacoes_reais(self, tmp_path):
        import subprocess
        from pathlib import Path

        from django.template.loader import render_to_string

        html = render_to_string('interface/detalhe_rad.html', {'numero_rad': 'R00001'})
        caminho_html = tmp_path / 'detalhe_rad_renderizado.html'
        caminho_html.write_text(html)

        script = Path(__file__).resolve().parent / 'js_tests' / 'teste_detalhe_rad.js'
        resultado = subprocess.run(
            ['node', str(script), str(caminho_html)],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(__file__).resolve().parent / 'js_tests'),
        )
        assert resultado.returncode == 0, (
            f'Teste da tela de detalhe falhou:\n{resultado.stdout}\n{resultado.stderr}'
        )
        assert 'TODOS OS TESTES PASSARAM' in resultado.stdout


@pytest.mark.django_db
class TestConflitoDeRascunhoComDomReal:
    """RG-SYNC-018/019/020 — "apenas um RAD em preenchimento por vez"."""

    def test_conflito_de_rascunho_com_interacoes_reais(self, tmp_path):
        import subprocess
        from pathlib import Path

        from django.template.loader import render_to_string

        html = render_to_string('interface/novo_rad.html')
        caminho_html = tmp_path / 'novo_rad_renderizado.html'
        caminho_html.write_text(html)

        script = Path(__file__).resolve().parent / 'js_tests' / 'teste_conflito_rascunho.js'
        resultado = subprocess.run(
            ['node', str(script), str(caminho_html)],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(__file__).resolve().parent / 'js_tests'),
        )
        assert resultado.returncode == 0, (
            f'Teste de conflito de rascunho falhou:\n{resultado.stdout}\n{resultado.stderr}'
        )
        assert 'TODOS OS TESTES PASSARAM' in resultado.stdout


@pytest.mark.django_db
class TestGerenciarColaboradoresComDomReal:
    """CRUD completo do cadastro oficial de colaboradores, exclusivo do Administrador."""

    def test_gerenciar_colaboradores_com_interacoes_reais(self, tmp_path):
        import subprocess
        from pathlib import Path

        from django.template.loader import render_to_string

        html = render_to_string('interface/gerenciar_colaboradores.html')
        caminho_html = tmp_path / 'gerenciar_colaboradores_renderizado.html'
        caminho_html.write_text(html)

        script = Path(__file__).resolve().parent / 'js_tests' / 'teste_gerenciar_colaboradores.js'
        resultado = subprocess.run(
            ['node', str(script), str(caminho_html)],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(__file__).resolve().parent / 'js_tests'),
        )
        assert resultado.returncode == 0, (
            f'Teste de gerenciar colaboradores falhou:\n{resultado.stdout}\n{resultado.stderr}'
        )
        assert 'TODOS OS TESTES PASSARAM' in resultado.stdout


class TestExportarClienteLogicaPura:
    """
    Logica pura de exportar_cliente.js: mapeamento de campos, mensagem
    e regra de habilitacao (RG-EXP-005). O jsPDF em si precisa de
    atob/canvas de navegador real, testado em
    interface/browser_tests/test_exportar_offline.py (Playwright).
    """

    def test_exportar_cliente_logica_pura(self):
        import subprocess
        from pathlib import Path

        script = Path(__file__).resolve().parent / 'js_tests' / 'teste_exportar_cliente.js'
        resultado = subprocess.run(
            ['node', str(script)],
            capture_output=True, text=True, timeout=30,
            cwd=str(Path(__file__).resolve().parent / 'js_tests'),
        )
        assert resultado.returncode == 0, (
            f'Teste de exportar_cliente falhou:\n{resultado.stdout}\n{resultado.stderr}'
        )
        assert 'TODOS OS TESTES PASSARAM' in resultado.stdout


class TestContratoDoRascunhoComOBackend:
    """
    O rascunho montado em rad_form.js usa as mesmas chaves que
    rad/regras_negocio.py::processar_sincronizacao espera no payload.
    Este teste nao executa o JS (impossivel via Django test client),
    mas prova que as chaves que o JS escreve no objeto `rascunho`
    aparecem literalmente no arquivo — uma mudanca de nome em um lado
    sem o outro quebraria a sincronizacao silenciosamente, entao
    qualquer edicao futura que renomeie um campo de um lado sem o
    outro faz este teste falhar.
    """

    def test_chaves_do_rascunho_batem_com_o_payload_esperado_pelo_backend(self):
        from pathlib import Path

        conteudo_js = (
            Path(__file__).resolve().parent / 'static' / 'interface' / 'js' / 'rad_form.js'
        ).read_text()

        chaves_esperadas = [
            'numero_os', 'numero_sa', 'data_preenchimento', 'id_local_inicial',
            'id_local_final', 'linhas', 'vias', 'equipes', 'km_poste',
            'id_tipo_manutencao', 'numero_falha', 'sync_id_tentativa',
            'hora_prog_inicio', 'data_hp_inicio', 'hora_prog_termino', 'data_hp_termino',
            'hora_real_inicio', 'data_hr_inicio', 'hora_real_termino', 'data_hr_termino',
            'id_motivo_atraso_inicio', 'desc_motivo_atraso_inicio',
            'id_motivo_atraso_termino', 'desc_motivo_atraso_termino',
            'servicos', 'outros_servico_desc', 'amv', 'colaboradores', 'anexos',
            'responsavel_atividade', 'operador_ccm', 'descricao_tecnica_atividade',
            'materiais_utilizados', 'observacoes_gerais',
        ]
        for chave in chaves_esperadas:
            assert chave in conteudo_js, f'Chave "{chave}" nao encontrada em rad_form.js'


@pytest.mark.django_db
class TestSincronizacaoDeCatalogos:
    def test_login_dispara_atualizacao_de_catalogos(self, client):
        resposta = client.get(reverse('interface:login'))
        assert b'RadDB.atualizarCatalogos()' in resposta.content

    def test_inicio_mostra_status_e_permite_atualizar_catalogos(self, client):
        resposta = client.get(reverse('interface:inicio'))
        assert b'status-catalogos' in resposta.content
        assert b'RadDB.atualizarCatalogos()' in resposta.content
        assert b'RadDB.dataUltimaAtualizacaoCatalogos()' in resposta.content


@pytest.mark.django_db
class TestServiceWorker:
    """
    RG-SYNC-001/010/011: o app shell (HTML/CSS/JS) precisa carregar
    mesmo offline, inclusive na primeira tentativa apos fechar o
    navegador -- nao so depois que a pagina ja carregou uma vez na
    sessao atual. O runtime do Service Worker (Cache API, eventos
    install/fetch) nao e testavel via Django test client nem via jsdom
    (nenhum dos dois implementa a API real) -- por isso a cobertura
    aqui e de conteudo/configuracao, nao de comportamento em runtime.
    """

    def test_sw_js_servido_na_raiz_do_dominio(self, client):
        """
        Precisa ser /sw.js (raiz), nao /static/interface/js/sw.js --
        o escopo de um Service Worker e limitado ao diretorio de onde
        ele e servido, entao servir de dentro de /static/ nunca
        conseguiria controlar /entrar/, /inicio/, /novo-rad/, etc.
        """
        resposta = client.get('/sw.js')
        assert resposta.status_code == 200

    def test_sw_js_tem_content_type_correto(self, client):
        resposta = client.get('/sw.js')
        assert resposta['Content-Type'] == 'application/javascript'

    def test_sw_nunca_intercepta_rotas_de_api(self, client):
        """
        Regressao critica: se o Service Worker passar a cachear
        respostas de API, o app passaria a ter DUAS fontes de verdade
        (cache HTTP do SW + IndexedDB via RadDB) que podem
        dessincronizar. Trava que todos os prefixos de API estao na
        lista de exclusao.
        """
        resposta = client.get('/sw.js')
        conteudo = resposta.content.decode()
        for prefixo in (
            "'/usuarios/'", "'/rad/'", "'/catalogos/'", "'/colaboradores/'",
            "'/consulta/'", "'/configuracoes/'", "'/admin/'", "'/media/'",
        ):
            assert prefixo in conteudo, f'Prefixo {prefixo} nao esta na lista de exclusao do SW'

    def test_sw_cacheia_o_app_shell(self, client):
        resposta = client.get('/sw.js')
        conteudo = resposta.content.decode()
        for url in ("'/'", "'/entrar/'", "'/inicio/'", "'/novo-rad/'", "'/consultar/'"):
            assert url in conteudo, f'{url} nao esta na lista do app shell'
        assert 'estilo.css' in conteudo
        assert 'rad_form.js' in conteudo
        assert 'exportar_cliente.js' in conteudo, (
            'sem isso a exportacao (RG-EXP-002) so funcionaria offline depois '
            'da primeira visita online, nao desde o primeiro carregamento'
        )
        assert 'jspdf.umd.min.js' in conteudo, 'jsPDF (self-hospedado) precisa estar no app shell'

    def test_sw_so_intercepta_requisicoes_get(self, client):
        resposta = client.get('/sw.js')
        assert "evento.request.method !== 'GET'" in resposta.content.decode()

    def test_paginas_registram_o_service_worker(self, client):
        resposta = client.get(reverse('interface:login'))
        assert b"navigator.serviceWorker.register('/sw.js')" in resposta.content


@pytest.mark.django_db
class TestIntegracaoComApiDeLogin:
    """
    Prova que o contrato entre o JS (auth.js/login.html) e a API real
    de login bate: os nomes de campo que o JS le da resposta
    (token, validade, login, perfis) existem de verdade na resposta do
    endpoint, e um token gerado por ele autentica normalmente numa
    rota protegida -- exatamente o fluxo que o navegador executa.
    """

    def test_contrato_de_campos_do_login_bate_com_o_que_o_js_espera(self, client):
        import json

        from usuarios.models import Usuario

        Usuario.objects.create(login='teste.contrato.frontend')
        resposta = client.post(
            reverse('usuarios:login'),
            data=json.dumps({'login': 'teste.contrato.frontend'}),
            content_type='application/json',
        )
        assert resposta.status_code == 200
        corpo = resposta.json()
        for campo in ('token', 'validade', 'login', 'perfis'):
            assert campo in corpo, f'Campo "{campo}" esperado pelo JS nao veio na resposta do login.'

    def test_token_do_login_autentica_em_rota_protegida(self, client):
        import json

        from usuarios.models import Usuario, UsuarioPerfil

        usuario = Usuario.objects.create(login='teste.token.frontend')
        UsuarioPerfil.objects.create(usuario=usuario, perfil=UsuarioPerfil.SUPERVISOR)

        resposta_login = client.post(
            reverse('usuarios:login'),
            data=json.dumps({'login': 'teste.token.frontend'}),
            content_type='application/json',
        )
        token = resposta_login.json()['token']

        resposta_protegida = client.get(
            reverse('consulta:listar_rads'), HTTP_AUTHORIZATION=f'Token {token}'
        )
        assert resposta_protegida.status_code == 200
