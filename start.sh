#!/bin/sh 
python manage.py migrate 
python manage.py carregar_catalogos 
exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3 --timeout 60 
