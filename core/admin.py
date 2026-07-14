from django.contrib import admin

from .models import Elemento, Pavimento


class ElementoInline(admin.TabularInline):
    model = Elemento
    extra = 1


@admin.register(Pavimento)
class PavimentoAdmin(admin.ModelAdmin):
    list_display = ['nome', 'criado_em']
    search_fields = ['nome']
    inlines = [ElementoInline]


@admin.register(Elemento)
class ElementoAdmin(admin.ModelAdmin):
    list_display = ['pavimento', 'categoria', 'tipo', 'nome', 'identificador', 'qtde',
                    'diametro', 'comprimento', 'peso_linear', 'peso_unitario', 'peso_total']
    list_filter = ['categoria', 'tipo', 'pavimento']
    search_fields = ['nome', 'identificador']
