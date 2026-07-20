from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Mudanca de negocio (16/07/2026):
    1. O campo antigo "SA" e renomeado para "OS" -- mesmas validacoes e
       regras (RG-IDENT-004 a 012, VLD-001), so muda o nome/rotulo.
    2. Um novo campo independente "N. SA" e adicionado: numerico, ate
       10 caracteres, obrigatorio (nova regra VLD-028).
    """

    dependencies = [
        ('rad', '0003_radanexo_categoria_foto_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='rad',
            old_name='numero_sa',
            new_name='numero_os',
        ),
        migrations.RenameIndex(
            model_name='rad',
            old_name='idx_rad_numero_sa',
            new_name='idx_rad_numero_os',
        ),
        migrations.AlterField(
            model_name='rad',
            name='numero_os',
            field=models.IntegerField(help_text='OS informada pelo usuario. Pode se repetir.'),
        ),
        migrations.AddField(
            model_name='rad',
            name='numero_sa',
            field=models.CharField(
                default='',
                help_text='N. SA. Numerico, ate 10 caracteres. Campo obrigatorio, independente da OS.',
                max_length=10,
            ),
            preserve_default=False,
        ),
    ]
