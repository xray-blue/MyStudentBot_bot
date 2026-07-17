import os
import logging
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
import database as db
from handlers.callbacks import button_handler
from handlers.messages import start, handle_message, media_handler, cmd_add, cmd_grades, cmd_tasks

# إعداد اللوج
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# ==========================================
# 🧠 نظام التنبيهات الذكي (يعمل في الخلفية)
# ==========================================
async def reminder_loop(application):
    """دالة تعمل في الخلفية كل 60 ثانية لفحص التنبيهات"""
    while True:
        try:
            # جلب المهام التي حان وقت تنبيهها
            reminders = await db.get_pending_reminders()
            
            for task in reminders:
                user_id = task['user_id']
                title = task['title']
                due_date = task['due_date']
                remind_hours = task['remind_before']
                
                # صياغة رسالة التنبيه
                msg = f"⏰ <b>تذكير بمهمة قادمة!</b>\n\n📌 العنوان: {title}\n📅 الموعد: {due_date}\n🔔 تم التنبيه قبل {remind_hours} ساعة"
                
                try:
                    # إرسال التنبيه للمستخدم
                    await application.bot.send_message(chat_id=user_id, text=msg, parse_mode='HTML')
                    # تعليم المهمة بأنه تم تنبيهها لكي لا تتكرر
                    await db.mark_as_notified(task['id'])
                    logging.info(f"تم إرسال تنبيه للمستخدم {user_id} عن مهمة: {title}")
                except Exception as e:
                    logging.error(f"فشل إرسال تنبيه للمستخدم {user_id}: {e}")
                    
        except Exception as e:
            logging.error(f"خطأ في خيط التنبيهات: {e}")
            
        # النوم لمدة 60 ثانية ثم الفحص مرة أخرى
        await asyncio.sleep(60)

# ==========================================
# تشغيل البوت
# ==========================================
async def post_init(application) -> None:
    await db.init_db()
    print("✅ تم تهيئة قاعدة البيانات بنجاح.")
    
    # إطلاق خيط التنبيهات في الخلفية بشكل موازي
    asyncio.create_task(reminder_loop(application))
    print("⏰ تم تفعيل نظام التنبيهات في الخلفية بنجاح.")

if __name__ == '__main__':
    TOKEN = os.environ.get("TOKEN", "PUT_YOUR_NEW_TOKEN_HERE")
    
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()

    # تسجيل المعالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("add", cmd_add))
    app.add_handler(CommandHandler("grades", cmd_grades))
    app.add_handler(CommandHandler("tasks", cmd_tasks))

    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.VIDEO | filters.VOICE | filters.AUDIO | filters.Document.ALL, media_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🚀 البوت يعمل بجميع الميزات المتقدمة ونظام التنبيهات...")
    app.run_polling()
