import aiosqlite
import hashlib

DB_NAME = "student_dashboard.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            type TEXT NOT NULL,
            title TEXT NOT NULL,
            due_date TEXT,
            is_notified BOOLEAN DEFAULT 0,
            remind_before INTEGER DEFAULT 0,
            completed BOOLEAN DEFAULT 0,
            priority INTEGER DEFAULT 0,
            attachment TEXT,
            link TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            score REAL NOT NULL,
            total REAL NOT NULL,
            title TEXT
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            password_hash TEXT,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            language TEXT DEFAULT 'ar',
            default_remind_hours INTEGER DEFAULT 24
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS recurring_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            frequency TEXT NOT NULL,
            interval_count INTEGER DEFAULT 1,
            days_of_week TEXT,
            day_of_month INTEGER,
            next_date TEXT,
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            badge_name TEXT NOT NULL,
            earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )''')
        await db.execute('''CREATE TABLE IF NOT EXISTS user_settings (
            user_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'ar',
            default_remind_hours INTEGER DEFAULT 24,
            theme TEXT DEFAULT 'light',
            FOREIGN KEY(user_id) REFERENCES users(user_id) ON DELETE CASCADE
        )''')

        # التوافق مع الإصدار السابق
        try: await db.execute("ALTER TABLE tasks ADD COLUMN completed BOOLEAN DEFAULT 0")
        except: pass
        try: await db.execute("ALTER TABLE tasks ADD COLUMN priority INTEGER DEFAULT 0")
        except: pass
        try: await db.execute("ALTER TABLE tasks ADD COLUMN attachment TEXT")
        except: pass
        try: await db.execute("ALTER TABLE tasks ADD COLUMN link TEXT")
        except: pass
        try: await db.execute("ALTER TABLE users ADD COLUMN xp INTEGER DEFAULT 0")
        except: pass
        try: await db.execute("ALTER TABLE users ADD COLUMN level INTEGER DEFAULT 1")
        except: pass
        try: await db.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'ar'")
        except: pass
        try: await db.execute("ALTER TABLE users ADD COLUMN default_remind_hours INTEGER DEFAULT 24")
        except: pass

        await db.commit()

# ===== دوال المهام =====
async def add_task_to_db(user_id, task_type, title, due_date, remind_before, priority=0, attachment=None, link=None):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            '''INSERT INTO tasks (user_id, type, title, due_date, remind_before, priority, attachment, link)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, task_type, title, due_date, remind_before, priority, attachment, link)
        )
        await db.commit()
        return cursor.lastrowid

async def get_tasks_from_db(user_id, task_filter=None, include_completed=False):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        query = 'SELECT * FROM tasks WHERE user_id = ?'
        params = [user_id]
        if not include_completed:
            query += ' AND completed = 0'
        if task_filter and task_filter != 'ALL':
            query += ' AND type = ?'
            params.append(task_filter)
        query += ' ORDER BY due_date ASC, priority DESC'
        cursor = await db.execute(query, params)
        return await cursor.fetchall()

async def update_task_completion(task_id, completed):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE tasks SET completed = ? WHERE id = ?', (completed, task_id))
        await db.commit()

# ===== دوال الدرجات =====
async def add_grade_to_db(user_id, subject, title, score, total):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            '''INSERT INTO grades (user_id, subject, score, total, title) VALUES (?, ?, ?, ?, ?)''',
            (user_id, subject, score, total, title)
        )
        await db.commit()

async def get_grades_from_db(user_id, subject=None):
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        if subject:
            cursor = await db.execute('SELECT * FROM grades WHERE user_id = ? AND subject = ? ORDER BY id DESC', (user_id, subject))
        else:
            cursor = await db.execute('SELECT * FROM grades WHERE user_id = ? ORDER BY subject, id DESC', (user_id,))
        return await cursor.fetchall()

# ===== دوال المستخدمين والإعدادات =====
async def get_user_hash(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT password_hash FROM users WHERE user_id = ?', (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else None

async def set_user_password(user_id, password):
    hashed = hashlib.sha256(password.encode()).hexdigest()
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('INSERT OR REPLACE INTO users (user_id, password_hash) VALUES (?, ?)', (user_id, hashed))
        await db.commit()

async def get_user_xp(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT xp, level FROM users WHERE user_id = ?', (user_id,))
        row = await cursor.fetchone()
        return row if row else (0, 1)

async def add_xp(user_id, xp_amount):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('UPDATE users SET xp = xp + ? WHERE user_id = ?', (xp_amount, user_id))
        cursor = await db.execute('SELECT xp FROM users WHERE user_id = ?', (user_id,))
        row = await cursor.fetchone()
        if row:
            xp = row[0]
            level = (xp // 100) + 1
            await db.execute('UPDATE users SET level = ? WHERE user_id = ?', (level, user_id))
        await db.commit()

async def get_user_settings(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,))
        row = await cursor.fetchone()
        if not row:
            await db.execute('INSERT INTO user_settings (user_id, language, default_remind_hours, theme) VALUES (?, ?, ?, ?)',
                             (user_id, 'ar', 24, 'light'))
            await db.commit()
            return {'language': 'ar', 'default_remind_hours': 24, 'theme': 'light'}
        return dict(row)

async def update_user_settings(user_id, key, value):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(f'UPDATE user_settings SET {key} = ? WHERE user_id = ?', (value, user_id))
        await db.commit()

async def add_recurring_task(user_id, task_id, frequency, interval=1, days=None, day_of_month=None):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            '''INSERT INTO recurring_tasks (user_id, task_id, frequency, interval_count, days_of_week, day_of_month, next_date)
               VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (user_id, task_id, frequency, interval, days, day_of_month, None)
        )
        await db.commit()

async def get_badges(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute('SELECT badge_name, earned_at FROM badges WHERE user_id = ? ORDER BY earned_at DESC', (user_id,))
        return await cursor.fetchall()

async def add_badge(user_id, badge_name):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('INSERT INTO badges (user_id, badge_name) VALUES (?, ?)', (user_id, badge_name))
        await db.commit()
