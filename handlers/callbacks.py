import math
import aiosqlite
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.constants import ParseMode

import database as db
import keyboards as kb
from utils import get_user_tag, notify_admin, ADMIN_ID, format_num

async def save_task_and_finish(query, context, user, attachment=None, link=None):
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

    await query.edit_message_text(
        f"✅ <b>تم حفظ المهمة</b> بنجاح!\n\n📌 {title}\n📅 {due_date}\n🔔 تنبيه قبل {remind_hours} ساعة",
        parse_mode=ParseMode.HTML,
        reply_markup=kb.get_main_menu()
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    user_tag = get_user_tag(user)
    data = query.data

    if data.startswith("admin_reply_"):
        if user.id != ADMIN_ID:
            return await query.answer("❌ هذا الزر للمطور فقط!", show_alert=True)
        target_id = int(data.split("_")[-1])
        context.user_data['action'] = 'ADMIN_TYPING_REPLY'
        context.user_data['reply_to_id'] = target_id
        await query.message.reply_text(f"✉️ اكتب ردك على المستخدم ({target_id}) الآن:\n(للإلغاء أرسل /cancel)")
        return
    # ===== معالجة زر "ابدأ الآن" من واجهة الستارت =====
    if data == "auth_start":
        if not await db.get_user_hash(user.id):
            context.user_data['state'] = 'AWAITING_SET_PWD'
            await query.edit_message_text("🔐 يرجى اختيار كلمة مرور للحساب (4 أحرف على الأقل):")
        else:
            context.user_data['state'] = 'AWAITING_LOGIN'
            await query.edit_message_text("🔐 يرجى إرسال كلمة المرور:")
        return
        
    if not context.user_data.get('auth'):
        return await query.answer("🔐 قم بتسجيل الدخول أولاً!", show_alert=True)

    if not data.startswith(("tfilter_", "tpage_", "menu_main", "grade_back", "menu_settings", "noop")):
        await notify_admin(context.bot, f"🔘 ضغط <b>{user_tag}</b> على:\n<code>{data}</code>")

    if data == "menu_main":
        is_auth = context.user_data.get('auth')
        context.user_data.clear()
        context.user_data['auth'] = is_auth
        await query.edit_message_text("⚙️ <b>القائمة الرئيسية</b>", parse_mode=ParseMode.HTML, reply_markup=kb.get_main_menu())

    elif data == "menu_settings":
        # تم إزالة "مراسلة المطور" من هنا لأن المستخدم يقدر يرسل لك في أي وقت الآن
        await query.edit_message_text("⚙️ <b>إعدادات الحساب</b>", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔑 تغيير كلمة السر", callback_data="set_change_pwd")],
            [InlineKeyboardButton("🗑 حذف جميع بياناتي", callback_data="set_del_all_prompt")],
            [InlineKeyboardButton("🌐 تغيير اللغة", callback_data="set_language")],
            [InlineKeyboardButton("⏰ ضبط التنبيه الافتراضي", callback_data="set_default_remind")],
            [InlineKeyboardButton("◀️ رجوع للقائمة", callback_data="menu_main")]
        ]))

    elif data == "set_language":
        await query.edit_message_text("🌐 اختر اللغة:", parse_mode=ParseMode.HTML, reply_markup=kb.get_language_menu())

    elif data.startswith("lang_"):
        lang = data.split("_")[1]
        await db.update_user_settings(user.id, 'language', lang)
        await query.answer(f"✅ تم تغيير اللغة إلى {'العربية' if lang=='ar' else 'English'}", show_alert=True)
        await query.edit_message_text("⚙️ <b>إعدادات الحساب</b>", parse_mode=ParseMode.HTML, reply_markup=kb.get_settings_menu())

    elif data == "set_default_remind":
        context.user_data['action'] = 'AWAITING_DEFAULT_REMIND'
        await query.edit_message_text("⏰ أرسل عدد الساعات الافتراضية للتنبيه (مثال: 24):", parse_mode=ParseMode.HTML, reply_markup=kb.get_back_button())

    elif data == "set_change_pwd":
        context.user_data['action'] = 'AWAITING_OLD_PWD'
        await query.edit_message_text("🔑 أرسل كلمة السر الحالية:", parse_mode=ParseMode.HTML, reply_markup=kb.get_back_button())

    elif data == "set_del_all_prompt":
        await query.edit_message_text(
            "⚠️ <b>تحذير:</b> سيتم حذف جميع بياناتك نهائياً!\n\nهل أنت متأكد؟",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🗑 نعم، احذف الكل", callback_data="del_all_yes")],
                [InlineKeyboardButton("❌ لا، ارجع", callback_data="menu_settings")]
            ])
        )
        
    elif data == "del_all_yes":
        user_id = user.id
        async with aiosqlite.connect("student_dashboard.db") as db_conn:
            await db_conn.execute('DELETE FROM tasks WHERE user_id = ?', (user_id,))
            await db_conn.execute('DELETE FROM grades WHERE user_id = ?', (user_id,))
            await db_conn.execute('DELETE FROM badges WHERE user_id = ?', (user_id,))
            await db_conn.execute('DELETE FROM recurring_tasks WHERE user_id = ?', (user_id,))
            await db_conn.execute('DELETE FROM user_settings WHERE user_id = ?', (user_id,))
            await db_conn.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
            await db_conn.commit()
        context.user_data.clear() 
        await query.edit_message_text("🗑 <b>تم حذف جميع بياناتك بنجاح.</b>\n\nلإعادة التسجيل أرسل /start", parse_mode=ParseMode.HTML)

    elif data == "menu_add":
        await query.edit_message_text("📝 <b>إضافة مهمة جديدة</b>\n\nاختر نوع المهمة:", parse_mode=ParseMode.HTML, reply_markup=kb.get_task_types_menu())

    elif data in ["type_exam", "type_homework", "type_prep", "type_note"]:
        task_type = data.split("_")[1]
        context.user_data['task_type'] = task_type
        context.user_data['action'] = 'awaiting_task_title'
        await query.edit_message_text(f"📌 أرسل <b>عنوان</b> المهمة:", parse_mode=ParseMode.HTML, reply_markup=kb.get_back_button())

    elif data.startswith("prio_"):
        priority = int(data.split("_")[1])
        context.user_data['priority'] = priority
        context.user_data['action'] = 'awaiting_task_date'
        await query.edit_message_text("📅 أرسل تاريخ المهمة (YYYY-MM-DD) أو اكتب 'اليوم' أو 'غداً':", parse_mode=ParseMode.HTML, reply_markup=kb.get_back_button())

    elif data.startswith("remind_"):
        remind_hours = int(data.split("_")[1])
        context.user_data['remind_hours'] = remind_hours
        await query.edit_message_text("🔄 هل تريد تكرار هذه المهمة؟", parse_mode=ParseMode.HTML, reply_markup=kb.get_recurring_menu())

    elif data.startswith("recur_"):
        recur_type = data.split("_")[1]
        context.user_data['recurring'] = recur_type if recur_type != 'none' else None
        await query.edit_message_text("📎 هل تريد إرفاق ملف أو رابط؟", parse_mode=ParseMode.HTML, reply_markup=kb.get_attachment_menu())

    elif data == "attach_yes":
        context.user_data['action'] = 'awaiting_attachment'
        await query.edit_message_text("أرسل الملف أو اكتب الرابط:", parse_mode=ParseMode.HTML, reply_markup=kb.get_back_button())
        
    elif data == "attach_no":
        await save_task_and_finish(query, context, user)

    # ===== حذف المهمة (تم وضعه هنا ليكون واضحاً ويعمل 100%) =====
    # ===== حذف المهمة (مع التأكيد) =====
    elif data == "menu_del_task":
        tasks = await db.get_tasks_from_db(user.id, include_completed=False)
        if not tasks:
            await query.answer("📭 لا توجد مهام لحذفها!", show_alert=True)
            return
        buttons = []
        response = "🗑 <b>اختر المهمة التي تريد حذفها:</b>\n\n"
        for t in tasks:
            emoji = {"exam": "📝", "homework": "📚", "prep": "📖", "note": "📄"}.get(t['type'], "📌")
            due = f" <code>{t['due_date']}</code>" if t['due_date'] else ""
            response += f"{emoji} {t['title']}{due}\n"
            # تغيير اسم الزر إلى del_task_confirm
            buttons.append([InlineKeyboardButton(f"🗑 حذف: {t['title'][:25]}", callback_data=f"del_task_confirm_{t['id']}")])
        buttons.append([InlineKeyboardButton("◀️ رجوع للقائمة", callback_data="menu_main")])
        await query.edit_message_text(response, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

    # ===== نافذة التأكيد قبل الحذف =====
    elif data.startswith("del_task_confirm_"):
        task_id = int(data.split("_")[-1])
        context.user_data['del_task_id'] = task_id # حفظ المؤقت
        await query.edit_message_text(
            "⚠️ <b>تحذير:</b> هل أنت متأكد من حذف هذه المهمة نهائياً؟", 
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ نعم، احذفها", callback_data="del_task_yes")],
                [InlineKeyboardButton("❌ لا، ارجع", callback_data="menu_del_task")]
            ])
        )

    # ===== تنفيذ الحذف الفعلي =====
    elif data == "del_task_yes":
        task_id = context.user_data.get('del_task_id')
        if task_id:
            async with aiosqlite.connect("student_dashboard.db") as db_conn:
                await db_conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
                await db_conn.commit()
            context.user_data.pop('del_task_id', None)
        await query.answer("🗑 تم حذف المهمة بنجاح!", show_alert=True)
        await query.edit_message_text("✅ تم حذف المهمة.", reply_markup=kb.get_main_menu())

    # ===== التقويم =====
    elif data == "menu_calendar":
        now = datetime.now()
        year, month = now.year, now.month
        tasks = await db.get_tasks_from_db(user.id, include_completed=True)
        tasks_by_day = {}
        for t in tasks:
            if t['due_date']:
                try:
                    d = datetime.strptime(t['due_date'], '%Y-%m-%d')
                    if d.year == year and d.month == month: tasks_by_day[d.day] = tasks_by_day.get(d.day, 0) + 1
                except: pass
        await query.edit_message_text(f"📅 <b>{month}/{year}</b>", parse_mode=ParseMode.HTML, reply_markup=kb.generate_calendar(year, month, tasks_by_day))

    elif data.startswith("cal_day_"):
        parts = data.split("_")
        date_str = f"{parts[2]}-{int(parts[3]):02d}-{int(parts[4]):02d}"
        tasks = await db.get_tasks_from_db(user.id, include_completed=True)
        tasks_day = [t for t in tasks if t['due_date'] == date_str]
        if tasks_day:
            response = f"📅 <b>مهام {date_str}</b>\n\n"
            for t in tasks_day:
                status = "✅" if t['completed'] else "⏳"
                response += f"{status} {t['title']} ({t['type']})\n"
            await query.edit_message_text(response, parse_mode=ParseMode.HTML, reply_markup=kb.get_back_button())
        else:
            await query.answer("لا توجد مهام في هذا اليوم.", show_alert=True)

    elif data.startswith("cal_prev_") or data.startswith("cal_next_") or data == "cal_today":
        if data == "cal_today":
            now = datetime.now()
            year, month = now.year, now.month
        else:
            parts = data.split("_")
            year, month = int(parts[2]), int(parts[3])
            if "prev" in data: 
                month -= 1
                if month == 0: month, year = 12, year - 1
            else: 
                month += 1
                if month == 13: month, year = 1, year + 1
        tasks = await db.get_tasks_from_db(user.id, include_completed=True)
        tasks_by_day = {}
        for t in tasks:
            if t['due_date']:
                try:
                    d = datetime.strptime(t['due_date'], '%Y-%m-%d')
                    if d.year == year and d.month == month: tasks_by_day[d.day] = tasks_by_day.get(d.day, 0) + 1
                except: pass
        await query.edit_message_text(f"📅 <b>{month}/{year}</b>", parse_mode=ParseMode.HTML, reply_markup=kb.generate_calendar(year, month, tasks_by_day))

    # ===== عرض المهام =====
    elif data.startswith("tfilter_") or data.startswith("tpage_"):
        parts = data.split("_")
        action, current_filter = parts[0], parts[1]
        current_page = int(parts[2]) if action == "tpage" else 1
        tasks = await db.get_tasks_from_db(user.id, current_filter, include_completed=False)
        total_pages = max(1, math.ceil(len(tasks) / 5))
        if current_page > total_pages: current_page = total_pages
        buttons = [
            [InlineKeyboardButton("📋 الكل", callback_data="tfilter_ALL"), InlineKeyboardButton("📝 امتحانات", callback_data="tfilter_exam"), InlineKeyboardButton("📚 واجبات", callback_data="tfilter_homework")],
            [InlineKeyboardButton("📖 تحضيرات", callback_data="tfilter_prep"), InlineKeyboardButton("📄 الملاحظات", callback_data="tfilter_note")]
        ]
        if not tasks:
            buttons.append([InlineKeyboardButton("◀️ رجوع", callback_data="menu_main")])
            await query.edit_message_text("📭 لا توجد مهام.", reply_markup=InlineKeyboardMarkup(buttons))
        else:
            start_idx = (current_page - 1) * 5
            paginated_tasks = tasks[start_idx: start_idx + 5]
            response = f"📋 <b>المهام</b> (صفحة {current_page}/{total_pages})\n\n"
            for t in paginated_tasks:
                emoji = {"exam": "📝", "homework": "📚", "prep": "📖", "note": "📄"}.get(t['type'], "📌")
                due = f" <code>{t['due_date']}</code>" if t['due_date'] else ""
                prio_emoji = {2: "🔴", 1: "🟡", 0: "🟢"}.get(t['priority'], "⚪")
                response += f"{prio_emoji} {emoji} {t['title']}{due}\n"
                buttons.append([InlineKeyboardButton(f"⚙️ {t['title'][:20]}", callback_data=f"action_{t['id']}")])
            nav_row = []
            if current_page > 1: nav_row.append(InlineKeyboardButton("◀️ السابق", callback_data=f"tpage_{current_filter}_{current_page-1}"))
            nav_row.append(InlineKeyboardButton(f"{current_page}/{total_pages}", callback_data="noop"))
            if current_page < total_pages: nav_row.append(InlineKeyboardButton("التالي ▶️", callback_data=f"tpage_{current_filter}_{current_page+1}"))
            buttons.append(nav_row)
            buttons.append([InlineKeyboardButton("◀️ رجوع", callback_data="menu_main")])
            await query.edit_message_text(response, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("action_"):
        task_id = int(data.split("_")[1])
        context.user_data['current_task_id'] = task_id
        await query.edit_message_text("⚙️ اختر إجراء للمهمة:", parse_mode=ParseMode.HTML, reply_markup=kb.get_task_action_menu(task_id))

    elif data.startswith("complete_"):
        task_id = int(data.split("_")[1])
        await db.update_task_completion(task_id, True)
        await db.add_xp(user.id, 10)
        badges = await db.get_badges(user.id)
        if not badges: await db.add_badge(user.id, "🌟 أول إنجاز")
        completed_tasks = await db.get_tasks_from_db(user.id, include_completed=True)
        completed_count = sum(1 for t in completed_tasks if t['completed'])
        if completed_count == 5: await db.add_badge(user.id, "🏅 5 مهام")
        elif completed_count == 10: await db.add_badge(user.id, "🎖️ 10 مهام")
        await query.answer("✅ تم الإنجاز! +10 XP", show_alert=True)
        await query.edit_message_text("✅ تم تحديث المهمة.", reply_markup=kb.get_main_menu())

    elif data.startswith("edit_"):
        task_id = int(data.split("_")[1])
        context.user_data['action'] = 'awaiting_edit_title'
        context.user_data['edit_task_id'] = task_id
        await query.edit_message_text("✏️ أرسل العنوان الجديد:", reply_markup=kb.get_back_button())

    elif data.startswith("postpone_"):
        task_id = int(data.split("_")[1])
        context.user_data['action'] = 'awaiting_postpone_days'
        context.user_data['postpone_task_id'] = task_id
        await query.edit_message_text("⏰ كم يوماً تريد تأجيل المهمة؟", reply_markup=kb.get_back_button())

    elif data.startswith("pin_"):
        task_id = int(data.split("_")[1])
        async with aiosqlite.connect("student_dashboard.db") as db_conn:
            await db_conn.execute('UPDATE tasks SET priority = 2 WHERE id = ?', (task_id,))
            await db_conn.commit()
        await query.answer("📌 تم تثبيت المهمة!", show_alert=True)
        await query.edit_message_text("✅ تم التثبيت.", reply_markup=kb.get_main_menu())

    # ===== نظام الدرجات =====
    elif data == "menu_grade":
        await query.edit_message_text("📊 <b>إدارة الدرجات</b>\n\nاختر عملية:", parse_mode=ParseMode.HTML, reply_markup=kb.get_grades_menu())

    elif data == "grade_add":
        context.user_data['action'] = 'waiting_new_subject'
        await query.edit_message_text("📝 أرسل <b>اسم المادة</b> الجديدة:\n(للإلغاء أرسل /cancel)", parse_mode=ParseMode.HTML, reply_markup=kb.get_back_button())

    elif data == "grade_view_all":
        subjects = await db.get_user_subjects(user.id)
        if not subjects:
            await query.answer("📭 لا توجد مواد مسجلة بعد! أضف مادة جديدة.", show_alert=True)
            return
        context.user_data['subjects_list'] = subjects
        buttons = []
        for idx, subj in enumerate(subjects):
            buttons.append([InlineKeyboardButton(f"📘 {subj}", callback_data=f"subj_view_{idx}")])
        buttons.append([InlineKeyboardButton("◀️ رجوع للقائمة الرئيسية", callback_data="menu_main")])
        await query.edit_message_text("📚 <b>موادي المسجلة:</b>\n\nاختر مادة لعرض تفاصيلها:", parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("subj_view_"):
        idx = int(data.split("_")[-1])
        subjects = context.user_data.get('subjects_list', [])
        if idx >= len(subjects): return await query.answer("❌ خطأ!", show_alert=True)
        subject = subjects[idx]
        grades = await db.get_grades_from_db(user.id, subject=subject)
        response = f"📘 <b>مادة: {subject}</b>\n\n"
        buttons = []
        if not grades:
            response += "لا توجد درجات مسجلة في هذه المادة بعد."
        else:
            for g in grades:
                score_txt = format_num(g['score']) if g['score'] == g['total'] else f"{format_num(g['score'])}/{format_num(g['total'])}"
                title = g['title'] if g['title'] else "بدون عنوان"
                response += f"• {title}: <code>{score_txt}</code>\n"
                buttons.append([InlineKeyboardButton(f"✏️ تعديل: {title[:20]} ({score_txt})", callback_data=f"grade_edit_{g['id']}")])
        buttons.append([InlineKeyboardButton(f"➕ إضافة درجة جديدة لمادة ({subject})", callback_data=f"grade_add_to_subj_{idx}")])
        buttons.append([InlineKeyboardButton("◀️ رجوع لقائمة المواد", callback_data="grade_view_all")])
        await query.edit_message_text(response, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))

    elif data.startswith("grade_add_to_subj_"):
        idx = int(data.split("_")[-1])
        subjects = context.user_data.get('subjects_list', [])
        if idx < len(subjects):
            subject = subjects[idx]
            context.user_data['current_subject'] = subject
            context.user_data['action'] = 'waiting_grade_input'
            await query.message.reply_text(f"📚 مادة: <b>{subject}</b>\n\nأرسل الدرجة الجديدة (مثال: الشهر الثاني 85):", parse_mode=ParseMode.HTML)
            await query.answer("✅ تم تحديد المادة، اكتب الدرجة الآن", show_alert=False)

    elif data == "grade_add_another":
        subject = context.user_data.get('current_subject')
        if subject:
            context.user_data['action'] = 'waiting_grade_input'
            await query.message.reply_text(f"📚 مادة: <b>{subject}</b>\n\nأرسل الدرجة التالية:", parse_mode=ParseMode.HTML)
        else:
            context.user_data['action'] = 'waiting_new_subject'
            await query.edit_message_text("📝 أرسل اسم المادة:", parse_mode=ParseMode.HTML, reply_markup=kb.get_back_button())

    elif data.startswith("grade_edit_"):
        grade_id = int(data.split("_")[-1])
        context.user_data['action'] = 'waiting_edit_grade_score'
        context.user_data['edit_grade_id'] = grade_id
        await query.edit_message_text("✏️ أرسل الدرجة الجديدة (مثال: 95 أو 85/100):\n(للإلغاء أرسل /cancel)", parse_mode=ParseMode.HTML, reply_markup=kb.get_back_button())

    elif data == "menu_achievements":
        badges = await db.get_badges(user.id)
        xp, level = await db.get_user_xp(user.id)
        response = f"🏆 <b>إنجازاتي</b>\n\n🎯 المستوى: {level}\n⭐ النقاط: {xp}\n\n"
        if badges:
            response += "🏅 <b>الشارات:</b>\n"
            for badge in badges: response += f"• {badge[0]} (منذ {badge[1]})\n"
        else:
            response += "لا توجد شارات حتى الآن."
        await query.edit_message_text(response, parse_mode=ParseMode.HTML, reply_markup=kb.get_back_button())
