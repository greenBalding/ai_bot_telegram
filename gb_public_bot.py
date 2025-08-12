import ollama
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
import os
import re
import json
import pdfplumber

# Configurações e pastas
LOG_FILE = "bot_interactions.log"
INSTRUCTIONS_FILE = "instructions.txt"
TOKEN_FILE = "token.txt"
MEMORIA_FILE = "memoria.json"  # Novo arquivo para guardar contexto
TEMP_DIR = "temp_files"

os.makedirs(TEMP_DIR, exist_ok=True)

# =========================
# Funções de memória
# =========================
def carregar_memoria():
    if os.path.exists(MEMORIA_FILE):
        with open(MEMORIA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_memoria(memoria):
    with open(MEMORIA_FILE, "w", encoding="utf-8") as f:
        json.dump(memoria, f, ensure_ascii=False, indent=2)

# =========================
# Funções existentes
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

def markdown_to_html(text):
    text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*(.*?)\*", r"<i>\1</i>", text)
    return text

# =========================
# Função adaptada para manter contexto
# =========================
def query_ollama(user_id, message_text, image_path=None):
    try:
        memoria = carregar_memoria()
        system_instructions = load_instructions()

        # Se não existir histórico para o usuário, cria
        if str(user_id) not in memoria:
            memoria[str(user_id)] = [{"role": "system", "content": system_instructions}]

        # Adiciona a mensagem do usuário ao histórico
        user_msg = {"role": "user", "content": message_text}
        if image_path:
            model_name = "llava:7b"  # multimodal
            user_msg["images"] = [image_path]
        else:
            model_name = "gemma3:1b"  # texto puro

        memoria[str(user_id)].append(user_msg)

        # Mantém no máximo as últimas 10 interações (para não crescer demais)
        if len(memoria[str(user_id)]) > 20:
            memoria[str(user_id)] = memoria[str(user_id)][-20:]

        # Chama o modelo com todo o histórico
        response = ollama.chat(
            model=model_name,
            messages=memoria[str(user_id)]
        )

        bot_reply = response["message"]["content"]

        # Salva resposta no histórico
        memoria[str(user_id)].append({"role": "assistant", "content": bot_reply})

        # Salva memória no disco
        salvar_memoria(memoria)

        return bot_reply
    except Exception as e:
        return f"Error interacting with AI model: {e}"

# =========================
# Funções para PDFs
# =========================
def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
        return text.strip()
    except Exception as e:
        return f"Erro ao ler PDF: {e}"

# =========================
# Handlers do Telegram
# =========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = f"@{context.bot.username}"
    user_message = update.message.text
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"

    is_private = update.message.chat.type == "private"
    is_mentioned = bot_username.lower() in user_message.lower()
    is_reply_to_bot = (
        update.message.reply_to_message
        and update.message.reply_to_message.from_user.id == context.bot.id
    )

    if is_private or is_mentioned or is_reply_to_bot:
        clean_message = user_message.replace(bot_username, "").strip()
        reply = query_ollama(user_id, clean_message)
        log_interaction(user_id, username, user_message, reply)
        styled_reply = markdown_to_html(reply)
        await update.message.reply_text(styled_reply, parse_mode="HTML")

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = f"@{context.bot.username}"
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"
    caption = update.message.caption or "Descreva a imagem"

    is_private = update.message.chat.type == "private"
    is_mentioned = caption and bot_username.lower() in caption.lower()
    is_reply_to_bot = (
        update.message.reply_to_message
        and update.message.reply_to_message.from_user.id == context.bot.id
    )

    if is_private or is_mentioned or is_reply_to_bot:
        caption = caption.replace(bot_username, "").strip()

        photo = update.message.photo[-1]
        file = await photo.get_file()
        image_path = os.path.join(TEMP_DIR, f"{user_id}_{datetime.now().timestamp()}.jpg")
        await file.download_to_drive(image_path)

        reply = query_ollama(user_id, caption, image_path=image_path)
        log_interaction(user_id, username, f"[Imagem] {caption}", reply)

        styled_reply = markdown_to_html(reply)
        await update.message.reply_text(styled_reply, parse_mode="HTML")

        try:
            os.remove(image_path)
        except Exception:
            pass

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_username = f"@{context.bot.username}"
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"
    caption = update.message.caption or ""

    is_private = update.message.chat.type == "private"
    is_mentioned = caption and bot_username.lower() in caption.lower()
    is_reply_to_bot = (
        update.message.reply_to_message
        and update.message.reply_to_message.from_user.id == context.bot.id
    )

    if is_private or is_mentioned or is_reply_to_bot:
        document = update.message.document
        if document.mime_type == "application/pdf":
            file = await document.get_file()
            pdf_path = os.path.join(TEMP_DIR, f"{user_id}_{datetime.now().timestamp()}.pdf")
            await file.download_to_drive(pdf_path)

            pdf_text = extract_text_from_pdf(pdf_path)
            try:
                os.remove(pdf_path)
            except Exception:
                pass

            if not pdf_text:
                reply = "Não consegui extrair texto desse PDF."
            else:
                reply = query_ollama(user_id, pdf_text)

            log_interaction(user_id, username, "[Documento PDF]", reply)
            styled_reply = markdown_to_html(reply)
            await update.message.reply_text(styled_reply, parse_mode="HTML")
        else:
            await update.message.reply_text("Por favor, envie um arquivo PDF válido.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Oi! Eu sou seu bot multimodal rodando localmente.\n"
        "Vou responder suas mensagens privadas ou se me mencionarem em grupos."
    )

if __name__ == "__main__":
    BOT_TOKEN = load_token()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(MessageHandler(filters.Document.PDF, handle_document))

    print("Bot is running...")
    app.run_polling()