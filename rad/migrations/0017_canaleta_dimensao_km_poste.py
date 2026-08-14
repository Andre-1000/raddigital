# Gerado manualmente em 14/08/2026 -- adiciona os campos Km/Poste
# Inicial e Km/Poste Final em cada linha de Dimensões da Canaleta (ver
# rad/models.py::RadCanaletaDimensao). Campos opcionais, texto livre
# (mesmo formato/mascara do campo Km/Poste geral do RAD) -- nenhuma
# linha de dado precisa ser migrada aqui, e so uma coluna nova.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('rad', '0016_canaleta_dimensoes_e_justificativa'),
    ]

    operations = [
        migrations.AddField(
            model_name='radcanaletadimensao',
            name='km_poste_inicial',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.AddField(
            model_name='radcanaletadimensao',
            name='km_poste_final',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
    ]
