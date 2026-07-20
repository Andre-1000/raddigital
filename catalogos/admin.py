from django.contrib import admin

from .models import (
    CatAcaoAmv,
    CatEquipe,
    CatLinha,
    CatLocal,
    CatMch,
    CatMotivoAtraso,
    CatServico,
    CatTipoDefeitoAmv,
    CatTipoManutencao,
    CatVia,
)


@admin.register(CatEquipe)
class CatEquipeAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome')
    search_fields = ('codigo', 'nome')


@admin.register(CatLinha)
class CatLinhaAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'nome')
    search_fields = ('codigo', 'nome')


@admin.register(CatLocal)
class CatLocalAdmin(admin.ModelAdmin):
    list_display = ('sigla', 'nome', 'categoria')
    list_filter = ('categoria',)
    search_fields = ('sigla', 'nome')


@admin.register(CatTipoManutencao)
class CatTipoManutencaoAdmin(admin.ModelAdmin):
    list_display = ('nome',)


@admin.register(CatVia)
class CatViaAdmin(admin.ModelAdmin):
    list_display = ('nome',)


@admin.register(CatServico)
class CatServicoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'requer_amv', 'requer_descricao', 'ativo')
    list_filter = ('requer_amv', 'requer_descricao', 'ativo')
    search_fields = ('nome',)


@admin.register(CatMotivoAtraso)
class CatMotivoAtrasoAdmin(admin.ModelAdmin):
    list_display = ('nome', 'requer_descricao')


@admin.register(CatMch)
class CatMchAdmin(admin.ModelAdmin):
    list_display = ('identificacao', 'modelo', 'via', 'ur', 'local_amv', 'linha')
    list_filter = ('linha', 'modelo')
    search_fields = ('identificacao', 'ur', 'local_amv')


@admin.register(CatTipoDefeitoAmv)
class CatTipoDefeitoAmvAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ativo')
    list_filter = ('ativo',)


@admin.register(CatAcaoAmv)
class CatAcaoAmvAdmin(admin.ModelAdmin):
    list_display = ('nome', 'ativo')
    list_filter = ('ativo',)
