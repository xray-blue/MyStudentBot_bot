from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from datetime import datetime, timedelta

def get_back_button():
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ رجوع", callback_data="menu_main")]])

def get_main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة مهمة جديدة", callback_data="menu_add")],
        [InlineKeyboardButton("📊 إدارة الدرجات", callback_data="menu_grade"),
         InlineKeyboardButton("📋 عرض المهام", callback_data="tfilter_ALL")],
        [InlineKeyboardButton("🗑 حذف مهمة", callback_data="menu_del_task"),
         InlineKeyboardButton("⚙️ الإعدادات", callback_data="menu_settings")],
        [InlineKeyboardButton("📅 التقويم", callback_data="menu_calendar"),
         InlineKeyboardButton("🏆 إنجازاتي", callback_data="menu_achievements")]
    ])

def get_task_types_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📝 امتحان", callback_data="type_exam"), InlineKeyboardButton("📚 واجب", callback_data="type_homework")],
        [InlineKeyboardButton("📖 تحضير", callback_data="type_prep"), InlineKeyboardButton("📄 ملاحظة سريعة", callback_data="type_note")],
        [InlineKeyboardButton("◀️ رجوع", callback_data="menu_main")]
    ])

def get_priority_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔴 عاجل", callback_data="prio_2"), InlineKeyboardButton("🟡 مهم", callback_data="prio_1"), InlineKeyboardButton("🟢 عادي", callback_data="prio_0")],
        [InlineKeyboardButton("◀️ إلغاء", callback_data="menu_main")]
    ])

def get_attachment_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📎 إرفاق ملف/رابط", callback_data="attach_yes")],
        [InlineKeyboardButton("❌ تخطي", callback_data="attach_no")]
    ])

def get_remind_menu_advanced():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("⏰ ساعة", callback_data="remind_1"), InlineKeyboardButton("🕒 3 ساعات", callback_data="remind_3"), InlineKeyboardButton("🕕 12 ساعة", callback_data="remind_12")],
        [InlineKeyboardButton("📅 يوم", callback_data="remind_24"), InlineKeyboardButton("📆 3 أيام", callback_data="remind_72"), InlineKeyboardButton("🗓️ أسبوع", callback_data="remind_168")],
        [InlineKeyboardButton("🔕 بدون تنبيه", callback_data="remind_0")],
        [InlineKeyboardButton("◀️ إلغاء", callback_data="menu_main")]
    ])

def get_recurring_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔁 يومي", callback_data="recur_daily"), InlineKeyboardButton("🔁 أسبوعي", callback_data="recur_weekly")],
        [InlineKeyboardButton("🔁 شهري", callback_data="recur_monthly"), InlineKeyboardButton("🔁 سنوي", callback_data="recur_yearly")],
        [InlineKeyboardButton("❌ لا تكرار", callback_data="recur_none")]
    ])

def get_settings_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔑 تغيير كلمة السر", callback_data="set_change_pwd")],
        [InlineKeyboardButton("🗑 حذف جميع بياناتي", callback_data="set_del_all_prompt")],
        [InlineKeyboardButton("🌐 تغيير اللغة", callback_data="set_language")],
        [InlineKeyboardButton("⏰ ضبط التنبيه الافتراضي", callback_data="set_default_remind")],
        [InlineKeyboardButton("◀️ رجوع للقائمة", callback_data="menu_main")]
    ])

def get_language_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇸🇦 العربية", callback_data="lang_ar")],
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_en")],
        [InlineKeyboardButton("◀️ رجوع", callback_data="menu_settings")]
    ])

def get_task_action_menu(task_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ تم الإنجاز", callback_data=f"complete_{task_id}"), InlineKeyboardButton("✏️ تعديل", callback_data=f"edit_{task_id}")],
        [InlineKeyboardButton("⏰ تأجيل", callback_data=f"postpone_{task_id}"), InlineKeyboardButton("📌 تثبيت", callback_data=f"pin_{task_id}")],
        [InlineKeyboardButton("🗑 حذف", callback_data=f"del_task_{task_id}")],
        [InlineKeyboardButton("◀️ رجوع", callback_data="menu_main")]
    ])

def get_grades_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ إضافة درجة لمادة", callback_data="grade_add")],
        [InlineKeyboardButton("📊 عرض جميع الدرجات", callback_data="grade_view_all")],
        [InlineKeyboardButton("◀️ رجوع", callback_data="menu_main")]
    ])

def generate_calendar(year, month, tasks_by_day):
    # tasks_by_day الآن بهيكل: { day: {'tasks': int, 'notes': int} }
    keyboard = []
    keyboard.append([InlineKeyboardButton(f"{month}/{year}", callback_data="noop")])
    days_of_week = ["سبت", "أحد", "اثنين", "ثلاثاء", "أربعاء", "خميس", "جمعة"]
    keyboard.append([InlineKeyboardButton(d, callback_data="noop") for d in days_of_week])
    
    first_day = datetime(year, month, 1)
    start_weekday = (first_day.weekday() + 2) % 7 
    
    if month == 12: next_month = datetime(year+1, 1, 1)
    else: next_month = datetime(year, month+1, 1)
    days_in_month = (next_month - timedelta(days=1)).day

    row = []
    for _ in range(start_weekday):
        row.append(InlineKeyboardButton(" ", callback_data="noop"))
        
    for day in range(1, days_in_month+1):
        counts = tasks_by_day.get(day, {'tasks': 0, 'notes': 0})
        label = f"{day}"
        
        # ترميز الأيقونات حسب المحتوى
        if counts['tasks'] > 0 and counts['notes'] > 0:
            label = f"{day}🔴📝"
        elif counts['tasks'] > 0:
            label = f"{day}🔴"
        elif counts['notes'] > 0:
            label = f"{day}📝"
            
        row.append(InlineKeyboardButton(label, callback_data=f"cal_day_{year}_{month}_{day}"))
        if len(row) == 7:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([
        InlineKeyboardButton("◀️", callback_data=f"cal_prev_{year}_{month}"),
        InlineKeyboardButton("📅 اليوم", callback_data="cal_today"),
        InlineKeyboardButton("▶️", callback_data=f"cal_next_{year}_{month}")
    ])
    keyboard.append([InlineKeyboardButton("◀️ رجوع", callback_data="menu_main")])
    return InlineKeyboardMarkup(keyboard)
