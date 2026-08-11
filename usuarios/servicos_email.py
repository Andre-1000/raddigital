"""
Envio de e-mail transacional (redefinicao de senha, 30/07/2026).

Usa o backend configurado em settings.EMAIL_BACKEND. Sem as variaveis
de ambiente EMAIL_* configuradas, o Django usa o backend "console" por
padrao (imprime o e-mail no log em vez de enviar de verdade) -- e assim
mesmo em producao, ate Andre configurar uma conta SMTP real. Ver
CLAUDE.md / README para a lista de variaveis necessarias.
"""
from django.conf import settings
from django.core.mail import send_mail


def enviar_email_redefinicao_senha(usuario, token):
    link = f'{settings.URL_BASE_SITE}/redefinir-senha/?token={token}'
    corpo = (
        'Olá,\n\n'
        f'Recebemos uma solicitação para redefinir a senha da conta "{usuario.login}" '
        'no Sistema RAD.\n\n'
        'Para criar uma nova senha, acesse o link abaixo (válido por 1 hora):\n'
        f'{link}\n\n'
        'Se você não solicitou isso, pode ignorar este e-mail com segurança -- '
        'sua senha atual continua válida.\n\n'
        'Sistema RAD Digital'
    )
    send_mail(
        subject='Redefinição de senha — Sistema RAD',
        message=corpo,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[usuario.email],
        fail_silently=False,
    )
