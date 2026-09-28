#!/bin/sh
python manage.py migrate
python manage.py carregar_catalogos
python manage.py shell << EOF
from usuarios.models import Usuario, UsuarioPerfil
if not Usuario.objects.filter(login='teste.dev').exists():
    u = Usuario.objects.create(login='teste.dev')
    UsuarioPerfil.objects.create(usuario=u, perfil='administrador')
    print('Usuario teste.dev criado')
else:
    print('Usuario teste.dev ja existe')
EOF
# 28/09/2026: --access-logfile - liga o log de acesso -- cada requisicao
# vira uma linha nos Logs do Render (caminho + bytes enviados), para
# descobrir o que causa os picos de banda de saida. Pode ser removido
# depois de identificada a causa.
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60 --access-logfile -
