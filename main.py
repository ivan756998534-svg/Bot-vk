import sqlite3
import re
import time
import asyncio
from datetime import datetime
from vkbottle.bot import Bot, Message
from vkbottle import DocMessagesUploader
TOKEN = "vk1.a.nSVDeqVxBl5NwrIv-1FiT_lfVkQ5FTVcnVbgDjX7tNUIL-2uUQWxqUsyvZxkXB9expe5MeE51yCh6474-Wr2kaEfbJ09PJIBu6wL28VjeRKFsLFVrYu0GLFr5INSOcgps7tKxtAB-d2x_3s1xfH59TYTPcRz9bSX3PPcBfZgdWbOThKheFnUG72Xb9lM2T0YO0c_QBKJdQUOYILFq9tmQw"
OWNER_ID = 807140123

bot = Bot(token=TOKEN)
doc_uploader = DocMessagesUploader(bot.api)
conn = sqlite3.connect("rp_manager_network.db")
cursor = conn.cursor()
START_TIME = time.time()

def first(items):
    return next(iter(items), "")
cursor.execute("CREATE TABLE IF NOT EXISTS known_chats (chat_id INTEGER PRIMARY KEY, title TEXT DEFAULT 'Беседа проекта')")
cursor.execute("CREATE TABLE IF NOT EXISTS chat_requests (chat_id INTEGER PRIMARY KEY, requester_id INTEGER, title TEXT, created_at INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS global_staff (user_id INTEGER PRIMARY KEY, role_name TEXT DEFAULT 'Участник', access INTEGER DEFAULT 0)")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER, user_id INTEGER, nickname TEXT DEFAULT 'Не установлен',
        role_name TEXT DEFAULT 'Участник', access INTEGER DEFAULT 0,
        warns INTEGER DEFAULT 0, preds INTEGER DEFAULT 0, mute_until INTEGER DEFAULT 0,
        msgs INTEGER DEFAULT 0, rep INTEGER DEFAULT 0,
        term_until INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, user_id)
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_settings (
        chat_id INTEGER PRIMARY KEY, silence INTEGER DEFAULT 0,
        welcome_text TEXT DEFAULT 'Добро пожаловать в беседу!',
        welcome_enabled INTEGER DEFAULT 1,
        rules_text TEXT DEFAULT 'Правила не установлены.',
        links_text TEXT DEFAULT 'Ссылки проекта ещё не установлены.',
        anticaps INTEGER DEFAULT 0, antiflood INTEGER DEFAULT 0,
        antilink INTEGER DEFAULT 0, autoclean_sys INTEGER DEFAULT 1
    )
