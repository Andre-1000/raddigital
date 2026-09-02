from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('dados/', views.dados, name='dados'),
    path('exportar-excel/', views.exportar_excel, name='exportar_excel'),
]
