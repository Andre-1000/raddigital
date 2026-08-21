# Gerado manualmente em 21/08/2026 -- remove o campo 'exportado'
# (booleano, orfao: nunca era setado nem filtrado em lugar nenhum do
# sistema -- confirmado 0 registros com valor True em producao antes
# desta migration) e adiciona data_ultima_exportacao_excel no lugar.
# Guardar a DATA em vez de um SIM/NAO da historico/auditoria de quando
# cada RAD foi exportado, e permite que o endpoint de exportacao
# (consulta/views.py::exportar_excel) filtre automaticamente so o que
# ainda nao foi exportado, sem controle manual.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rad', '0017_canaleta_dimensao_km_poste'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='rad',
            name='exportado',
        ),
        migrations.AddField(
            model_name='rad',
            name='data_ultima_exportacao_excel',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
