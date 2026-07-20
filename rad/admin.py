from django.contrib import admin

from .models import (
    Rad,
    RadAmv,
    RadAmvAcao,
    RadAmvDefeito,
    RadAnexo,
    RadColaborador,
    RadEquipe,
    RadLinha,
    RadServico,
    RadVia,
)


class RadLinhaInline(admin.TabularInline):
    model = RadLinha
    extra = 0


class RadViaInline(admin.TabularInline):
    model = RadVia
    extra = 0


class RadEquipeInline(admin.TabularInline):
    model = RadEquipe
    extra = 0


class RadServicoInline(admin.TabularInline):
    model = RadServico
    extra = 0


class RadColaboradorInline(admin.TabularInline):
    model = RadColaborador
    extra = 0


class RadAnexoInline(admin.TabularInline):
    model = RadAnexo
    extra = 0


@admin.register(Rad)
class RadAdmin(admin.ModelAdmin):
    list_display = (
        'numero_rad',
        'numero_os',
        'numero_sa',
        'numero_execucao',
        'status',
        'usuario',
        'data_preenchimento',
    )
    list_filter = ('status', 'tipo_manutencao')
    search_fields = ('numero_rad', 'numero_os', 'usuario__login')
    readonly_fields = ('numero_rad', 'numero_execucao', 'sync_id_tentativa')
    inlines = [
        RadLinhaInline,
        RadViaInline,
        RadEquipeInline,
        RadServicoInline,
        RadColaboradorInline,
        RadAnexoInline,
    ]


@admin.register(RadAmv)
class RadAmvAdmin(admin.ModelAdmin):
    list_display = ('rad', 'mch', 'modelo_mch', 'via_mch', 'linha_mch')
    search_fields = ('rad__numero_rad', 'mch__identificacao')


admin.site.register(RadAmvDefeito)
admin.site.register(RadAmvAcao)
