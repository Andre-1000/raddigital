"""
Adiciona o "campo" exportar_pdf_oficial a CampoFormulario -- na
verdade nao e um campo do formulario, e uma funcionalidade do sistema
(exportacao em PDF no layout oficial), mas reaproveita a mesma tabela
e a mesma tela de Configuracoes ja existente, exatamente como pedido
(22/07/2026): "onde o administrador pode habilitar ou desabilitar os
campos" deve ser tambem onde ele liga/desliga o PDF.

Comeca DESABILITADO por padrao -- o servidor de producao ainda nao tem
o LibreOffice instalado (ver rad/exportacao_oficial.py::gerar_pdf_oficial_bytes),
entao a exportacao em PDF geraria erro se fosse habilitada agora. Deixa
estruturado para o dia em que o LibreOffice for instalado (junto da
troca de banco/plano de hospedagem): so ligar o toggle nesta tela, sem
precisar mexer em codigo.
"""
from django.db import migrations


def criar_flag_pdf(apps, schema_editor):
    CampoFormulario = apps.get_model('configuracoes', 'CampoFormulario')
    CampoFormulario.objects.get_or_create(
        chave='exportar_pdf_oficial',
        defaults={
            'rotulo': 'Exportação em PDF (layout oficial)',
            'habilitado': False,
            'obrigatorio': False,
        },
    )


def remover_flag_pdf(apps, schema_editor):
    CampoFormulario = apps.get_model('configuracoes', 'CampoFormulario')
    CampoFormulario.objects.filter(chave='exportar_pdf_oficial').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('configuracoes', '0003_campo_obrigatorio'),
    ]

    operations = [
        migrations.RunPython(criar_flag_pdf, remover_flag_pdf),
    ]
