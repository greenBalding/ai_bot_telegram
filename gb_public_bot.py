import ollama
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
import os

# =========================
# Configurações e Arquivos
# =========================

LOG_FILE = "bot_interactions.log"
INSTRUCTIONS_FILE = "instructions.txt"
TOKEN_FILE = "token.txt"

# =========================
# Funções Utilitárias
# =========================

# Função para ler token do bot
def load_token(file_path=TOKEN_FILE):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()

# Função para carregar instruções do arquivo
def load_instructions(file_path=INSTRUCTIONS_FILE):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""  # Se não existir, retorna vazio

# Função para gravar logs
def log_interaction(user_id, username, user_message, bot_reply):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] UserID: {user_id} | Username: {username}\n")
        f.write(f"User: {user_message}\n")
        f.write(f"Bot: {bot_reply}\n")
        f.write("-" * 50 + "\n")

# =========================
# Comunicação com o Ollama
# =========================

def query_gemma3(message_text):
    try:
        system_instructions = load_instructions()

        response = ollama.chat(
            model="gemma3:4b",
            messages=[
                {"role": "system", "content": system_instructions},  # Instruções fixas
                {"role": "user", "content": message_text}
            ]
        )
        return response["message"]["content"]
    except Exception as e:
        return f"Error interacting with AI model: {e}"

# =========================
# Handlers do Telegram
# =========================

# Responde mensagens comuns
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"

    reply = query_gemma3(user_message)

    log_interaction(user_id, username, user_message, reply)

    await update.message.reply_text(reply)

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Oi! Eu sou seu bot com Gemma 3 rodando localmente.\n"
        "Minhas respostas seguem as instruções do arquivo instructions.txt."
    )

# =========================
# Execução do Bot
# =========================

if __name__ == "__main__":
    BOT_TOKEN = load_token()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()