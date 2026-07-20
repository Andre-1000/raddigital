from django.contrib import admin

from .models import ColaboradorCadastro


@admin.register(ColaboradorCadastro)
class ColaboradorCadastroAdmin(admin.ModelAdmin):
    list_display = ('registro_empresa', 'nome', 'ativo', 'data_criacao')
    list_filter = ('ativo',)
    search_fields = ('registro_empresa', 'nome')