""")
cursor.execute("CREATE TABLE IF NOT EXISTS local_bans (chat_id INTEGER, user_id INTEGER, reason TEXT, ban_until INTEGER DEFAULT 0, PRIMARY KEY (chat_id, user_id))")
cursor.execute("CREATE TABLE IF NOT EXISTS global_bans (user_id INTEGER PRIMARY KEY, reason TEXT, ban_until INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS user_notes (chat_id INTEGER, user_id INTEGER, author_id INTEGER, note_text TEXT, created_at INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS bot_blacklist (user_id INTEGER PRIMARY KEY, reason TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS bot_config (key TEXT PRIMARY KEY, value TEXT)")
migrations = [
    "ALTER TABLE known_chats ADD COLUMN title TEXT DEFAULT 'Беседа проекта'",
    "ALTER TABLE users ADD COLUMN msgs INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN rep INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN term_until INTEGER DEFAULT 0",
    "ALTER TABLE local_bans ADD COLUMN ban_until INTEGER DEFAULT 0",
    "ALTER TABLE global_bans ADD COLUMN ban_until INTEGER DEFAULT 0",
    "ALTER TABLE chat_settings ADD COLUMN welcome_enabled INTEGER DEFAULT 1",
    "ALTER TABLE chat_settings ADD COLUMN rules_text TEXT DEFAULT 'Правила не установлены.'",
    "ALTER TABLE chat_settings ADD COLUMN links_text TEXT DEFAULT 'Ссылки проекта ещё не установлены.'",
    "ALTER TABLE chat_settings ADD COLUMN anticaps INTEGER DEFAULT 0",
    "ALTER TABLE chat_settings ADD COLUMN antiflood INTEGER DEFAULT 0",
    "ALTER TABLE chat_settings ADD COLUMN antilink INTEGER DEFAULT 0",
    "ALTER TABLE chat_settings ADD COLUMN autoclean_sys INTEGER DEFAULT 1"
]
for q in migrations:
    try:
        cursor.execute(q)
    except Exception:
        pass
conn.commit()

last_msg_time = {}
admin_actions_log = {}

LINK_PATTERN = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/|vk\.com/|vk\.me/|vk\.cc/|clck\.ru/|youtu\.be/|youtube\.com/|discord\.gg/|discord\.com/|"
    r"@(?:club|public|event)\d+|\[(?:club|public|event)\d+\||"
    r"\b[a-zA-Z0-9а-яё-]{2,}\.(?:ru|com|net|org|me|gg|io|xyz|info|biz|su|рф|online|site|store|top|club|pro|link|tk|ml|ga|cf|kz|by|ua)\b)",
    re.IGNORECASE
)
HELP_DICT = {
    "старт": "🚀 +старт (или /start)\nАктивирует бота в беседе (для создателя чата или 4–5 ранга).",
    "стата": "📊 +стата [@игрок]\nПрофиль игрока: ник, должность, срок, актив и наказания.",
    "ссылки": "🔗 +ссылки (или +форум)\nПоказывает важные ссылки проекта. Изменить: +устссылки [текст]",
    "ник": "🏷 +ник [@игрок] [Ник]\nУстанавливает игровой ник участнику в текущей беседе.",
    "гник": "🌐 +гник [@игрок] [Ник]\nУстанавливает ник сразу во всех беседах. Снять: -гник @игрок",
    "срок": "⏳ +срок [@игрок] [дни] / -срок [@игрок]\nУстанавливает срок поста (например: +срок @durov 30). Список: +сроки",
    "приветствие": "👋 +приветствие [текст]\nЗадаёт приветствие. Вкл/выкл: +приветствие_режим [№] | Удалить: -приветствие [№]",
    "закреп": "📌 +закреп (ответом на сообщение) / -закреп\nЗакрепляет или открепляет сообщение в беседе.",
    "чранг": "🎯 +чмодер / +чадмин / +чга / +чзга / +чспец / +чснять [@игрок] [№ чатов]\nВыдаёт или снимает должность в конкретных беседах из списка «+чаты».",
    "мут": "🔇 +мут [@игрок] [срок] [причина]\nПримеры: +мут @durov 30м Флуд | +мут @durov 2ч Спам",
    "пред": "⚠️ +пред [@игрок] [причина]\nВыдаёт устное предупреждение (2 преда = 1 выговор).",
    "выг": "📛 +выг [@игрок] [причина]\nВыдаёт строгий выговор (3 выговора = автокик).",
    "бан": "⛔ +бан [@игрок] [срок] [причина]\nНа время: +бан @durov 7д Слив | Навсегда: +бан @durov Реклама",
    "гбан": "🌐 +гбан [@игрок] [срок] [причина]\nГлобальный бан во всех чатах сети.",
    "бэкап": "💾 +бэкап\nОтправляет резервную копию базы данных владельцу в ЛС."
}
def ui_box(title: str, lines: list, footer: str = "") -> str:
    clean_lines = []
    for line in lines:
        if not line:
            continue
        if line.startswith("\n"):
            clean_lines.append(line)
        elif line.startswith(("•", "▸", "—", "👤", "🛡", "⚔️", "👑", "🎯", "🌐", "📌", "👋", "⛔", "🔇", "⚠️")):
            clean_lines.append(f"  {line}")
        else:
            clean_lines.append(f"  ▸ {line}")
    body = "\n".join(clean_lines)
    res = f"╭──「 {title} 」──╮\n\n{body}\n\n╰──────────────────╯"
    if footer:
        res += f"\n💡 {footer}"
    return res

def parse_duration(token: str):
    m = re.match(r"^(\d+)([мчдmhd]?)$", token.lower())
    if not m:
        return None
    val = int(m.group(1))
    unit = m.group(2)
    if val <= 0:
        return None
    if unit in ["", "м", "m"]:
        return val * 60, f"{val} мин."
    if unit in ["ч", "h"]:
        return val * 3600, f"{val} ч."
    if unit in ["д", "d"]:
        return val * 86400, f"{val} дн."
    return None
def format_left(until_ts: int, now_ts: int):
    if until_ts == 0:
        return "Навсегда"
    rem = max(1, until_ts - now_ts)
    if rem >= 86400:
        return f"{rem // 86400} дн. {(rem % 86400) // 3600} ч."
    if rem >= 3600:
        return f"{rem // 3600} ч. {(rem % 3600) // 60} мин."
    return f"{rem // 60 + 1} мин."

def is_chat_active(cid: int) -> bool:
    cursor.execute("SELECT 1 FROM known_chats WHERE chat_id = ?", (cid,))
    return cursor.fetchone() is not None

def register_chat(cid: int, title: str = "Беседа проекта"):
    cursor.execute("""
        INSERT INTO known_chats (chat_id, title) VALUES (?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET title = ?
    """, (cid, title, title))
    conn.commit()
async def fetch_chat_title(cid: int) -> str:
    try:
        res = await bot.api.messages.get_conversations_by_id(peer_ids=[cid])
        for item in res.items:
            if item.chat_settings:
                return item.chat_settings.title
    except Exception:
        pass
    return "Беседа проекта"

async def is_vk_chat_owner(cid: int, uid: int) -> bool:
    try:
        mem = await bot.api.messages.get_conversation_members(peer_id=cid)
        for item in mem.items:
            if item.member_id == uid and getattr(item, "is_owner", False):
                return True
    except Exception:
        pass
    return False
def set_second_owner(cid: int, uid: int):
    cursor.execute("""
        INSERT INTO users (chat_id, user_id, role_name, access)
        VALUES (?, ?, 'Второй владелец', 5)
        ON CONFLICT(chat_id, user_id) DO UPDATE SET role_name = 'Второй владелец', access = 5
    """, (cid, uid))
    conn.commit()

async def auto_assign_owner(cid: int):
    try:
        mem = await bot.api.messages.get_conversation_members(peer_id=cid)
        member_ids = [i.member_id for i in mem.items]
        if OWNER_ID in member_ids:
            set_second_owner(cid, OWNER_ID)
            return True
    except Exception:
        pass
    return False
def get_chat_settings(cid: int):
    cursor.execute("""
        SELECT silence, welcome_text, welcome_enabled, rules_text, links_text, anticaps, antiflood, antilink, autoclean_sys
        FROM chat_settings WHERE chat_id = ?
    """, (cid,))
    r = cursor.fetchone()
    if not r:
        cursor.execute("INSERT INTO chat_settings (chat_id) VALUES (?)", (cid,))
        conn.commit()
        return (0, "Добро пожаловать в беседу!", 1, "Правила не установлены.", "Ссылки проекта ещё не установлены.", 0, 0, 0, 1)
    return r

def get_global(uid: int):
    if uid == OWNER_ID:
        return ("Второй владелец", 5)
    cursor.execute("SELECT role_name, access FROM global_staff WHERE user_id = ?", (uid,))
    r = cursor.fetchone()
    return r if r else ("Участник", 0)
def get_user(cid: int, uid: int):
    cursor.execute("""
        SELECT nickname, role_name, access, warns, preds, mute_until, msgs, rep, term_until
        FROM users WHERE chat_id = ? AND user_id = ?
    """, (cid, uid))
    r = cursor.fetchone()
    if not r:
        def_role = "Второй владелец" if uid == OWNER_ID else "Участник"
        def_acc = 5 if uid == OWNER_ID else 0
        cursor.execute(
            "INSERT INTO users (chat_id, user_id, role_name, access) VALUES (?, ?, ?, ?)",
            (cid, uid, def_role, def_acc)
        )
        conn.commit()
        nick, lr, la, w, p, m, ms, rep, term = ("Не установлен", def_role, def_acc, 0, 0, 0, 0, 0, 0)
    else:
        nick, lr, la, w, p, m, ms, rep, term = r
    if uid == OWNER_ID:
        return (nick, "Второй владелец", 5, w, p, m, ms, rep, term)
    gr, ga = get_global(uid)
    if ga >= la and ga > 0:
        return (nick, f"{gr} [Глобал]", ga, w, p, m, ms, rep, term)
    return (nick, lr, la, w, p, m, ms, rep, term)
async def send_log(text: str):
    cursor.execute("SELECT value FROM bot_config WHERE key = 'log_chat'")
    r = cursor.fetchone()
    val = first(r) if r else ""
    if val:
        try:
            await bot.api.messages.send(
                peer_id=int(val),
                message=f"📜 ЖУРНАЛ ДЕЙСТВИЙ\n\n{text}",
                random_id=0
            )
        except Exception:
            pass

async def check_anti_sliv(cid: int, chat_id: int, actor_id: int) -> bool:
    if actor_id == OWNER_ID:
        return False
    now = time.time()
    acts = admin_actions_log.get((cid, actor_id), [])
    acts = [t for t in acts if now - t < 60]
    acts.append(now)
    admin_actions_log[(cid, actor_id)] = acts
    if len(acts) >= 4:
        cursor.execute("UPDATE users SET access = 0, role_name = 'Участник' WHERE user_id = ?", (actor_id,))
        cursor.execute("DELETE FROM global_staff WHERE user_id = ?", (actor_id,))
        cursor.execute("INSERT OR REPLACE INTO local_bans VALUES (?, ?, ?, ?)", (cid, actor_id, "Автозащита: подозрение на слив админки", 0))
        conn.commit()
        try:
            await bot.api.messages.remove_chat_user(chat_id=chat_id, member_id=actor_id)
        except Exception:
            pass
        alert = f"🚨 АНТИСЛИВ СРАБОТАЛ!\nАдминистратор [id{actor_id}|нарушитель] совершил 4+ наказания за минуту, снят с поста и заблокирован."
        await send_log(alert)
        try:
            await bot.api.messages.send(peer_id=OWNER_ID, message=alert, random_id=0)
        except Exception:
            pass
        return True
    return False
def check_ban(cid: int, uid: int):
    now_ts = int(time.time())
    cursor.execute("SELECT reason, ban_until FROM global_bans WHERE user_id = ?", (uid,))
    gb = cursor.fetchone()
    if gb:
        gb_reason, gb_until = gb
        if gb_until > 0 and gb_until <= now_ts:
            cursor.execute("DELETE FROM global_bans WHERE user_id = ?", (uid,))
            conn.commit()
        else:
            return ("Глобальный бан", gb_reason, format_left(gb_until, now_ts))
    cursor.execute("SELECT reason, ban_until FROM local_bans WHERE chat_id = ? AND user_id = ?", (cid, uid))
    lb = cursor.fetchone()
    if lb:
        lb_reason, lb_until = lb
        if lb_until > 0 and lb_until <= now_ts:
            cursor.execute("DELETE FROM local_bans WHERE chat_id = ? AND user_id = ?", (cid, uid))
            conn.commit()
        else:
            return ("Бан чата", lb_reason, format_left(lb_until, now_ts))
    return None
def get_target(m: Message, args: list):
    if m.reply_message:
        return m.reply_message.from_id
    target_arg = first(args[1:])
    if target_arg:
        match = re.search(r"\[id(\d+)\|", target_arg)
        if match:
            return int(match.group(1))
        if target_arg.isdigit():
            return int(target_arg)
    return None

def get_tail(m: Message, args: list, start: int = 2):
    return " ".join(args[1:]) if m.reply_message else " ".join(args[start:])
async def expiration_worker():
    while True:
        await asyncio.sleep(45)
        now_ts = int(time.time())
        try:
            cursor.execute("SELECT chat_id, user_id FROM local_bans WHERE ban_until > 0 AND ban_until <= ?", (now_ts,))
            exp_local = cursor.fetchall()
            if exp_local:
                cursor.execute("DELETE FROM local_bans WHERE ban_until > 0 AND ban_until <= ?", (now_ts,))
                conn.commit()
                for cid, uid in exp_local:
                    await send_log(f"🔓 Авторазбан чата: срок бана [id{uid}|игрока] в беседе {cid} истёк.")

            cursor.execute("SELECT user_id FROM global_bans WHERE ban_until > 0 AND ban_until <= ?", (now_ts,))
            exp_glob = cursor.fetchall()
            if exp_glob:
                cursor.execute("DELETE FROM global_bans WHERE ban_until > 0 AND ban_until <= ?", (now_ts,))
                conn.commit()
                for (uid,) in exp_glob:
                    await send_log(f"🔓 Авто-глобал-разбан: срок бана [id{uid}|игрока] истёк.")
            cursor.execute("SELECT chat_id, user_id FROM users WHERE mute_until > 0 AND mute_until <= ?", (now_ts,))
            exp_mutes = cursor.fetchall()
            if exp_mutes:
                cursor.execute("UPDATE users SET mute_until = 0 WHERE mute_until > 0 AND mute_until <= ?", (now_ts,))
                conn.commit()
                for cid, uid in exp_mutes:
                    await send_log(f"🔊 Авторазмут: срок мута [id{uid}|игрока] в беседе {cid} истёк.")

            cursor.execute("SELECT chat_id, user_id, nickname FROM users WHERE term_until > 0 AND term_until <= ?", (now_ts,))
            exp_terms = cursor.fetchall()
            if exp_terms:
                cursor.execute("UPDATE users SET term_until = 0 WHERE term_until > 0 AND term_until <= ?", (now_ts,))
                conn.commit()
                for cid, uid, nick in exp_terms:
                    await send_log(f"🏁 Окончание срока: у [id{uid}|{nick}] в чате {cid} подошёл к концу назначенный срок поста!")
        except Exception:
            pass
@bot.on.chat_message()
async def handler(m: Message):
    cid = m.peer_id
    text_raw = (m.text or "").strip()
    args_pre = text_raw.split()
    cmd_pre = first(args_pre).lower()
    _, _, acc_pre, _, _, _, _, _, _ = get_user(cid, m.from_id) if m.from_id > 0 else ("", "", 0, 0, 0, 0, 0, 0, 0)

    if cmd_pre in ["+заявка", "+подключить"]:
        if is_chat_active(cid):
            return await m.answer("✅ Эта беседа уже привязана к объединению проекта.")
        chat_title = " ".join(args_pre[1:]).strip() or await fetch_chat_title(cid)
        cursor.execute(
            "INSERT OR REPLACE INTO chat_requests (chat_id, requester_id, title, created_at) VALUES (?, ?, ?, ?)",
            (cid, m.from_id, chat_title, int(time.time()))
        )
        conn.commit()
        return await m.answer(ui_box(
            "📩 ЗАЯВКА НА ОБЪЕДИНЕНИЕ",
            [
                f"Беседа: {chat_title}",
                f"Подал: [id{m.from_id}|участник]",
                "Статус: Ожидает подтверждения в этом чате"
            ],
            "Создатель чата или 4–5 ранг должны написать здесь: +одобрить"
        ))
    if cmd_pre in ["+одобрить", "+чат", "+активировать", "+старт", "старт", "/start", "начать"]:
        is_vk_owner = await is_vk_chat_owner(cid, m.from_id)
        if is_chat_active(cid) and cmd_pre in ["+старт", "старт", "/start", "начать"]:
            if is_vk_owner and m.from_id != OWNER_ID:
                cursor.execute("""
                    INSERT INTO users (chat_id, user_id, role_name, access)
                    VALUES (?, ?, 'Владелец беседы', 5)
                    ON CONFLICT(chat_id, user_id) DO UPDATE SET role_name = 'Владелец беседы', access = 5
                """, (cid, m.from_id))
            set_second_owner(cid, OWNER_ID)
            conn.commit()
            return await m.answer(ui_box(
                "🚀 БОТ УЖЕ ЗАПУЩЕН",
                ["Беседа активна и готова к работе."],
                "Напиши «+помощь» для просмотра всех команд."
            ))

        if acc_pre < 4 and not is_vk_owner:
            return await m.answer("❌ Одобрить и запустить бота может только создатель беседы ВК или 4–5 ранг.")

        if is_chat_active(cid) and cmd_pre == "+одобрить":
            return await m.answer("✅ Эта беседа уже состоит в объединении.")
        cursor.execute("SELECT title FROM chat_requests WHERE chat_id = ?", (cid,))
        req_row = cursor.fetchone()
        req_title = first(req_row) if req_row else ""
        custom_title = " ".join(args_pre[1:]).strip()
        chat_title = custom_title or req_title or await fetch_chat_title(cid)
        register_chat(cid, chat_title)
        cursor.execute("DELETE FROM chat_requests WHERE chat_id = ?", (cid,))
        owner_line = ""
        if is_vk_owner and m.from_id != OWNER_ID:
            cursor.execute("""
                INSERT INTO users (chat_id, user_id, role_name, access)
                VALUES (?, ?, 'Владелец беседы', 5)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET role_name = 'Владелец беседы', access = 5
            """, (cid, m.from_id))
            owner_line = "Создателю беседы выдан 5 ранг!"
        elif not is_vk_owner:
            try:
                mem = await bot.api.messages.get_conversation_members(peer_id=cid)
                for item in mem.items:
                    if getattr(item, "is_owner", False) and item.member_id > 0 and item.member_id != OWNER_ID:
                        cursor.execute("""
                            INSERT INTO users (chat_id, user_id, role_name, access)
                            VALUES (?, ?, 'Владелец беседы', 5)
                            ON CONFLICT(chat_id, user_id) DO UPDATE SET role_name = 'Владелец беседы', access = 5
                        """, (cid, item.member_id))
                        owner_line = f"Создателю [id{item.member_id}|беседы] выдан 5 ранг!"
                        break
            except Exception:
                pass
        set_second_owner(cid, OWNER_ID)
        conn.commit()
        await send_log(f"[id{m.from_id}|Руководитель] активировал беседу «{chat_title}».")
        return await m.answer(ui_box(
            "✅ БОТ ЗАПУЩЕН И ОБЪЕДИНЁН",
            [
                f"Название: {chat_title}",
                f"Активировал: [id{m.from_id}|руководитель]",
                owner_line,
                "Все модули защиты и управления включены."
            ],
            "Напиши «+помощь» для изучения команд."
        ))

    if cmd_pre == "-одобрить" and (acc_pre >= 4 or await is_vk_chat_owner(cid, m.from_id)):
        cursor.execute("DELETE FROM chat_requests WHERE chat_id = ?", (cid,))
        conn.commit()
        return await m.answer("❌ Заявка на объединение этой беседы отклонена.")
    if not is_chat_active(cid):
        if m.action and m.action.type.value == "chat_invite_user" and m.action.member_id and m.action.member_id < 0:
            ok = await auto_assign_owner(cid)
            if ok:
                chat_title = await fetch_chat_title(cid)
                register_chat(cid, chat_title)
                await m.answer(ui_box(
                    "✅ БОТ АКТИВИРОВАН",
                    [
                        "Второй владелец найден в беседе.",
                        f"Чат «{chat_title}» привязан к сети."
                    ]
                ))
            else:
                await m.answer(ui_box(
                    "🔒 ПРИВАТНЫЙ БОТ",
                    [
                        "1. Выдайте боту права администратора.",
                        "2. Создатель беседы должен написать «+старт» или «+одобрить».",
                        "3. Либо подайте заявку командой «+заявка»."
                    ]
                ))
        return

    sil, w_text, w_enabled, rules_text, links_text, acaps, aflood, alink, aclean_sys = get_chat_settings(cid)
    if m.action:
        act_type = m.action.type.value
        if aclean_sys == 1 and act_type in ["chat_kick_user", "chat_pin_message", "chat_unpin_message", "chat_title_update"]:
            try:
                await bot.api.messages.delete(peer_id=cid, cmids=[m.conversation_message_id], delete_for_all=True)
            except Exception:
                pass

        if act_type == "chat_kick_user":
            uid = m.action.member_id
            if uid and uid > 0 and uid == m.from_id and uid != OWNER_ID:
                _, _, u_acc, _, _, _, _, _, _ = get_user(cid, uid)
                if u_acc == 0:
                    try:
                        await bot.api.messages.remove_chat_user(chat_id=m.chat_id, member_id=uid)
                        await m.answer(ui_box(
                            "🚪 АВТОКИК ВЫШЕДШЕГО",
                            [
                                f"Участник: [id{uid}|игрок]",
                                "Причина: Самостоятельно покинул беседу"
                            ]
                        ))
                        await send_log(f"🚪 Автокик вышедшего: [id{uid}|игрок] (чат {cid}).")
                    except Exception:
                        pass
            return
        if act_type == "chat_invite_user":
            uid = m.action.member_id
            if uid and uid > 0:
                if uid == OWNER_ID:
                    set_second_owner(cid, OWNER_ID)
                    return
                ban = check_ban(cid, uid)
                if ban:
                    b_type, b_reason, b_left = ban
                    await m.answer(ui_box(
                        "⛔ ДОСТУП ЗАКРЫТ",
                        [
                            f"Игрок: [id{uid}|участник]",
                            f"Статус: {b_type} ({b_left})",
                            f"Причина: {b_reason}"
                        ]
                    ))
                    try:
                        await bot.api.messages.remove_chat_user(chat_id=m.chat_id, member_id=uid)
                    except Exception:
                        pass
                    return
                get_user(cid, uid)
                if w_enabled == 1 and w_text:
                    await m.answer(ui_box(
                        "👋 ДОБРО ПОЖАЛОВАТЬ",
                        [
                            f"Приветствуем, [id{uid}|игрок]!",
                            w_text
                        ],
                        "Напиши «+помощь» или «+ссылки»"
                    ))
            return
    if m.from_id < 0:
        return

    if m.from_id != OWNER_ID and check_ban(cid, m.from_id):
        try:
            await bot.api.messages.remove_chat_user(chat_id=m.chat_id, member_id=m.from_id)
        except Exception:
            pass
        return

    nick, role, acc, warns, preds, mute, msgs, rep, term = get_user(cid, m.from_id)
    now = int(time.time())

    if acc < 1 and (mute > now or sil == 1):
        try:
            await bot.api.messages.delete(peer_id=cid, cmids=[m.conversation_message_id], delete_for_all=True)
        except Exception:
            pass
        return

    if not m.text:
        return

    args = m.text.strip().split()
    cmd = first(args).lower()
    if not cmd:
        return
    if acc < 1:
        if alink == 1 and LINK_PATTERN.search(m.text):
            try:
                await bot.api.messages.delete(peer_id=cid, cmids=[m.conversation_message_id], delete_for_all=True)
            except Exception:
                pass
            return
        if not cmd.startswith(("+", "/", "!", "-")):
            if aflood == 1:
                prev = last_msg_time.get((cid, m.from_id), 0)
                last_msg_time[(cid, m.from_id)] = time.time()
                if time.time() - prev < 1.5:
                    try:
                        await bot.api.messages.delete(peer_id=cid, cmids=[m.conversation_message_id], delete_for_all=True)
                    except Exception:
                        pass
                    return
            if acaps == 1 and len(m.text) >= 8:
                let = [c for c in m.text if c.isalpha()]
                if let and sum(1 for c in let if c.isupper()) / len(let) > 0.75:
                    try:
                        await bot.api.messages.delete(peer_id=cid, cmids=[m.conversation_message_id], delete_for_all=True)
                    except Exception:
                        pass
                    return

    cursor.execute("UPDATE users SET msgs = msgs + 1 WHERE chat_id = ? AND user_id = ?", (cid, m.from_id))
    conn.commit()

    if not cmd.startswith(("+", "/", "!", "-")):
        return

    if m.from_id != OWNER_ID:
        cursor.execute("SELECT 1 FROM bot_blacklist WHERE user_id = ?", (m.from_id,))
        if cursor.fetchone():
            return
    if cmd in ["/help", "!помощь", "/помощь", "+помощь", "+команды"]:
        sub = first(args[1:]).lower().lstrip("+/-!")
        if sub in HELP_DICT:
            return await m.answer(ui_box("📖 СПРАВКА ПО КОМАНДЕ", [HELP_DICT[sub]]))
        if sub == "игрок":
            return await m.answer(ui_box(
                "👤 КОМАНДЫ ИГРОКОВ [0+ УР.]",
                [
                    "+стата [@игрок] — профиль, срок и статистика",
                    "+ссылки (+форум) — важные ссылки проекта",
                    "+новыйгод (+нг) — отсчёт до Нового года",
                    "+топ — топ активных участников чата",
                    "+реп / -реп [@игрок] — изменить репутацию",
                    "+ники / +состав / +гсостав — списки",
                    "+онлайн / +правила / +пинг — инфо"
                ],
                "Подробнее о команде: +помощь [команда]"
            ))
        if sub == "модер":
            return await m.answer(ui_box(
                "🛡 МОДЕРАЦИЯ [1+ УР.]",
                [
                    "+ник / +снятьник [@игрок] [Ник] — управление ником",
                    "+найтиник [часть] — поиск по никам чата",
                    "+чекбан [@игрок] — проверка банов и мутов",
                    "+мут / -мут [@игрок] [срок] [причина]",
                    "+пред / -пред [@игрок] — устный пред (2=выг)",
                    "+мутлист / +преды / +выги — списки нарушителей",
                    "+заметка / +заметки [@игрок] — досье игрока"
                ]
            ))
        if sub == "админ":
            return await m.answer(ui_box(
                "⚔️ АДМИНИСТРИРОВАНИЕ [2+ УР.]",
                [
                    "+выг / -выг [@игрок] [причина] — выговор (3=кик)",
                    "+кик [@игрок] [причина] — исключить из чата",
                    "+бан / -бан [@игрок] [срок] [причина] / +баны",
                    "+срок / -срок [@игрок] [дни] / +сроки — контроль поста",
                    "+закреп (ответом) / -закреп — закрепить сообщение",
                    "+тишина / +антикапс / +антифлуд — режимы",
                    "+антиссылка / +автоочистка — фильтрация",
                    "+созыв [текст] / +очистить / +инфочат"
                ]
            ))
        if sub in ["га", "руководство", "старшие"]:
            return await m.answer(ui_box(
                "👑 РУКОВОДСТВО [3–5 УР.]",
                [
                    "+гник / -гник [@игрок] [Ник] — ник во всех чатах",
                    "+гбан / -гбан / +гкик / +гбаны — глобал наказания",
                    "+снятьвсе [@игрок] — очистить все наказания",
                    "+кикмолчунов — кик тех, у кого 0 сообщений",
                    "+приветствие [текст] — задать приветствие",
                    "+приветствие_режим [№] / -приветствие [№] — вкл/выкл/удалить",
                    "+устправила / +устссылки [текст]",
                    "+сбросстатистики — обнулить счётчик сообщений",
                    "Ранги чата: +модер, +админ, +га, +зга, +спец, +снять",
                    "Глобал: +гмодер, +гадмин, +гга, +гспец, +гснять",
                    "По № чатов: +чмодер, +чадмин, +чга, +чзга, +чспец, +чснять [@игрок] [№...]",
                    "[4–5 ур.]: +старт, +одобрить, +чаты, -чат [№], +заявки",
                    "[4–5 ур.]: +логчат, -логчат, +чсбота, -чсбота, +рассылка",
                    "[Владелец]: +бэкап — скачать базу данных в ЛС"
                ]
            ))
        return await m.answer(ui_box(
            "📋 СПРАВОЧНИК КОМАНД",
            [
                "👤 +помощь игрок — профиль, ссылки, списки",
                "🛡 +помощь модер — ники, муты, преды, досье",
                "⚔️ +помощь админ — выги, баны, сроки, закреп",
                "👑 +помощь га — ранги, сеть бесед, приветствия"
            ],
            "Любую команду можно применять ответом на сообщение!"
        ))
    elif cmd in ["+ссылки", "+форум", "+правилапроекта", "/links"]:
        await m.answer(ui_box("🔗 РЕСУРСЫ И ССЫЛКИ ПРОЕКТА", [links_text]))

    elif cmd in ["+новыйгод", "+нг", "/newyear"]:
        now_dt = datetime.now()
        next_year = now_dt.year + 1
        ny_dt = datetime(next_year, 1, 1, 0, 0, 0)
        diff = ny_dt - now_dt
        await m.answer(ui_box(
            f"🎄 ДО НОВОГО {next_year} ГОДА",
            [
                f"Дней: {diff.days}",
                f"Часов: {diff.seconds // 3600} | Минут: {(diff.seconds % 3600) // 60}"
            ]
        ))

    elif cmd in ["+пинг", "/ping"]:
        ms = round((time.time() - m.date) * 1000)
        up = int(time.time() - START_TIME) // 60
        await m.answer(ui_box(
            "🏓 СТАТУС БОТА",
            [
                f"Отклик сервера: {abs(ms)} мс",
                f"Время работы: {up} мин."
            ]
        ))

    elif cmd in ["+правила", "/rules"]:
        await m.answer(ui_box("📖 ПРАВИЛА БЕСЕДЫ", [rules_text]))
    elif cmd in ["+стата", "+профиль", "/stats", "!стата"]:
        tid = get_target(m, args) or m.from_id
        tn, tr, ta, tw, tp, tm, tmsgs, trep, tterm = get_user(cid, tid)
        ms_status = f"Активен ({format_left(tm, now)})" if tm > now else "Нет"
        term_status = format_left(tterm, now) if tterm > now else "Не задан"
        cursor.execute("SELECT COUNT(*) FROM user_notes WHERE chat_id = ? AND user_id = ?", (cid, tid))
        (ncnt,) = cursor.fetchone()
        await m.answer(ui_box(
            "📊 ПРОФИЛЬ ИГРОКА",
            [
                f"Игрок: [id{tid}|{tn}]",
                f"Должность: {tr} ({ta} ур.)",
                f"Срок поста: {term_status}",
                f"Репутация: {trep} | Сообщений: {tmsgs + (1 if tid == m.from_id else 0)}",
                f"Выги: {tw}/3 | Преды: {tp}/2",
                f"Досье: {ncnt} | Мут: {ms_status}"
            ]
        ))

    elif cmd in ["+онлайн", "/online"]:
        try:
            mem = await bot.api.messages.get_conversation_members(peer_id=cid, fields=["online"])
            online_list = []
            for p in mem.profiles:
                if getattr(p, "online", 0) == 1:
                    dev = "📱" if getattr(p, "online_mobile", 0) == 1 else "💻"
                    online_list.append(f"{dev} [id{p.id}|{p.first_name} {p.last_name}]")
            if not online_list:
                return await m.answer("😴 Сейчас никого нет в сети.")
            await m.answer(ui_box(f"🟢 В СЕТИ ({len(online_list)})", online_list[:25]))
        except Exception:
            await m.answer("⚠️ Не удалось получить список онлайн (выдайте боту права администратора).")
    elif cmd in ["+реп", "-реп"]:
        tid = get_target(m, args)
        if not tid or tid == m.from_id:
            return await m.answer("⚠️ Укажите другого игрока.")
        get_user(cid, tid)
        d = 1 if cmd == "+реп" else -1
        cursor.execute("UPDATE users SET rep = rep + ? WHERE chat_id = ? AND user_id = ?", (d, cid, tid))
        conn.commit()
        _, _, _, _, _, _, _, new_rep, _ = get_user(cid, tid)
        await m.answer(f"⭐ Репутация [id{tid}|игрока] изменена! Текущая: {new_rep}")

    elif cmd in ["+топ", "/top", "!топ"]:
        cursor.execute("SELECT user_id, nickname, msgs, rep FROM users WHERE chat_id = ? AND msgs > 0 ORDER BY msgs DESC LIMIT 10", (cid,))
        rows = cursor.fetchall()
        if not rows:
            return await m.answer("📭 Статистика сообщений пока пуста.")
        lines = [f"{i}. [id{u}|{n if n != 'Не установлен' else 'Игрок'}] — {c} сообщ. (⭐{r})" for i, (u, n, c, r) in enumerate(rows, 1)]
        await m.answer(ui_box("🏆 ТОП АКТИВНЫХ ИГРОКОВ", lines))

    elif cmd in ["+срок", "-срок", "+сроки"]:
        if acc < 2:
            return await m.answer("❌ Нужен 2+ ур.")
        if cmd == "+сроки":
            cursor.execute("SELECT user_id, nickname, role_name, term_until FROM users WHERE chat_id = ? AND term_until > ? ORDER BY term_until ASC", (cid, now))
            rows = cursor.fetchall()
            if not rows:
                return await m.answer("📭 Активных сроков поста в этом чате нет.")
            lines = [f"[id{u}|{n if n != 'Не установлен' else 'Игрок'}] ({r}) — осталось {format_left(tu, now)}" for u, n, r, tu in rows]
            return await m.answer(ui_box("⏳ КОНТРОЛЬ СРОКОВ ПОСТА", lines))

        tid = get_target(m, args)
        if not tid:
            return await m.answer("⚠️ Укажите игрока.")
        get_user(cid, tid)
        if cmd == "-срок":
            cursor.execute("UPDATE users SET term_until = 0 WHERE chat_id = ? AND user_id = ?", (cid, tid))
            conn.commit()
            return await m.answer(f"✅ Отсчёт срока поста снят с [id{tid}|игрока].")

        days_str = first(args[1:]) if m.reply_message else first(args[2:])
        if not days_str.isdigit():
            return await m.answer("⚠️ Укажите срок в днях. Пример: +срок @игрок 30")
        days = int(days_str)
        if days <= 0 or days > 365:
            return await m.answer("⚠️ Укажите корректное количество дней (от 1 до 365).")
        end_ts = now + (days * 86400)
        cursor.execute("UPDATE users SET term_until = ? WHERE chat_id = ? AND user_id = ?", (end_ts, cid, tid))
        conn.commit()
        tn, _, _, _, _, _, _, _, _ = get_user(cid, tid)
        await m.answer(ui_box("⏳ НАЗНАЧЕН СРОК ПОСТА", [f"Игрок: [id{tid}|{tn}]", f"Длительность: {days} дн."]))
        await send_log(f"[id{m.from_id}|Админ] установил срок {days} дн. для [id{tid}|игрока].")
    elif cmd in ["+заметка", "+заметки"]:
        if acc < 1:
            return await m.answer("❌ Нужен 1+ ур.")
        tid = get_target(m, args)
        if not tid:
            return await m.answer("⚠️ Укажите игрока.")
        if cmd == "+заметка":
            note = get_tail(m, args, 2)
            if not note:
                return await m.answer("⚠️ Введите текст заметки.")
            cursor.execute("INSERT INTO user_notes VALUES (?, ?, ?, ?, ?)", (cid, tid, m.from_id, note, now))
            conn.commit()
            return await m.answer(f"🗂 Заметка добавлена в досье [id{tid}|игрока].")
        cursor.execute("SELECT author_id, note_text FROM user_notes WHERE chat_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 10", (cid, tid))
        rows = cursor.fetchall()
        if not rows:
            return await m.answer("📭 Досье этого игрока пусто.")
        body = [f"{t} (от [id{a}|адм])" for a, t in rows]
        await m.answer(ui_box(f"🗂 ДОСЬЕ [id{tid}|ИГРОКА]", body))

    elif cmd in ["+ники", "/nicks", "!ники", "+найтиник"]:
        if cmd == "+найтиник":
            if acc < 1:
                return await m.answer("❌ Нужен 1+ ур.")
            q = " ".join(args[1:]).strip()
            if not q:
                return await m.answer("⚠️ Укажите часть ника для поиска.")
            cursor.execute("SELECT user_id, nickname FROM users WHERE chat_id = ? AND user_id != ? AND nickname LIKE ?", (cid, OWNER_ID, f"%{q}%"))
            rows = cursor.fetchall()
            if not rows:
                return await m.answer("🔍 Совпадений не найдено.")
            body = [f"[id{u}|{n}]" for u, n in rows]
            return await m.answer(ui_box(f"🔍 ПОИСК НИКА: {q}", body))
        cursor.execute("SELECT user_id, nickname FROM users WHERE chat_id = ? AND user_id != ? AND nickname != 'Не установлен'", (cid, OWNER_ID))
        rows = cursor.fetchall()
        if not rows:
            return await m.answer("📭 В чате ещё не установлены ники.")
        body_list = []
        for i, (u, n) in enumerate(rows, 1):
            _, u_role, _, _, _, _, _, _, _ = get_user(cid, u)
            body_list.append(f"{i}. [id{u}|{n}] — {u_role}")
        await m.answer(ui_box("📝 СПИСОК НИКОВ ЧАТА", body_list))
    elif cmd in ["+состав", "+админы", "+модеры", "+гсостав"]:
        if cmd == "+гсостав":
            cursor.execute("SELECT user_id, role_name, access FROM global_staff WHERE access >= 1 AND user_id != ? ORDER BY access DESC", (OWNER_ID,))
            rows = cursor.fetchall()
            if not rows:
                return await m.answer("📭 Глобальный состав пуст.")
            res = [f"[{a} ур. | {r}] — [id{u}|Админ]" for u, r, a in rows]
            return await m.answer(ui_box("🌐 ГЛОБАЛЬНЫЙ СОСТАВ", res))
        cursor.execute("SELECT user_id, nickname FROM users WHERE chat_id = ? AND user_id != ?", (cid, OWNER_ID))
        st = []
        for u, n in cursor.fetchall():
            _, u_role, u_acc, _, _, _, _, _, _ = get_user(cid, u)
            if u_acc >= 1:
                st.append((u_acc, f"[{u_acc} ур. | {u_role}] — [id{u}|{n if n != 'Не установлен' else 'Без ника'}]"))
        if not st:
            return await m.answer("📭 Администрация чата не назначена.")
        st.sort(key=lambda x: first(x), reverse=True)
        await m.answer(ui_box("🛡 СОСТАВ ЧАТА", [line for _, line in st]))

    elif cmd in ["+чекбан", "+банчек", "/checkban"]:
        if acc < 1:
            return await m.answer("❌ Нужен 1+ ур.")
        tid = get_target(m, args)
        if not tid:
            return await m.answer("⚠️ Укажите игрока.")
        now_ts = int(time.time())
        status_lines = [f"Игрок: [id{tid}|участник]"]
        cursor.execute("SELECT reason, ban_until FROM global_bans WHERE user_id = ?", (tid,))
        gb = cursor.fetchone()
        if gb:
            gb_reason, gb_until = gb
            if gb_until > 0 and gb_until <= now_ts:
                cursor.execute("DELETE FROM global_bans WHERE user_id = ?", (tid,))
                conn.commit()
            else:
                status_lines.append(f"🌐 Глобал бан: {format_left(gb_until, now_ts)} ({gb_reason})")
        cursor.execute("SELECT reason, ban_until FROM local_bans WHERE chat_id = ? AND user_id = ?", (cid, tid))
        lb = cursor.fetchone()
        if lb:
            lb_reason, lb_until = lb
            if lb_until > 0 and lb_until <= now_ts:
                cursor.execute("DELETE FROM local_bans WHERE chat_id = ? AND user_id = ?", (cid, tid))
                conn.commit()
            else:
                status_lines.append(f"⛔ Бан чата: {format_left(lb_until, now_ts)} ({lb_reason})")
        cursor.execute("SELECT 1 FROM bot_blacklist WHERE user_id = ?", (tid,))
        if cursor.fetchone():
            status_lines.append("🚫 ЧС бота: Активен")
        _, _, _, _, _, t_mute, _, _, _ = get_user(cid, tid)
        if t_mute > now_ts:
            status_lines.append(f"🔇 Мут чата: {format_left(t_mute, now_ts)}")
        if len(status_lines) == 1:
            status_lines.append("✅ Активных банов и мутов нет")
        return await m.answer(ui_box("🔍 ПРОВЕРКА ИГРОКА", status_lines))
    elif cmd in ["+чаты", "+списокчатов", "-чат", "+заявки"]:
        if acc < 4:
            return await m.answer("❌ Управление объединением доступно с 4+ ур.")
        if cmd in ["+чаты", "+списокчатов"]:
            cursor.execute("SELECT chat_id, title FROM known_chats ORDER BY ROWID ASC")
            rows = cursor.fetchall()
            if not rows:
                return await m.answer("📭 Список объединённых бесед пуст.")
            lines = [f"{idx_c}. {c_title}{' (текущая)' if c_id == cid else ''}" for idx_c, (c_id, c_title) in enumerate(rows, 1)]
            return await m.answer(ui_box("🌐 ОБЪЕДИНЁННЫЕ БЕСЕДЫ", lines, "Открепить: -чат [номер из списка]"))
        if cmd == "-чат":
            num_str = first(args[1:])
            if not num_str.isdigit():
                return await m.answer("⚠️ Укажите номер беседы из списка «+чаты».")
            num = int(num_str)
            cursor.execute("SELECT chat_id, title FROM known_chats ORDER BY ROWID ASC")
            rows = cursor.fetchall()
            if num < 1 or num > len(rows):
                return await m.answer(f"⚠️ Неверный номер. В списке сейчас бесед: {len(rows)}.")
            target_cid, target_title = rows[num - 1]
            cursor.execute("DELETE FROM known_chats WHERE chat_id = ?", (target_cid,))
            conn.commit()
            await send_log(f"[id{m.from_id}|Админ] открепил беседу «{target_title}» (ID: {target_cid}).")
            return await m.answer(ui_box("🔌 БЕСЕДА ОТКРЕПЛЕНА", [f"Название: {target_title}", f"Номер: {num}"]))
        if cmd == "+заявки":
            cursor.execute("SELECT chat_id, requester_id, title FROM chat_requests")
            reqs = cursor.fetchall()
            if not reqs:
                return await m.answer("📭 Ожидающих заявок нет.")
            lines = [f"{r_title} (от [id{r_uid}|игрока])" for r_cid, r_uid, r_title in reqs]
            return await m.answer(ui_box("📩 ОЖИДАЮЩИЕ ЗАЯВКИ", lines, "Зайдите в нужный чат и напишите: +одобрить"))
    elif cmd in ["+мутлист", "+преды", "+выги", "+баны", "+гбаны"]:
        if cmd == "+мутлист":
            if acc < 1:
                return await m.answer("❌ Нужен 1+ ур.")
            cursor.execute("SELECT user_id, nickname, mute_until FROM users WHERE chat_id = ? AND mute_until > ?", (cid, now))
            rows = cursor.fetchall()
            if not rows:
                return await m.answer("📭 Активных мутов нет.")
            body = [f"[id{u}|{n}] — {format_left(mu, now)}" for u, n, mu in rows]
            return await m.answer(ui_box("🔇 АКТИВНЫЕ МУТЫ", body))
        if cmd in ["+преды", "+выги"]:
            if acc < 1:
                return await m.answer("❌ Нужен 1+ ур.")
            cursor.execute("SELECT user_id, nickname, warns, preds FROM users WHERE chat_id = ? AND (warns > 0 OR preds > 0)", (cid,))
            rows = cursor.fetchall()
            if not rows:
                return await m.answer("📭 Нарушителей нет.")
            body = [f"[id{u}|{n}] — Выги: {w}/3 | Преды: {p}/2" for u, n, w, p in rows]
            return await m.answer(ui_box("⚠️ НАРУШИТЕЛИ ЧАТА", body))
        if cmd == "+баны":
            if acc < 2:
                return await m.answer("❌ Нужен 2+ ур.")
            cursor.execute("DELETE FROM local_bans WHERE chat_id = ? AND ban_until > 0 AND ban_until <= ?", (cid, now))
            conn.commit()
            cursor.execute("SELECT user_id, reason, ban_until FROM local_bans WHERE chat_id = ?", (cid,))
            rows = cursor.fetchall()
            if not rows:
                return await m.answer("📭 Локальный бан-лист пуст.")
            body = [f"[id{u}|Игрок] [{format_left(bu, now)}] — {r}" for u, r, bu in rows]
            return await m.answer(ui_box("⛔ БАНЫ ЧАТА", body))
        if acc < 3:
            return await m.answer("❌ Нужен 3+ ур.")
        cursor.execute("DELETE FROM global_bans WHERE ban_until > 0 AND ban_until <= ?", (now,))
        conn.commit()
        cursor.execute("SELECT user_id, reason, ban_until FROM global_bans")
        rows = cursor.fetchall()
        if not rows:
            return await m.answer("📭 Глобальный бан-лист пуст.")
        body = [f"[id{u}|Игрок] [{format_left(bu, now)}] — {r}" for u, r, bu in rows]
        return await m.answer(ui_box("🌐 ГЛОБАЛЬНЫЕ БАНЫ", body))
    elif cmd in ["+чмодер", "+чадмин", "+чга", "+чзга", "+чспец", "+чснять"]:
        if acc < 4:
            return await m.answer("❌ Назначение должностей по номерам бесед доступно с 4+ ур.")
        tid = get_target(m, args)
        if not tid or tid == OWNER_ID or tid == m.from_id:
            return await m.answer("⚠️ Укажите корректного игрока.")
        raw_nums = " ".join(args[1:]) if m.reply_message else " ".join(args[2:])
        nums = [int(x) for x in re.findall(r"\d+", raw_nums)]
        if not nums:
            return await m.answer("⚠️ Укажите номера бесед из списка «+чаты». Пример: +чмодер @игрок 1 3")
        rmap = {"модер": (1, "Модератор"), "админ": (2, "Администратор"), "га": (3, "ГА/ЗГА"), "зга": (3, "ГА/ЗГА"), "спец": (4, "Спец. адм"), "снять": (0, "Участник")}
        lvl, title = rmap[cmd[2:]]
        if lvl >= acc and m.from_id != OWNER_ID:
            return await m.answer("❌ Можно выдавать ранг только ниже своего.")
        cursor.execute("SELECT chat_id, title FROM known_chats ORDER BY ROWID ASC")
        all_chats = cursor.fetchall()
        applied = []
        skipped = []
        for n in dict.fromkeys(nums):
            if n < 1 or n > len(all_chats):
                skipped.append(f"№{n} (не найден)")
                continue
            t_cid, t_title = all_chats[n - 1]
            _, _, cur_l_acc, _, _, _, _, _, _ = get_user(t_cid, tid)
            if cur_l_acc >= acc and m.from_id != OWNER_ID:
                skipped.append(f"№{n} (ранг выше)")
                continue
            cursor.execute("UPDATE users SET access = ?, role_name = ? WHERE chat_id = ? AND user_id = ?", (lvl, title, t_cid, tid))
            applied.append(f"№{n} «{t_title}»")
        conn.commit()
        if not applied:
            return await m.answer("⚠️ Не удалось обновить должность ни в одной из указанных бесед.")
        res_lines = [f"Игрок: [id{tid}|участник]", f"Роль: {title} ({lvl} ур.)", f"Применено: {', '.join(applied)}"]
        if skipped:
            res_lines.append(f"Пропущено: {', '.join(skipped)}")
        await m.answer(ui_box("🎯 ДОЛЖНОСТЬ ПО ЧАТАМ", res_lines))
        await send_log(f"[id{m.from_id}|Админ] назначил {title} ({lvl} ур.) [id{tid}|игроку] в чатах: {', '.join(applied)}.")
    elif cmd in ["+модер", "+админ", "+га", "+зга", "+спец", "+снять", "+гмодер", "+гадмин", "+гга", "+гзга", "+гспец", "+гснять"]:
        if acc < 2:
            return await m.answer("❌ Нужен 2+ ур.")
        tid = get_target(m, args)
        if not tid or tid == OWNER_ID or tid == m.from_id:
            return await m.answer("⚠️ Укажите корректного игрока.")
        is_glob = cmd.startswith("+г") and cmd != "+га"
        _, g_acc = get_global(tid)
        _, _, l_acc, _, _, _, _, _, _ = get_user(cid, tid)
        t_acc = g_acc if is_glob else l_acc
        if t_acc >= acc and m.from_id != OWNER_ID:
            return await m.answer("❌ Нельзя изменить ранг равного или старшего.")
        rmap = {"модер": (1, "Модератор"), "админ": (2, "Администратор"), "га": (3, "ГА/ЗГА"), "зга": (3, "ГА/ЗГА"), "спец": (4, "Спец. адм"), "снять": (0, "Участник")}
        key = cmd[2:] if is_glob else cmd[1:]
        lvl, title = rmap[key]
        if lvl >= acc and m.from_id != OWNER_ID:
            return await m.answer("❌ Можно выдавать ранг только ниже своего.")
        if is_glob:
            cursor.execute("INSERT OR REPLACE INTO global_staff VALUES (?, ?, ?)", (tid, title, lvl))
            if lvl == 0:
                cursor.execute("UPDATE users SET access = 0, role_name = 'Участник' WHERE user_id = ?", (tid,))
        else:
            cursor.execute("UPDATE users SET access = ?, role_name = ? WHERE chat_id = ? AND user_id = ?", (lvl, title, cid, tid))
        conn.commit()
        await m.answer(ui_box("🎖 НАЗНАЧЕНИЕ РАНГА", [f"Игрок: [id{tid}|участник]", f"Роль: {title} ({lvl} ур.)"]))
        await send_log(f"[id{m.from_id}|Админ] выдал ранг {title} ({lvl} ур.) игроку [id{tid}|участнику].")
    elif cmd in ["+бан", "-бан", "+гбан", "-гбан", "+гкик"]:
        req = 3 if cmd.startswith(("+г", "-г")) else 2
        if acc < req:
            return await m.answer(f"❌ Нужен {req}+ ур.")
        tid = get_target(m, args)
        if not tid:
            return await m.answer("⚠️ Укажите игрока.")
        if cmd == "-бан":
            cursor.execute("DELETE FROM local_bans WHERE chat_id = ? AND user_id = ?", (cid, tid))
            conn.commit()
            return await m.answer(f"✅ Локальный бан снят с [id{tid}|участника].")
        if cmd == "-гбан":
            cursor.execute("DELETE FROM global_bans WHERE user_id = ?", (tid,))
            conn.commit()
            return await m.answer(f"✅ Глобальный бан снят с [id{tid}|участника].")
        _, g_acc = get_global(tid)
        _, _, l_acc, _, _, _, _, _, _ = get_user(cid, tid)
        t_acc = g_acc if req == 3 else l_acc
        if tid == OWNER_ID or (t_acc >= acc and m.from_id != OWNER_ID):
            return await m.answer("❌ Нельзя применить к этому админу.")
        if await check_anti_sliv(cid, m.chat_id, m.from_id):
            return
        idx_start = 1 if m.reply_message else 2
        ban_until = 0
        dur_label = "Навсегда"
        dur_token = first(args[idx_start:])
        if cmd in ["+бан", "+гбан"] and dur_token:
            parsed = parse_duration(dur_token)
            if parsed:
                b_sec, b_txt = parsed
                ban_until = now + b_sec
                dur_label = b_txt
                idx_start += 1
        reason = " ".join(args[idx_start:]) or "Не указана"
        if cmd == "+бан":
            cursor.execute("INSERT OR REPLACE INTO local_bans VALUES (?, ?, ?, ?)", (cid, tid, reason, ban_until))
            cursor.execute("UPDATE users SET access = 0, role_name = 'Участник' WHERE chat_id = ? AND user_id = ?", (cid, tid))
            conn.commit()
            await m.answer(ui_box("⛔ БАН В ЧАТЕ", [f"Игрок: [id{tid}|участник]", f"Срок: {dur_label}", f"Причина: {reason}"]))
            try:
                await bot.api.messages.remove_chat_user(chat_id=m.chat_id, member_id=tid)
            except Exception:
                pass
        else:
            if cmd == "+гбан":
                cursor.execute("INSERT OR REPLACE INTO global_bans VALUES (?, ?, ?)", (tid, reason, ban_until))
            cursor.execute("DELETE FROM global_staff WHERE user_id = ?", (tid,))
            cursor.execute("UPDATE users SET access = 0, role_name = 'Участник' WHERE user_id = ?", (tid,))
            conn.commit()
            cursor.execute("SELECT chat_id FROM known_chats")
            chats = cursor.fetchall()
            k = 0
            for (pid,) in chats:
                try:
                    await bot.api.messages.remove_chat_user(chat_id=pid - 2000000000, member_id=tid)
                    k += 1
                except Exception:
                    pass
            info = [f"Игрок: [id{tid}|участник] ({k}/{len(chats)} чатов)", f"Причина: {reason}"]
            if cmd == "+гбан":
                info.insert(1, f"Срок: {dur_label}")
            await m.answer(ui_box(f"🌐 ГЛОБАЛЬНАЯ МЕРА ({cmd})", info))
        await send_log(f"[id{m.from_id}|Админ] применил {cmd} ({dur_label}) к [id{tid}|игроку]. Причина: {reason}")
    elif cmd in ["+ник", "/snick", "+снятьник", "+гник", "-гник", "+гснятьник", "+мут", "-мут"]:
        is_glob_nick = cmd in ["+гник", "-гник", "+гснятьник"]
        req = 3 if is_glob_nick else 1
        if acc < req:
            return await m.answer(f"❌ Нужен {req}+ ур.")
        tid = get_target(m, args)
        if not tid:
            return await m.answer("⚠️ Укажите игрока.")
        get_user(cid, tid)
        if cmd in ["-гник", "+гснятьник"]:
            cursor.execute("UPDATE users SET nickname = 'Не установлен' WHERE user_id = ?", (tid,))
            conn.commit()
            await send_log(f"[id{m.from_id}|Админ] сбросил глобальный ник [id{tid}|игроку].")
            return await m.answer(f"🌐 Глобальный ник сброшен для [id{tid}|игрока] во всех беседах.")
        if cmd == "+гник":
            nn = get_tail(m, args, 2)
            if not nn:
                return await m.answer("⚠️ Укажите ник. Пример: +гник @игрок Ivan_Petrov")
            cursor.execute("SELECT chat_id FROM known_chats")
            all_chats = cursor.fetchall()
            for (chat_item,) in all_chats:
                cursor.execute("INSERT INTO users (chat_id, user_id, nickname) VALUES (?, ?, ?) ON CONFLICT(chat_id, user_id) DO UPDATE SET nickname = ?", (chat_item, tid, nn, nn))
            conn.commit()
            await send_log(f"[id{m.from_id}|Админ] установил глобальный ник «{nn}» [id{tid}|игроку].")
            return await m.answer(ui_box("🌐 ГЛОБАЛЬНЫЙ НИК", [f"Игрок: [id{tid}|участник]", f"Новый ник: {nn}", f"Обновлено бесед: {len(all_chats)}"]))
        if cmd == "+снятьник":
            cursor.execute("UPDATE users SET nickname = 'Не установлен' WHERE chat_id = ? AND user_id = ?", (cid, tid))
            conn.commit()
            return await m.answer(f"✅ Ник сброшен для [id{tid}|игрока].")
        if cmd in ["+ник", "/snick"]:
            nn = get_tail(m, args, 2)
            if not nn:
                return await m.answer("⚠️ Укажите ник. Пример: +ник @игрок Ivan_Petrov")
            cursor.execute("UPDATE users SET nickname = ? WHERE chat_id = ? AND user_id = ?", (nn, cid, tid))
            conn.commit()
            return await m.answer(f"✅ Ник установлен: {nn}")
        if cmd == "-мут":
            cursor.execute("UPDATE users SET mute_until = 0 WHERE chat_id = ? AND user_id = ?", (cid, tid))
            conn.commit()
            return await m.answer("🔊 Мут снят.")
        idx = 1 if m.reply_message else 2
        dur_token = first(args[idx:])
        if not dur_token:
            return await m.answer("⚠️ Пример: +мут @игрок 30м Флуд (или 2ч / 1д)")
        parsed = parse_duration(dur_token)
        if not parsed:
            return await m.answer("⚠️ Укажите корректное время (30м, 2ч, 1д).")
        reason = " ".join(args[idx+1:]) or "Не указана"
        dur_sec, dur_txt = parsed
        cursor.execute("UPDATE users SET mute_until = ? WHERE chat_id = ? AND user_id = ?", (now + dur_sec, cid, tid))
        conn.commit()
        await m.answer(ui_box("🔇 ВЫДАН МУТ", [f"Игрок: [id{tid}|участник]", f"Срок: {dur_txt}", f"Причина: {reason}"]))
        await send_log(f"[id{m.from_id}|Админ] выдал мут ({dur_txt}) [id{tid}|игроку].")
    elif cmd in ["+пред", "-пред", "+выг", "-выг", "/warn", "/unwarn", "+снятьвсе"]:
        req = 1 if cmd in ["+пред", "-пред"] else (3 if cmd == "+снятьвсе" else 2)
        if acc < req:
            return await m.answer(f"❌ Нужен {req}+ ур.")
        tid = get_target(m, args)
        if not tid:
            return await m.answer("⚠️ Укажите игрока.")
        tn, _, _, tw, tp, _, _, _, _ = get_user(cid, tid)
        if cmd == "+снятьвсе":
            cursor.execute("UPDATE users SET warns = 0, preds = 0, mute_until = 0 WHERE chat_id = ? AND user_id = ?", (cid, tid))
            conn.commit()
            return await m.answer(f"✨ Все наказания сняты с [id{tid}|игрока].")
        if cmd in ["-пред", "-выг", "/unwarn"]:
            if cmd == "-пред":
                cursor.execute("UPDATE users SET preds = ? WHERE chat_id = ? AND user_id = ?", (max(0, tp - 1), cid, tid))
                conn.commit()
                return await m.answer(f"✅ Пред снят ({max(0, tp - 1)}/2).")
            cursor.execute("UPDATE users SET warns = ? WHERE chat_id = ? AND user_id = ?", (max(0, tw - 1), cid, tid))
            conn.commit()
            return await m.answer(f"✅ Выговор снят ({max(0, tw - 1)}/3).")
        reason = get_tail(m, args, 2) or "Не указана"
        if cmd == "+пред":
            tp += 1
            if tp >= 2:
                tp, tw = 0, tw + 1
        else:
            tw += 1
        if tw >= 3:
            cursor.execute("UPDATE users SET warns = 0, preds = 0 WHERE chat_id = ? AND user_id = ?", (cid, tid))
            conn.commit()
            await m.answer(ui_box("🚫 ИСКЛЮЧЕНИЕ (3/3 ВЫГОВОРОВ)", [f"Игрок: [id{tid}|{tn}]", f"Причина: {reason}"]))
            try:
                await bot.api.messages.remove_chat_user(chat_id=m.chat_id, member_id=tid)
            except Exception:
                pass
        else:
            cursor.execute("UPDATE users SET warns = ?, preds = ? WHERE chat_id = ? AND user_id = ?", (tw, tp, cid, tid))
            conn.commit()
            await m.answer(ui_box("⚠️ ВЫДАНО НАКАЗАНИЕ", [f"Игрок: [id{tid}|{tn}]", f"Статус: Выги {tw}/3 | Преды {tp}/2", f"Причина: {reason}"]))
        await send_log(f"[id{m.from_id}|Админ] выдал {cmd} [id{tid}|игроку] ({tw}/3, {tp}/2).")
    elif cmd in ["+кик", "/kick", "+кикмолчунов", "+закреп", "-закреп", "+тишина", "+антикапс", "+антифлуд", "+антиссылка", "+автоочистка", "+созыв", "+очистить", "+инфочат"]:
        req = 3 if cmd == "+кикмолчунов" else 2
        if acc < req:
            return await m.answer(f"❌ Нужен {req}+ ур.")
        if cmd == "+закреп":
            if not m.reply_message:
                return await m.answer("⚠️ Ответьте на сообщение, которое нужно закрепить.")
            try:
                await bot.api.messages.pin(peer_id=cid, conversation_message_id=m.reply_message.conversation_message_id)
                return await m.answer("📌 Сообщение закреплено.")
            except Exception:
                return await m.answer("⚠️ Не удалось закрепить сообщение (проверьте права администратора у бота).")
        elif cmd == "-закреп":
            try:
                await bot.api.messages.unpin(peer_id=cid)
                return await m.answer("📍 Сообщение откреплено.")
            except Exception:
                return await m.answer("⚠️ Не удалось открепить сообщение.")
        elif cmd in ["+кик", "/kick"]:
            tid = get_target(m, args)
            if not tid or tid == OWNER_ID:
                return await m.answer("⚠️ Укажите корректного игрока.")
            if await check_anti_sliv(cid, m.chat_id, m.from_id):
                return
            reason = get_tail(m, args, 2) or "Не указана"
            await m.answer(ui_box("👢 ИСКЛЮЧЕНИЕ ИЗ ЧАТА", [f"Игрок: [id{tid}|участник]", f"Причина: {reason}"]))
            try:
                await bot.api.messages.remove_chat_user(chat_id=m.chat_id, member_id=tid)
            except Exception:
                pass
        elif cmd == "+кикмолчунов":
            mem = await bot.api.messages.get_conversation_members(peer_id=cid)
            k = 0
            for i in mem.items:
                if i.member_id > 0 and i.member_id != OWNER_ID:
                    _, _, u_acc, _, _, _, u_msgs, _, _ = get_user(cid, i.member_id)
                    if u_acc == 0 and u_msgs == 0:
                        try:
                            await bot.api.messages.remove_chat_user(chat_id=m.chat_id, member_id=i.member_id)
                            k += 1
                        except Exception:
                            pass
            await m.answer(f"🧹 Исключено молчунов: {k}.")
        elif cmd in ["+тишина", "+антикапс", "+антифлуд", "+антиссылка", "+автоочистка"]:
            col_map = {
                "+тишина": ("silence", sil),
                "+антикапс": ("anticaps", acaps),
                "+антифлуд": ("antiflood", aflood),
                "+антиссылка": ("antilink", alink),
                "+автоочистка": ("autoclean_sys", aclean_sys)
            }
            col, cur_val = col_map[cmd]
            nv = 0 if cur_val == 1 else 1
            cursor.execute(f"UPDATE chat_settings SET {col} = ? WHERE chat_id = ?", (nv, cid))
            conn.commit()
            await m.answer(f"⚙️ Режим «{cmd[1:]}»: {'Включён ✅' if nv == 1 else 'Выключен ❌'}")
        elif cmd == "+созыв":
            mem = await bot.api.messages.get_conversation_members(peer_id=cid)
            tags = [f"[id{i.member_id}|•]" for i in mem.items if i.member_id > 0]
            await m.answer(f"📢 Внимание! {' '.join(args[1:]) or 'Общий сбор!'}\n" + "".join(tags))
        elif cmd == "+очистить":
            await m.answer("🧹 Чат очищен.\n" + "\n" * 25 + "✨ Продолжаем общение!")
        elif cmd == "+инфочат":
            cursor.execute("SELECT COUNT(*) FROM users WHERE chat_id = ?", (cid,))
            (u_c,) = cursor.fetchone()
            cursor.execute("SELECT COUNT(*) FROM local_bans WHERE chat_id = ?", (cid,))
            (b_c,) = cursor.fetchone()
            await m.answer(ui_box(
                "ℹ️ ПАСПОРТ БЕСЕДЫ",
                [
                    f"ID чата: {cid}",
                    f"Участников в базе: {u_c} | Банов: {b_c}",
                    f"Приветствие: {'Вкл' if w_enabled else 'Выкл'} | Тишина: {'Вкл' if sil else 'Выкл'}",
                    f"Капс: {'Вкл' if acaps else 'Выкл'} | Флуд: {'Вкл' if aflood else 'Выкл'} | Ссылки: {'Вкл' if alink else 'Выкл'}",
                    f"Автоочистка: {'Вкл' if aclean_sys else 'Выкл'} | Антислив: Вкл"
                ]
            ))
    elif cmd in ["+приветствие", "+приветствие_режим", "-приветствие", "+устправила", "+устссылки", "+сбросстатистики", "+чсбота", "-чсбота", "+логчат", "-логчат", "+рассылка", "+бэкап"]:
        if cmd == "+бэкап":
            if m.from_id != OWNER_ID:
                return await m.answer("❌ Команда доступна только владельцу бота.")
            conn.commit()
            try:
                doc = await doc_uploader.upload(
                    file_source="rp_manager_network.db",
                    peer_id=OWNER_ID,
                    title=f"backup_{datetime.now().strftime('%Y-%m-%d_%H-%M')}.db"
                )
                await bot.api.messages.send(
                    peer_id=OWNER_ID,
                    message="💾 Резервная копия базы данных успешно создана!",
                    attachment=doc,
                    random_id=0
                )
                return await m.answer("✅ Файл базы данных отправлен вам в личные сообщения.")
            except Exception as e:
                return await m.answer(f"⚠️ Не удалось отправить бэкап (напишите боту в ЛС сначала). Ошибка: {e}")

        req = 4 if cmd in ["+чсбота", "-чсбота", "+логчат", "-логчат", "+рассылка"] else 3
        if acc < req:
            return await m.answer(f"❌ Нужен {req}+ ур.")
        if cmd == "+приветствие_режим":
            target_cid = cid
            target_label = "текущей беседе"
            num_str = first(args[1:])
            if num_str.isdigit():
                if acc < 4:
                    return await m.answer("❌ Управление чужим чатом по номеру доступно с 4+ ур.")
                num = int(num_str)
                cursor.execute("SELECT chat_id, title FROM known_chats ORDER BY ROWID ASC")
                rows = cursor.fetchall()
                if num < 1 or num > len(rows):
                    return await m.answer(f"⚠️ Неверный номер. В списке «+чаты» сейчас бесед: {len(rows)}.")
                target_cid, target_title = rows[num - 1]
                target_label = f"беседе «{target_title}» (№{num})"
            t_set = get_chat_settings(target_cid)
            nv = 0 if t_set == 1 else 1
            cursor.execute("UPDATE chat_settings SET welcome_enabled = ? WHERE chat_id = ?", (nv, target_cid))
            conn.commit()
            return await m.answer(f"👋 Приветствие в {target_label}: {'Включено ✅' if nv == 1 else 'Отключено ❌'}")
        if cmd == "-приветствие":
            target_cid = cid
            target_label = "текущей беседе"
            num_str = first(args[1:])
            if num_str.isdigit():
                if acc < 4:
                    return await m.answer("❌ Управление чужим чатом по номеру доступно с 4+ ур.")
                num = int(num_str)
                cursor.execute("SELECT chat_id, title FROM known_chats ORDER BY ROWID ASC")
                rows = cursor.fetchall()
                if num < 1 or num > len(rows):
                    return await m.answer(f"⚠️ Неверный номер. В списке «+чаты» сейчас бесед: {len(rows)}.")
                target_cid, target_title = rows[num - 1]
                target_label = f"беседе «{target_title}» (№{num})"
            get_chat_settings(target_cid)
            cursor.execute("UPDATE chat_settings SET welcome_text = '', welcome_enabled = 0 WHERE chat_id = ?", (target_cid,))
            conn.commit()
            return await m.answer(f"🗑 Приветствие в {target_label} полностью удалено и отключено.")
        if cmd == "+сбросстатистики":
            cursor.execute("UPDATE users SET msgs = 0 WHERE chat_id = ?", (cid,))
            conn.commit()
            return await m.answer("🔄 Счётчики сообщений в чате обнулены.")
        if cmd in ["+логчат", "-логчат"]:
            if cmd == "-логчат":
                cursor.execute("DELETE FROM bot_config WHERE key = 'log_chat'")
            else:
                cursor.execute("INSERT OR REPLACE INTO bot_config VALUES ('log_chat', ?)", (str(cid),))
            conn.commit()
            return await m.answer("📜 Чат логов обновлён.")
        if cmd in ["+чсбота", "-чсбота"]:
            tid = get_target(m, args)
            if not tid or tid == OWNER_ID:
                return await m.answer("⚠️ Укажите игрока.")
            if cmd == "-чсбота":
                cursor.execute("DELETE FROM bot_blacklist WHERE user_id = ?", (tid,))
            else:
                cursor.execute("INSERT OR REPLACE INTO bot_blacklist VALUES (?, ?)", (tid, "ЧС бота"))
            conn.commit()
            return await m.answer(f"🚫 ЧС бота обновлён для [id{tid}|игрока].")
        txt = " ".join(args[1:])
        if not txt:
            return await m.answer("⚠️ Введите текст.")
        if cmd == "+приветствие":
            cursor.execute("UPDATE chat_settings SET welcome_text = ?, welcome_enabled = 1 WHERE chat_id = ?", (txt, cid))
            conn.commit()
            await m.answer("✅ Приветствие обновлено и включено.")
        elif cmd == "+устправила":
            cursor.execute("UPDATE chat_settings SET rules_text = ? WHERE chat_id = ?", (txt, cid))
            conn.commit()
            await m.answer("✅ Правила обновлены.")
        elif cmd == "+устссылки":
            cursor.execute("UPDATE chat_settings SET links_text = ? WHERE chat_id = ?", (txt, cid))
            conn.commit()
            await m.answer("✅ Ссылки проекта обновлены.")
        elif cmd == "+рассылка":
            cursor.execute("SELECT chat_id FROM known_chats")
            chats = cursor.fetchall()
            s = 0
            for (pid,) in chats:
                try:
                    await bot.api.messages.send(peer_id=pid, message=ui_box("📣 ОБЪЯВЛЕНИЕ ПРОЕКТА", [txt]), random_id=0)
                    s += 1
                except Exception:
                    pass
            await m.answer(f"✅ Отправлено в {s} из {len(chats)} чатов.")

bot.loop_wrapper.add_task(expiration_worker())
bot.run()
