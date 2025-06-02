import os
import sys
import time
import requests
import subprocess
import traceback
from flask import Flask, request, jsonify
from typing import Dict, Any, Optional

# ======================
# CONFIGURAÇÃO INICIAL
# ======================
app = Flask(__name__)

# Constantes
MAX_RETRIES = 3
REQUEST_TIMEOUT = 10
TELEGRAM_API_TIMEOUT = 5

# ======================
# VERIFICAÇÕES INICIAIS
# ======================
def check_environment() -> None:
    """Verifica todas as dependências e variáveis de ambiente"""
    errors = []
    
    # 1. Verifica variáveis de ambiente
    required_env_vars = ['TELEGRAM_TOKEN', 'OPENROUTER_API_KEY']
    for var in required_env_vars:
        if not os.getenv(var):
            errors.append(f"Variável de ambiente faltando: {var}")

    # 2. Verifica dependências Python
    required_packages = {'gunicorn', 'flask', 'requests', 'python-dotenv'}
    try:
        installed = {pkg.split('==')[0].lower() for pkg in subprocess.check_output(
            [sys.executable, '-m', 'pip', 'freeze']).decode().split()}
        missing = required_packages - installed
        if missing:
            errors.append(f"Pacotes faltando: {', '.join(missing)}")
    except Exception as e:
        errors.append(f"Erro ao verificar pacotes: {str(e)}")

    # 3. Verifica acesso a APIs externas
    try:
        requests.get("https://api.telegram.org", timeout=5)
    except Exception as e:
        errors.append(f"Não conseguiu acessar API do Telegram: {str(e)}")

    if errors:
        error_msg = "🚨 Erros de configuração:\n" + "\n".join(errors)
        app.logger.critical(error_msg)
        raise RuntimeError(error_msg)

    print("✅ Ambiente verificado com sucesso!")

# Executa as verificações ao iniciar
try:
    check_environment()
except Exception as e:
    print(f"❌ Falha crítica: {str(e)}")
    sys.exit(1)

# ======================
# CONFIGURAÇÕES DINÂMICAS
# ======================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PORT = int(os.getenv("PORT", 10000))
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# Personalidade da Melissa
SYSTEM_PROMPT = """
[CONTEXTO]
Você é Melissa, uma carioca de 25 anos, recepcionista de academia com personalidade:
- Ousada e provocante, mas não vulgar
- Adora samba, funk e novelas
- Tem um gato chamado Loki
- Fala com gírias cariocas naturais

[REGRAS]
1. Respostas curtas (1-2 frases)
2. Máximo 2 emojis por mensagem
3. Tom flertante e descontraído
4. Nunca seja genérica ou robótica

[EXEMPLOS]
Usuário: Oi
Melissa: E aí gato! Tá me procurando por quê? 😏

Usuário: /start
Melissa: Oiê! Eu sou a Melissa, sua acompanhante preferida... Bora bater um papo? 🔥
"""

# ======================
# CORE FUNCTIONS
# ======================
def send_telegram_message(chat_id: int, text: str) -> bool:
    """Envia mensagem com retry automático"""
    for attempt in range(MAX_RETRIES):
        try:
            response = requests.post(
                TELEGRAM_API_URL,
                json={"chat_id": chat_id, "text": text},
                timeout=TELEGRAM_API_TIMEOUT
            )
            response.raise_for_status()
            return True
        except Exception as e:
            app.logger.error(f"Tentativa {attempt + 1} falhou: {str(e)}")
            time.sleep(1)
    
    app.logger.error(f"Falha ao enviar mensagem após {MAX_RETRIES} tentativas")
    return False

def generate_response(prompt: str) -> str:
    """Gera resposta com fallback robusto"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://melissa-bot.com",
        "X-Title": "MelissaBot"
    }

    payload = {
        "model": "anthropic/claude-3-haiku",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.8,
        "max_tokens": 150,
        "timeout": REQUEST_TIMEOUT
    }

    # Tentativa principal com OpenRouter
    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        
        error_msg = response.json().get("error", {}).get("message", "Erro desconhecido")
        app.logger.error(f"OpenRouter API error: {error_msg}")
    
    except Exception as e:
        app.logger.error(f"Falha na API: {str(e)}")
        traceback.print_exc()

    # Fallback local
    fallback_responses = [
        "Tô meio lenta hoje... manda de novo? 😅",
        "A conexão falou... bora tentar outra vez? 🔥",
        "Nem ouvi direito... repete aí gato! 😏"
    ]
    return random.choice(fallback_responses)

# ======================
# ROTAS PRINCIPAIS
# ======================
@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    """Endpoint principal com tratamento completo de erros"""
    try:
        data: Dict[str, Any] = request.get_json()
        app.logger.debug(f"Dados recebidos: {data}")

        if not data.get("message"):
            app.logger.warning("Mensagem vazia recebida")
            return jsonify({"status": "error", "message": "Invalid request"}), 400

        message = data["message"]
        chat_id = message["chat"]["id"]
        text = message.get("text", "").strip()

        # Resposta para /start
        if text.startswith("/start"):
            response_text = "E aí gato! Eu sou a Melissa, sua acompanhante virtual... 😏 O que vamos aprontar hoje?"
        elif text:
            response_text = generate_response(text)
        else:
            response_text = "Manda algo mais interessante pra eu responder... 👀"

        # Envio com tratamento de erro
        if not send_telegram_message(chat_id, response_text):
            app.logger.error("Falha crítica ao enviar para Telegram")

        return jsonify({"status": "success"})

    except Exception as e:
        app.logger.critical(f"Erro não tratado: {str(e)}")
        traceback.print_exc()
        return jsonify({"status": "error", "message": "Internal server error"}), 500

@app.route("/health")
def health_check():
    """Endpoint de saúde com verificação profunda"""
    checks = {
        "api_telegram": False,
        "api_openrouter": False,
        "environment": True
    }

    # Teste Telegram
    try:
        response = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getMe", timeout=3)
        checks["api_telegram"] = response.status_code == 200
    except:
        pass

    # Teste OpenRouter
    try:
        response = requests.head("https://openrouter.ai/api/v1", timeout=3)
        checks["api_openrouter"] = response.status_code == 200
    except:
        pass

    status = "healthy" if all(checks.values()) else "degraded"
    
    return jsonify({
        "status": status,
        "checks": checks,
        "version": "2.0",
        "model": "anthropic/claude-3-haiku"
    })

# ======================
# INICIALIZAÇÃO
# ======================
if __name__ == "__main__":
    print("\n" + "="*50)
    print(f"🔥 Melissa Bot - Versão 2.0")
    print(f"🔧 Porta: {PORT}")
    print(f"🤖 Modelo: anthropic/claude-3-haiku")
    print(f"🛡️  Ambiente verificado com sucesso!")
    print("="*50 + "\n")
    
    app.run(host="0.0.0.0", port=PORT, debug=False)
