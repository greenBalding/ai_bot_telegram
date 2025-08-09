import ollama
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
import os

# Path to save the log file
LOG_FILE = "bot_interactions.log"

# Function to write logs
def log_interaction(user_id, username, user_message, bot_reply):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] UserID: {user_id} | Username: {username}\n")
        f.write(f"User: {user_message}\n")
        f.write(f"Bot: {bot_reply}\n")
        f.write("-" * 50 + "\n")

# Function to read the telegram bot token from a file
def load_token(file_path="token.txt"):
    with open(file_path, "r") as file:
        return file.read().strip()

# Your Telegram bot token here
BOT_TOKEN = load_token()

# Function to send user message to Ollama's Gemma 3 and get a response
def query_gemma3(message_text):
    try:
        response = ollama.chat(
            model="gemma3:4b",
            messages=[{"role": "user", "content": message_text}]
        )
        return response['message']['content']
    except Exception as e:
        return f"Error interacting with AI model: {e}"

# Handler for Telegram messages
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.message.from_user.id
    username = update.message.from_user.username or "Unknown"
    
    reply = query_gemma3(user_message)

    # Log the conversation
    log_interaction(user_id, username, user_message, reply)

    await update.message.reply_text(reply)

# Start command handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! I’m your AI-powered Telegram bot running Gemma 3 locally. Send me a message!"
    )

if __name__ == "__main__":
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot is running...")
    app.run_polling()