"""
Validacao de senha propria (30/07/2026) -- nao usa os validators padrao
do Django (AUTH_PASSWORD_VALIDATORS em settings.py) porque alguns deles
(ex.: UserAttributeSimilarityValidator) esperam um objeto com a
interface do django.contrib.auth.User (get_username, etc.), que o model
Usuario deste projeto nao implementa -- o Sistema RAD nunca usou
django.contrib.auth pra autenticacao de usuario final, so pro /admin/.
"""
TAMANHO_MINIMO_SENHA = 8

SENHAS_COMUNS_PROIBIDAS = {
    '12345678', '123456789', 'senha123', 'password', 'qwerty123',
    'admin123', '11111111', '00000000', 'abc12345', 'trivia123',
}


def validar_senha(senha, login=None):
    """Retorna lista de mensagens de erro (vazia se a senha for valida)."""
    erros = []

    if not senha or len(senha) < TAMANHO_MINIMO_SENHA:
        erros.append(f'A senha deve ter no mínimo {TAMANHO_MINIMO_SENHA} caracteres.')
        return erros  # sem checagem adicional se ja falhou no basico

    if senha.isdigit():
        erros.append('A senha não pode ser só números.')

    if senha.lower() in SENHAS_COMUNS_PROIBIDAS:
        erros.append('Essa senha é muito comum. Escolha outra.')

    if login and senha.lower() == login.lower():
        erros.append('A senha não pode ser igual ao login.')

    return erros
