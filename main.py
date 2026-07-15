import os
import logging
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import database as db
from handlers.callbacks import button_handler
from handlers.messages import start, handle_message, media_handler

# إعداد اللوج
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def post_init(application) -> None:
    await db.init_db()
    print("✅ تم تهيئة قاعدة البيانات بنجاح.")

if __name__ == '__main__':
    TOKEN = os.environ.get("TOKEN", "PUT_YOUR_NEW_TOKEN_HERE")
    
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    # تسجيل المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.VOICE | filters.AUDIO | filters.Document.ALL, media_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 البوت يعمل بجميع الميزات المتقدمة...")
    app.run_polling()