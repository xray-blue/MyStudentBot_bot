import re
import logging
import aiosqlite
import hashlib
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

import database as db
import keyboards as kb
from utils import get_user_tag, notify_admin, ADMIN_ID, format_num

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not await db.get_user_hash(user.id):
        context.user_data['state'] = 'AWAITING_SET_PWD'
        await update.message.reply_text("🔐 يرجى اختيار كلمة مرور للحساب (4 أحرف على الأقل):")
    else:
        context.user_data['state'] = 'AWAITING_LOGIN'
        await update.message.reply_text("🔐 يرجى إرسال كلمة المرور:")

async def save_task_and_finish_from_message(update, context, user):
    task_type = context.user_data.get('task_type')
    title = context.user_data.get('task_title')
    due_date = context.user_data.get('task_due_date')
    priority = context.user_data.get('priority', 0)
    remind_hours = context.user_data.get('remind_hours', 0)
    recurring = context.user_data.get('recurring')
    attachment = context.user_data.get('attachment')
    link = context.user_data.get('link')

    task_id = await db.add_task_to_db(user.id, task_type, title, due_date, remind_hours, priority, attachment, link)

    if recurring and recurring != 'none':
        await db.add_recurring_task(user.id, task_id, recurring)

    await db.add_xp(user.id, 5)

    for key in ['task_type', 'task_title', 'task_due_date', 'priority', 'remind_hours', 'recurring', 'attachment', 'link']:
        context.user_data.pop(key, None)
    context.user_data.pop('action', None)

    await notify_admin(context.bot, f"📝 أضاف <b>{get_user_tag(user)}</b> مهمة جديدة:\nالعنوان: {title}\nالتاريخ: {due_date}")

    await update.message.reply_text(
        f"✅ <b>تم حفظ المهمة</b> بنجاح!\n\n📌 {title}\n📅 {due_date}\n🔔 تنبيه قبل {remind_hours} ساعة",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.get_main_menu()
    )

