from django.urls import path

from . import views

app_name = 'core'

urlpatterns = [
    path('', views.home, name='home'),
    path('pavimentos/', views.pavimento_list, name='pavimento_list'),
    path('relatorios/resumo-aco/', views.relatorio_resumo_aco, name='relatorio_resumo_aco'),
    path('pavimentos/novo/', views.pavimento_create, name='pavimento_create'),
    path('pavimentos/<int:pk>/', views.pavimento_detail, name='pavimento_detail'),
    path('pavimentos/<int:pk>/excluir/', views.pavimento_delete, name='pavimento_delete'),
    path('pavimentos/<int:pk>/duplicar-grupo/', views.grupo_duplicar, name='grupo_duplicar'),
    path('pavimentos/<int:pk>/copiar/', views.pavimento_copiar, name='pavimento_copiar'),
    path('pavimentos/<int:pk>/elementos/<int:elemento_pk>/excluir/',
         views.elemento_delete, name='elemento_delete'),
    path('pavimentos/<int:pk>/elementos/<int:elemento_pk>/editar/',
         views.elemento_edit, name='elemento_edit'),
]
