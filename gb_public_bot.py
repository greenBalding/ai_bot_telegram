import ollama
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
import os

# python gb_public_bot.py

# =========================
# Configurações e Arquivos
# =========================

LOG_FILE = "bot_interactions.log"
INSTRUCTIONS_FILE = "instructions.txt"
TOKEN_FILE = "token.txt"
TEMP_DIR = "temp_images"

# Criar pasta para imagens temporárias
os.makedirs(TEMP_DIR, exist_ok=True)

# =========================
# Funções Utilitárias
# =========================

def load_token(file_path=TOKEN_FILE):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read().strip()

def load_instructions(file_path=INSTRUCTIONS_FILE):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""

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

def query_ollama(message_text, image_path=None):
    try:
        system_instructions = load_instructions()
        user_msg = {"role": "user", "content": message_text}

        if image_path:
            user_msg["images"] = [image_path]

        response = ollama.chat(
            model="llava:7b",  # ou "elve"
            messages=[
                {"role": "system", "content": system_instructions},
                user_msg
            ]
        )
        return response["message"]["content"]
    except Exception as e:
        return f"Error interacting with AI model: {e}"

# =========================
# Handlers do Telegram
# =========================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"

    reply = query_ollama(user_message)

    log_interaction(user_id, username, user_message, reply)

    await update.message.reply_text(reply)

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"
    caption = update.message.caption or "Descreva a imagem"

    photo = update.message.photo[-1]  # pega a maior resolução
    file = await photo.get_file()
    image_path = os.path.join(TEMP_DIR, f"{user_id}_{datetime.now().timestamp()}.jpg")
    await file.download_to_drive(image_path)

    reply = query_ollama(caption, image_path=image_path)

    log_interaction(user_id, username, f"[Imagem] {caption}", reply)

    await update.message.reply_text(reply)

    # Remove a imagem temporária
    try:
        os.remove(image_path)
    except:
        pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Oi! Eu sou seu bot com modelo multimodal rodando localmente.\n"
        "Envie uma mensagem de texto ou uma imagem com legenda para análise."
    )

# =========================
# Execução do Bot
# =========================

if __name__ == "__main__":
    BOT_TOKEN = load_token()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))

    print("Bot is running...")
    app.run_polling()