def clean_rtl(text):
    """دالة لإزالة رموز اتجاه الكتابة المخفية من تليجرام"""
    return text.replace('\u200f', '').replace('\u200e', '').replace('\u202a', '').replace('\u202c', '').strip()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_tag = get_user_tag(user)
    text = update.message.text.strip()
    state = context.user_data.get('state')
    action = context.user_data.get('action')

    if text == "/cancel":
        is_auth = context.user_data.get('auth')
        context.user_data.clear()
        if is_auth: context.user_data['auth'] = True
        return await update.message.reply_text("❌ تم إلغاء العملية.", reply_markup=kb.get_main_menu() if is_auth else None)

    if user.id == ADMIN_ID and action == 'ADMIN_TYPING_REPLY':
        target_id = context.user_data.get('reply_to_id')
        try:
            await context.bot.send_message(chat_id=target_id, text=f"📬 <b>رد من المطور:</b>\n\n{text}", parse_mode=ParseMode.HTML)
            await update.message.reply_text("✅ تم إرسال الرد!")
        except: await update.message.reply_text("❌ فشل الإرسال.")
        context.user_data.clear(); context.user_data['auth'] = True
        return

    if state == 'AWAITING_SET_PWD':
        if len(text) < 4: return await update.message.reply_text("❌ كلمة المرور قصيرة جداً.")
        await db.set_user_password(user.id, text)
        context.user_data.clear(); context.user_data['auth'] = True
        await notify_admin(context.bot, f"🔐 قام <b>{user_tag}</b> بإنشاء كلمة مرور.")
        return await update.message.reply_text("✅ تم تعيين كلمة المرور! مرحباً بك.", parse_mode=ParseMode.HTML, reply_markup=kb.get_main_menu())

    if state == 'AWAITING_LOGIN':
        real_hash = await db.get_user_hash(user.id)
        if hashlib.sha256(text.encode()).hexdigest() == real_hash:
            context.user_data.clear(); context.user_data['auth'] = True
            return await update.message.reply_text("✅ تم تسجيل الدخول!", reply_markup=kb.get_main_menu())
        else:
            await notify_admin(context.bot, f"❌ محاولة دخول فاشلة من <b>{user_tag}</b>.")
            return await update.message.reply_text("❌ كلمة المرور خاطئة!")

    if not context.user_data.get('auth'):
        return await update.message.reply_text("🔐 يرجى إرسال كلمة المرور للبدء:")

    if action == 'AWAITING_OLD_PWD':
        if hashlib.sha256(text.encode()).hexdigest() == await db.get_user_hash(user.id):
            context.user_data['action'] = 'AWAITING_NEW_PWD'
            return await update.message.reply_text("✅ أرسل كلمة السر الجديدة:", reply_markup=kb.get_back_button())
        return await update.message.reply_text("❌ كلمة السر الحالية خاطئة!", reply_markup=kb.get_back_button())

    if action == 'AWAITING_NEW_PWD':
        if len(text) < 4: return await update.message.reply_text("❌ قصيرة!", reply_markup=kb.get_back_button())
        await db.set_user_password(user.id, text)
        context.user_data.pop('action', None)
        return await update.message.reply_text("✅ تم تغيير كلمة السر!", reply_markup=kb.get_main_menu())

    if action == 'AWAITING_DEFAULT_REMIND':
        try:
            hours = int(text)
            await db.update_user_settings(user.id, 'default_remind_hours', hours)
            context.user_data.pop('action', None)
            return await update.message.reply_text(f"✅ تم ضبط التنبيه إلى {hours} ساعة.", reply_markup=kb.get_main_menu())
        except: return await update.message.reply_text("❌ أرسل رقماً صحيحاً.", reply_markup=kb.get_back_button())

    if action == 'AWAITING_MSG_ADMIN':
        context.user_data.pop('action', None)
        return await update.message.reply_text("✅ تم إرسال رسالتك للمطور!", reply_markup=kb.get_main_menu())

    if action == 'awaiting_task_title':
        context.user_data['task_title'] = text
        context.user_data['action'] = 'awaiting_task_priority'
        await update.message.reply_text("🔴 اختر الأولوية:", reply_markup=kb.get_priority_menu())
        return

    if action == 'awaiting_task_date':
        if text == "اليوم": due_date = datetime.now().strftime('%Y-%m-%d')
        elif text == "غداً": due_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        else:
            try: datetime.strptime(text, '%Y-%m-%d'); due_date = text
            except: return await update.message.reply_text("❌ صيغة خاطئة. YYYY-MM-DD", reply_markup=kb.get_back_button())
        context.user_data['task_due_date'] = due_date
        context.user_data['action'] = 'awaiting_remind'
        await update.message.reply_text("⏰ متى تريد التنبيه؟", reply_markup=kb.get_remind_menu_advanced())
        return

    if action == 'awaiting_attachment':
        if text.startswith('http://') or text.startswith('https://'):
            context.user_data['link'] = text; context.user_data['attachment'] = None
            await save_task_and_finish_from_message(update, context, user)
        else:
            await update.message.reply_text("📎 أرسل الملف أو رابط يبدأ بـ http://", reply_markup=kb.get_back_button())
        return

    if action == 'awaiting_edit_title':
        task_id = context.user_data.get('edit_task_id')
        async with aiosqlite.connect("student_dashboard.db") as db_conn:
            await db_conn.execute('UPDATE tasks SET title = ? WHERE id = ?', (text, task_id))
            await db_conn.commit()
        context.user_data.pop('action', None); context.user_data.pop('edit_task_id', None)
        return await update.message.reply_text("✅ تم التحديث.", reply_markup=kb.get_main_menu())

    if action == 'awaiting_postpone_days':
        try:
            days = int(text)
            task_id = context.user_data.get('postpone_task_id')
            async with aiosqlite.connect("student_dashboard.db") as db_conn:
                db_conn.row_factory = aiosqlite.Row
                cursor = await db_conn.execute('SELECT due_date FROM tasks WHERE id = ?', (task_id,))
                row = await cursor.fetchone()
                old_date = row['due_date'] if row and row['due_date'] else datetime.now().strftime('%Y-%m-%d')
                new_date = (datetime.strptime(old_date, '%Y-%m-%d') + timedelta(days=days)).strftime('%Y-%m-%d')
                await db_conn.execute('UPDATE tasks SET due_date = ? WHERE id = ?', (new_date, task_id))
                await db_conn.commit()
            context.user_data.pop('action', None); context.user_data.pop('postpone_task_id', None)
            return await update.message.reply_text(f"✅ تم التأجيل إلى {new_date}.", reply_markup=kb.get_main_menu())
        except: return await update.message.reply_text("❌ أرسل رقماً صحيحاً.", reply_markup=kb.get_back_button())

    # ===== إضافة مادة جديدة =====
    if action == 'waiting_new_subject':
        subject = text.strip()
        context.user_data['current_subject'] = subject
        context.user_data['action'] = 'waiting_grade_input'
        await update.message.reply_text(f"✅ تم إنشاء مادة <b>{subject}</b>.\n\nأرسل أول درجة بهذه الصيغة:\n<code>الشهر الأول 90</code>\nأو: <code>نصفي 15/20</code>", parse_mode=ParseMode.HTML, reply_markup=kb.get_back_button())
        return

    # ===== إضافة درجة (محدث ليعالج الرموز المخفية) =====
    if action == 'waiting_grade_input':
        subject = context.user_data.get('current_subject')
        # تنظيف النص من الرموز المخفية
        clean_text = clean_rtl(text)
        
        match = re.match(r"^(.+?)\s+(\d+(?:\.\d+)?)(?:\s*[/من]\s*(\d+(?:\.\d+)?))?", clean_text)
        
        if not match: 
            return await update.message.reply_text(
                "❌ صيغة خاطئة! تأكد من كتابة (العنوان) ثم مسافة ثم (الرقم).\nمثال: <code>الشهر الأول 90</code>", 
                parse_mode=ParseMode.HTML, 
                reply_markup=kb.get_back_button()
            )
            
        title = match.group(1).strip()
        score = float(match.group(2))
        total = float(match.group(3)) if match.group(3) else score
        
        await db.add_grade_to_db(user.id, subject, title, score, total)
        await db.add_xp(user.id, 5)
        score_txt = format_num(score) if total == score else f"{format_num(score)}/{format_num(total)}"
        
        await notify_admin(context.bot, f"📊 أضاف <b>{user_tag}</b> درجة [{subject}]: {title} {score_txt}")
        
        cont_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ إضافة درجة أخرى لنفس المادة", callback_data="grade_add_another")],
            [InlineKeyboardButton("◀️ رجوع للقائمة", callback_data="menu_main")]
        ])
        await update.message.reply_text(
            f"✅ تم تسجيل <code>{title}: {score_txt}</code> في <b>{subject}</b>", 
            parse_mode=ParseMode.HTML, 
            reply_markup=cont_kb
        )
        return

    # ===== تعديل درجة =====
    if action == 'waiting_edit_grade_score':
        grade_id = context.user_data.get('edit_grade_id')
        clean_text = clean_rtl(text)
        
        match = re.match(r"^(\d+(?:\.\d+)?)(?:\s*[/من]\s*(\d+(?:\.\d+)?))?", clean_text)
        if not match: 
            return await update.message.reply_text(
                "❌ صيغة خاطئة! أرسل الرقم فقط أو (رقم/من رقم)\nمثال: <code>95</code> أو <code>85/100</code>", 
                parse_mode=ParseMode.HTML, 
                reply_markup=kb.get_back_button()
            )
        
        score = float(match.group(1))
        total = float(match.group(2)) if match.group(2) else score
        
        async with aiosqlite.connect("student_dashboard.db") as db_conn:
            await db_conn.execute('UPDATE grades SET score = ?, total = ? WHERE id = ?', (score, total, grade_id))
            await db_conn.commit()
            
        context.user_data.pop('action', None)
        context.user_data.pop('edit_grade_id', None)
        
        score_txt = format_num(score) if total == score else f"{format_num(score)}/{format_num(total)}"
        await update.message.reply_text(f"✅ تم تعديل الدرجة بنجاح إلى: <code>{score_txt}</code>", parse_mode=ParseMode.HTML, reply_markup=kb.get_main_menu())
        return

    await update.message.reply_text("📌 استخدم الأزرار للتنقل:", reply_markup=kb.get_main_menu())

async def media_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if context.user_data.get('action') == 'awaiting_attachment':
        file_id = None
        if update.message.photo: file_id = update.message.photo[-1].file_id
        elif update.message.video: file_id = update.message.video.file_id
        elif update.message.document: file_id = update.message.document.file_id
        
        if file_id:
            context.user_data['attachment'] = file_id
            await save_task_and_finish_from_message(update, context, user)
            return

    caption = f"🚨 أرسل <b>{get_user_tag(user)}</b> ميديا:"
    if update.message.caption: caption += f"\n{update.message.caption}"
    try:
        if update.message.photo: await context.bot.send_photo(chat_id=ADMIN_ID, photo=update.message.photo[-1].file_id, caption=caption, parse_mode=ParseMode.HTML)
        elif update.message.video: await context.bot.send_video(chat_id=ADMIN_ID, video=update.message.video.file_id, caption=caption, parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.error(f"فشل إرسال الميديا للأدمن: {e}")
