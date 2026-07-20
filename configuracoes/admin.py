from django.contrib import admin

from .models import CampoFormulario


@admin.register(CampoFormulario)
class CampoFormularioAdmin(admin.ModelAdmin):
    list_display = ('rotulo', 'chave', 'habilitado', 'atualizado_em', 'atualizado_por')
    list_filter = ('habilitado',)
    search_fields = ('chave', 'rotulo')
