from dotenv import load_dotenv
import os
import logging

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes


load_dotenv()
TOKEN = os.getenv("TOKEN") or os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Olá! Bot de vendinhas Herosaga pronto.")


def main() -> None:
    if not TOKEN:
        print("TOKEN não encontrado. Copie .env.example para .env e adicione o token.")
        return

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    print("Bot iniciando... pressione Ctrl+C para parar")
    app.run_polling()


if __name__ == "__main__":
    main()
