import os
import requests
from flask import Flask, request, jsonify
from typing import Dict, Any

app = Flask(__name__)

# Configurações iniciais
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
PORT = int(os.getenv("PORT", 10000))

# Verificação das variáveis de ambiente
if not all([TELEGRAM_TOKEN, OPENROUTER_API_KEY]):
    raise RuntimeError("Variáveis de ambiente necessárias não configuradas!")

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

# Personalidade da Melissa
SYSTEM_PROMPT = """
Você é Melissa, uma carioca safada de 25 anos com personalidade ousada e provocante. Suas características:
- Recepcionista em uma academia
- Adora samba, funk e pagode
- Tem um gato chamado Loki
- Viciada em novelas
- Fala com gírias cariocas ('e aí gato', 'fala sério')

Regras:
1. Seja direta e envolvente (1-2 frases)
2. Use no máximo 2 emojis por mensagem
3. Mantenha o tom flertante e provocante
4. Demonstre personalidade única

Emojis permitidos: 😏🔥😈🍑💦🤭👠🍒
"""

def gerar_resposta(prompt: str) -> str:
    """Gera resposta usando Claude 3 Haiku via OpenRouter"""
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://yourdomain.com",
        "X-Title": "MelissaBot"
    }

    payload = {
        "model": "anthropic/claude-3-haiku",
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.8,
        "max_tokens": 150
    }

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        else:
            error_msg = response.json().get("error", {}).get("message", "Erro desconhecido")
            app.logger.error(f"OpenRouter error: {error_msg}")
            return random.choice([
                "Ops, tive um branco... fala de novo? 😏",
                "A conexão falou... vamos tentar de novo? 🔥"
            ])
            
    except Exception as e:
        app.logger.error(f"Error generating response: {str(e)}")
        return "Tive um probleminha aqui... me manda de novo? 🤭"

@app.route(f"/{TELEGRAM_TOKEN}", methods=["POST"])
def webhook():
    """Endpoint principal para mensagens do Telegram"""
    data: Dict[str, Any] = request.get_json()
    
    if not data.get("message"):
        return jsonify({"status": "error", "message": "No message found"}), 400
        
    message = data["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "").strip()
    
    # Resposta para /start
    if text.startswith("/start"):
        resposta = "E aí gato! Eu sou a Melissa, sua acompanhante virtual... 😏 O que vamos aprontar hoje?"
    elif text:
        resposta = gerar_resposta(text)
    else:
        resposta = "Manda algo mais gostoso pra eu responder... 👀"
    
    # Envia a resposta
    requests.post(
        TELEGRAM_API_URL,
        json={"chat_id": chat_id, "text": resposta},
        timeout=5
    )
    
    return jsonify({"status": "success"})

@app.route("/")
def health_check():
    """Endpoint de verificação de saúde"""
    return jsonify({
        "status": "online",
        "service": "MelissaBot",
        "model": "anthropic/claude-3-haiku",
        "version": "2.0"
    })

if __name__ == "__main__":
    # Log inicial para debug
    print("="*50)
    print(f"✅ Bot iniciado com sucesso!")
    print(f"🔑 Modelo: anthropic/claude-3-haiku")
    print(f"🌐 Porta: {PORT}")
    print("="*50)
    
    app.run(host="0.0.0.0", port=PORT)
