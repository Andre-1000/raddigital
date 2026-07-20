# Sistema RAD — imagem de producao.
#
# Provider-agnostica: a mesma imagem roda em Railway, Render, AWS
# ECS/Fargate, Azure Container Apps, ou qualquer orquestrador que
# aceite um container Docker comum. A escolha do provedor de nuvem
# (ainda pendente, ver README) so muda ONDE esta imagem roda, nao
# como ela e construida.

FROM python:3.12-slim AS base

# psycopg2-binary evita precisar de libpq-dev, mas o build ainda
# precisa de um compilador para outras dependencias nativas (Pillow).
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libjpeg62-turbo-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=config.settings

COPY requirements.txt .
# playwright so e usado nos testes (interface/browser_tests/) -- nao
# faz sentido na imagem de producao, que nunca roda pytest.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y playwright

COPY . .

# Gera os arquivos estaticos com hash (WhiteNoise) em build time, nao
# em runtime -- assim o container nao precisa de permissao de escrita
# no filesystem para servir CSS/JS.
RUN DEBUG=False SECRET_KEY=build-time-only-nao-usado-em-runtime \
    python manage.py collectstatic --noinput

EXPOSE 8000

# --workers: ajustar conforme os recursos do plano contratado.
# --timeout 60: geracao de PDF/DOCX no backend pode levar alguns
# segundos para RADs grandes com muitos anexos.
CMD ["gunicorn", "config.wsgi:application", \
     "--bind", "0.0.0.0:8000", \
     "--workers", "3", \
     "--timeout", "60"]
