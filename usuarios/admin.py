from django.contrib import admin

from .models import Token, Usuario, UsuarioPerfil


class UsuarioPerfilInline(admin.TabularInline):
    model = UsuarioPerfil
    extra = 1
    max_num = 2  # Ate 2 perfis simultaneos por login (PRM-025)


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ('login', 'ativo', 'data_criacao', 'lista_perfis')
    list_filter = ('ativo',)
    search_fields = ('login',)
    inlines = [UsuarioPerfilInline]


@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'validade', 'data_criacao', 'dispositivo', 'expirado')
    list_filter = ('validade',)
    search_fields = ('usuario__login', 'token')
    readonly_fields = ('token', 'data_criacao')
