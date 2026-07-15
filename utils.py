import os
from telegram import Bot
from telegram.constants import ParseMode

ADMIN_ID = int(os.environ.get("ADMIN_ID", "8332173399"))

def format_num(n):
    return str(int(n)) if n == int(n) else str(n)

def get_user_tag(user):
    return f"@{user.username}" if user.username else user.first_name

async def notify_admin(bot: Bot, text: str):
    try:
        await bot.send_message(chat_id=ADMIN_ID, text=text, parse_mode=ParseMode.HTML)
    except Exception:
        pass