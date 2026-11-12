import sqlite3
import re
import time
import asyncio
from datetime import datetime
from vkbottle.bot import Bot, Message

TOKEN = "vk1.a.nSVDeqVxBl5NwrIv-1FiT_lfVkQ5FTVcnVbgDjX7tNUIL-2uUQWxqUsyvZxkXB9expe5MeE51yCh6474-Wr2kaEfbJ09PJIBu6wL28VjeRKFsLFVrYu0GLFr5INSOcgps7tKxtAB-d2x_3s1xfH59TYTPcRz9bSX3PPcBfZgdWbOThKheFnUG72Xb9lM2T0YO0c_QBKJdQUOYILFq9tmQw"
OWNER_ID = 807140123

bot = Bot(token=TOKEN)
conn = sqlite3.connect("rp_manager_network.db")
cursor = conn.cursor()
START_TIME = time.time()

cursor.execute("CREATE TABLE IF NOT EXISTS known_chats (chat_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS global_staff (user_id INTEGER PRIMARY KEY, role_name TEXT DEFAULT 'Участник', access INTEGER DEFAULT 0)")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER, user_id INTEGER, nickname TEXT DEFAULT 'Не установлен',
        role_name TEXT DEFAULT 'Участник', access INTEGER DEFAULT 0,
        warns INTEGER DEFAULT 0, preds INTEGER DEFAULT 0, mute_until INTEGER DEFAULT 0,
        msgs INTEGER DEFAULT 0, rep INTEGER DEFAULT 0,
        PRIMARY KEY (chat_id, user_id)
    )
""")
cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_settings (
        chat_id INTEGER PRIMARY KEY, silence INTEGER DEFAULT 0,
        welcome_text TEXT DEFAULT 'Добро пожаловать в беседу!',
        rules_text TEXT DEFAULT 'Правила не установлены.',
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
    "ALTER TABLE users ADD COLUMN msgs INTEGER DEFAULT 0",
    "ALTER TABLE users ADD COLUMN rep INTEGER DEFAULT 0",
    "ALTER TABLE local_bans ADD COLUMN ban_until INTEGER DEFAULT 0",
    "ALTER TABLE global_bans ADD COLUMN ban_until INTEGER DEFAULT 0",
    "ALTER TABLE chat_settings ADD COLUMN rules_text TEXT DEFAULT 'Правила не установлены.'",
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

LINK_PATTERN = re.compile(
    r"(https?://|www\.|t\.me/|telegram\.me/|vk\.com/|vk\.me/|vk\.cc/|clck\.ru/|youtu\.be/|youtube\.com/|discord\.gg/|discord\.com/|"
    r"@(?:club|public|event)\d+|\[(?:club|public|event)\d+\||"
    r"\b[a-zA-Z0-9а-яё-]{2,}\.(?:ru|com|net|org|me|gg|io|xyz|info|biz|su|рф|online|site|store|top|club|pro|link|tk|ml|ga|cf|kz|by|ua)\b)",
    re.IGNORECASE
)

HELP_DICT = {
    "стата": "📊 +стата [@игрок]\nПоказывает профиль игрока: ник, должность, сообщения, репутацию и наказания.",
    "ник": "🏷 +ник [@игрок] [Ник]\nУстанавливает игровой ник участнику.\nПример: +ник @durov Ivan_Ivanov",
    "мут": "🔇 +мут [@игрок] [срок] [причина]\nПримеры: +мут @durov 30 Флуд | +мут @durov 2ч Спам\nСнять мут: -мут @игрок",
    "пред": "⚠️ +пред [@игрок] [причина]\nВыдаёт устное предупреждение (2 преда = 1 выговор).\nСнять пред: -пред @игрок",
    "выг": "📛 +выг [@игрок] [причина]\nВыдаёт строгий выговор (3 выговора = автокик).\nСнять выговор: -выг @игрок",
    "кик": "👢 +кик [@игрок] [причина]\nИсключает участника из текущей беседы.",
    "бан": "⛔ +бан [@игрок] [срок] [причина]\nНа время: +бан @durov 7д Слив (м/ч/д)\nНавсегда: +бан @durov Реклама\nРазбанить: -бан @игрок",
    "гбан": "🌐 +гбан [@игрок] [срок] [причина]\nГлобальный бан во всех чатах (на время или навсегда).\nРазбанить: -гбан @игрок",
    "чсбота": "🚫 +чсбота [@игрок]\nЗапрещает игроку пользоваться командами бота во всех беседах.\nУбрать из ЧС: -чсбота @игрок",
    "новыйгод": "🎄 +новыйгод (или +нг)\nПоказывает точный отсчёт дней, часов и минут до Нового года."
}

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
def register_chat(cid: int):
    cursor.execute("INSERT OR IGNORE INTO known_chats (chat_id) VALUES (?)", (cid,))
    conn.commit()

def set_second_owner(cid: int, uid: int):
    cursor.execute("""
        INSERT INTO users (chat_id, user_id, role_name, access)
        VALUES (?, ?, 'Второй владелец', 4)
        ON CONFLICT(chat_id, user_id) DO UPDATE SET role_name = 'Второй владелец', access = 4
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
    register_chat(cid)
    cursor.execute("""
        SELECT silence, welcome_text, rules_text, anticaps, antiflood, antilink, autoclean_sys
        FROM chat_settings WHERE chat_id = ?
    """, (cid,))
    r = cursor.fetchone()
    if not r:
        cursor.execute("INSERT INTO chat_settings (chat_id) VALUES (?)", (cid,))
        conn.commit()
        return (0, "Добро пожаловать в беседу!", "Правила не установлены.", 0, 0, 0, 1)
    return r

def get_global(uid: int):
    if uid == OWNER_ID:
        return ("Второй владелец", 4)
    cursor.execute("SELECT role_name, access FROM global_staff WHERE user_id = ?", (uid,))
    r = cursor.fetchone()
    return r if r else ("Участник", 0)

def get_user(cid: int, uid: int):
    register_chat(cid)
    cursor.execute("""
        SELECT nickname, role_name, access, warns, preds, mute_until, msgs, rep
        FROM users WHERE chat_id = ? AND user_id = ?
    """, (cid, uid))
    r = cursor.fetchone()
    if not r:
        def_role = "Второй владелец" if uid == OWNER_ID else "Участник"
        def_acc = 4 if uid == OWNER_ID else 0
        cursor.execute(
            "INSERT INTO users (chat_id, user_id, role_name, access) VALUES (?, ?, ?, ?)",
            (cid, uid, def_role, def_acc)
        )
        conn.commit()
        nick, lr, la, w, p, m, ms, rep = ("Не установлен", def_role, def_acc, 0, 0, 0, 0, 0)
    else:
        nick, lr, la, w, p, m, ms, rep = r
    if uid == OWNER_ID:
        return (nick, "Второй владелец", 4, w, p, m, ms, rep)
    gr, ga = get_global(uid)
    if ga >= la and ga > 0:
        return (nick, f"{gr} [Глобал]", ga, w, p, m, ms, rep)
    return (nick, lr, la, w, p, m, ms, rep)

async def send_log(text: str):
    cursor.execute("SELECT value FROM bot_config WHERE key = 'log_chat'")
    r = cursor.fetchone()
    if r and r[0]:
        try:
            await bot.api.messages.send(
                peer_id=int(r[0]),
                message=f"📜 ЖУРНАЛ ДЕЙСТВИЙ\n────────────\n{text}",
                random_id=0
            )
        except Exception:
            pass

def check_ban(cid: int, uid: int):
    now_ts = int(time.time())
    cursor.execute("SELECT reason, ban_until FROM global_bans WHERE user_id = ?", (uid,))
    gb = cursor.fetchone()
    if gb:
        if gb[1] > 0 and gb[1] <= now_ts:
            cursor.execute("DELETE FROM global_bans WHERE user_id = ?", (uid,))
            conn.commit()
        else:
            return ("Глобальный бан", gb[0], format_left(gb[1], now_ts))
    cursor.execute("SELECT reason, ban_until FROM local_bans WHERE chat_id = ? AND user_id = ?", (cid, uid))
    lb = cursor.fetchone()
    if lb:
        if lb[1] > 0 and lb[1] <= now_ts:
            cursor.execute("DELETE FROM local_bans WHERE chat_id = ? AND user_id = ?", (cid, uid))
            conn.commit()
        else:
            return ("Бан чата", lb[0], format_left(lb[1], now_ts))
    return None

def get_target(m: Message, args: list):
    if m.reply_message:
        return m.reply_message.from_id
    if len(args) > 1:
        match = re.search(r"\[id(\d+)\|", args[1])
        if match:
            return int(match.group(1))
        if args[1].isdigit():
            return int(args[1])
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
        except Exception:
            pass

@bot.loop_wrapper.interval(seconds=3600)
async def keep_alive():
    pass
@bot.on.chat_message()
async def handler(m: Message):
    cid = m.peer_id
    cursor.execute("SELECT 1 FROM known_chats WHERE chat_id = ?", (cid,))
    is_new_chat = cursor.fetchone() is None
    register_chat(cid)

    if is_new_chat:
        await auto_assign_owner(cid)

    sil, w_text, rules_text, acaps, aflood, alink, aclean_sys = get_chat_settings(cid)

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
                u_acc = get_user(cid, uid)[2]
                if u_acc == 0:
                    try:
                        await bot.api.messages.remove_chat_user(chat_id=m.chat_id, member_id=uid)
                        await m.answer(
                            f"🚪 АВТОКИК\n"
                            f"────────────\n"
                            f"👤 Участник [id{uid}|игрок] покинул беседу и был исключён."
                        )
                        await send_log(f"🚪 Автокик вышедшего: [id{uid}|игрок] (чат {cid}).")
                    except Exception:
                        pass
            return

        if act_type == "chat_invite_user":
            uid = m.action.member_id
            if uid and uid < 0:
                await auto_assign_owner(cid)
                return

            if uid and uid > 0:
                if uid == OWNER_ID:
                    set_second_owner(cid, OWNER_ID)
                    return

                ban = check_ban(cid, uid)
                if ban:
                    await m.answer(
                        f"⛔ ДОСТУП ЗАКРЫТ\n"
                        f"────────────\n"
                        f"👤 Игрок: [id{uid}|участник]\n"
                        f"📌 Статус: {ban[0]} ({ban[2]})\n"
                        f"💬 Причина: {ban[1]}"
                    )
                    try:
                        await bot.api.messages.remove_chat_user(chat_id=m.chat_id, member_id=uid)
                    except Exception:
                        pass
                    return
                get_user(cid, uid)
                await m.answer(
                    f"👋 ДОБРО ПОЖАЛОВАТЬ\n"
                    f"────────────\n"
                    f"Приветствуем, [id{uid}|игрок]!\n"
                    f"💬 {w_text}\n\n"
                    f"💡 Напиши «+помощь», чтобы открыть список команд."
                )
            return
    if not m.text or m.from_id < 0:
        return

    if m.from_id != OWNER_ID and check_ban(cid, m.from_id):
        try:
            await bot.api.messages.remove_chat_user(chat_id=m.chat_id, member_id=m.from_id)
        except Exception:
            pass
        return

    args = m.text.strip().split()
    if not args:
        return
    cmd = args[0].lower()

    nick, role, acc, warns, preds, mute, msgs, rep = get_user(cid, m.from_id)
    now = int(time.time())

    if acc < 1:
        if mute > now or sil == 1:
            try:
                await bot.api.messages.delete(peer_id=cid, cmids=[m.conversation_message_id], delete_for_all=True)
            except Exception:
                pass
            return
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
        sub = args[1].lower().lstrip("+/-!") if len(args) > 1 else ""
        if sub in HELP_DICT:
            return await m.answer(f"📖 СПРАВКА ПО КОМАНДЕ\n────────────\n{HELP_DICT[sub]}")
        if sub == "игрок":
            return await m.answer(
                "👤 КОМАНДЫ ИГРОКОВ [0+ УР.]\n"
                "────────────\n"
                "▸ +стата [@игрок] — профиль и статистика\n"
                "▸ +новыйгод (+нг) — дней до Нового года\n"
                "▸ +топ — топ активных участников\n"
                "▸ +реп / -реп [@игрок] — репутация\n"
                "▸ +ники / +состав / +гсостав — списки\n"
                "▸ +онлайн / +правила / +пинг — инфо\n\n"
                "💡 Подробнее: +помощь [команда]"
            )
        if sub == "модер":
            return await m.answer(
                "🛡 МОДЕРАЦИЯ [1+ УР.]\n"
                "────────────\n"
                "▸ +ник [@игрок] [Ник] — поставить ник\n"
                "▸ +снятьник [@игрок] — сбросить ник\n"
                "▸ +найтиник [часть] — поиск по никам\n"
                "▸ +мут [@игрок] [срок] [причина] — мут (30м/2ч/1д)\n"
                "▸ -мут [@игрок] — снять мут / +мутлист\n"
                "▸ +пред / -пред [@игрок] — пред (2=выг)\n"
                "▸ +преды / +выги — список нарушителей\n"
                "▸ +заметка [@игрок] [текст] / +заметки"
            )
        if sub == "админ":
            return await m.answer(
                "⚔️ АДМИНИСТРИРОВАНИЕ [2+ УР.]\n"
                "────────────\n"
                "▸ +выг / -выг [@игрок] [причина] — выговор\n"
                "▸ +кик [@игрок] [причина] — исключить\n"
                "▸ +бан [@игрок] [срок] [причина] — временный/вечный бан\n"
                "▸ -бан [@игрок] — разбанить / +баны — список\n"
                "▸ +тишина / +антикапс / +антифлуд\n"
                "▸ +антиссылка / +автоочистка — режимы\n"
                "▸ +созыв [текст] / +очистить / +инфочат"
            )
        if sub in ["га", "руководство", "старшие"]:
            return await m.answer(
                "👑 РУКОВОДСТВО И РАНГИ [3-4 УР.]\n"
                "────────────\n"
                "▸ +гбан [@игрок] [срок] [причина] — глобал бан\n"
                "▸ -гбан [@игрок] / +гкик / +гбаны / +чаты\n"
                "▸ +снятьвсе [@игрок] — снять наказания\n"
                "▸ +кикмолчунов — кик тех, у кого 0 сообщ.\n"
                "▸ +приветствие / +устправила [текст]\n"
                "▸ +сбросстатистики — обнулить счётчик\n"
                "▸ Ранги: +модер, +админ, +га, +зга, +спец, +снять\n"
                "▸ Глобал: +гмодер, +гадмин, +гга, +гспец, +гснять\n"
                "▸ [4 ур.]: +логчат, -логчат, +чсбота, -чсбота, +рассылка"
            )
        return await m.answer(
            "📋 СПРАВОЧНИК КОМАНД\n"
            "────────────\n"
            "Выберите нужный раздел:\n\n"
            "👤 +помощь игрок — профиль, Новый год, списки\n"
            "🛡 +помощь модер — ники, муты, преды, досье\n"
            "⚔️ +помощь админ — выги, баны, защита чата\n"
            "👑 +помощь га — глобал-бан, ранги, настройки\n\n"
            "💡 Совет: команду можно писать ответом на сообщение игрока!"
     elif cmd in ["+новыйгод", "+нг", "/newyear"]:
        now_dt = datetime.now()
        next_year = now_dt.year + 1
        ny_dt = datetime(next_year, 1, 1, 0, 0, 0)
        diff = ny_dt - now_dt
        await m.answer(
            f"🎄 ДО НОВОГО {next_year} ГОДА\n"
            f"────────────\n"
            f"📅 Дней: {diff.days}\n"
            f"⏰ Часов: {diff.seconds // 3600} | Минут: {(diff.seconds % 3600) // 60}"
        )

    elif cmd in ["+пинг", "/ping"]:
        ms = round((time.time() - m.date) * 1000)
        up = int(time.time() - START_TIME) // 60
        await m.answer(f"🏓 Понг!\n⏱ Отклик: {abs(ms)} мс | Аптайм: {up} мин.")

    elif cmd in ["+правила", "/rules"]:
        await m.answer(f"📖 ПРАВИЛА БЕСЕДЫ\n────────────\n{rules_text}")

    elif cmd in ["+стата", "+профиль", "/stats", "!стата"]:
        tid = get_target(m, args) or m.from_id
        tn, tr, ta, tw, tp, tm, tmsgs, trep = get_user(cid, tid)
        ms_status = f"Активен ({format_left(tm, now)})" if tm > now else "Нет"
        cursor.execute("SELECT COUNT(*) FROM user_notes WHERE chat_id = ? AND user_id = ?", (cid, tid))
        ncnt = cursor.fetchone()[0]
        await m.answer(
            f"📊 ПРОФИЛЬ ИГРОКА\n"
            f"────────────\n"
            f"👤 Игрок: [id{tid}|{tn}]\n"
            f"🎖 Должность: {tr} ({ta} ур.)\n"
            f"⭐ Репутация: {trep} | 💬 Сообщений: {tmsgs + (1 if tid == m.from_id else 0)}\n"
            f"⚠️ Выги: {tw}/3 | Преды: {tp}/2\n"
            f"🗂 Досье: {ncnt} | 🔇 Мут: {ms_status}"
        )

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
            await m.answer(f"🟢 В СЕТИ ({len(online_list)})\n────────────\n" + "\n".join(online_list[:25]))
        except Exception:
            await m.answer("⚠️ Не удалось получить список онлайн (проверьте права администратора у бота).")

    elif cmd in ["+реп", "-реп"]:
        tid = get_target(m, args)
        if not tid or tid == m.from_id:
            return await m.answer("⚠️ Укажите другого игрока.")
        get_user(cid, tid)
        d = 1 if cmd == "+реп" else -1
        cursor.execute("UPDATE users SET rep = rep + ? WHERE chat_id = ? AND user_id = ?", (d, cid, tid))
        conn.commit()
        await m.answer(f"⭐ Репутация [id{tid}|игрока] изменена! Теперь: {get_user(cid, tid)[7]}")

    elif cmd in ["+топ", "/top", "!топ"]:
        cursor.execute("SELECT user_id, nickname, msgs, rep FROM users WHERE chat_id = ? AND msgs > 0 ORDER BY msgs DESC LIMIT 10", (cid,))
        rows = cursor.fetchall()
        if not rows:
            return await m.answer("📭 Статистика сообщений пока пуста.")
        lines = ["🏆 ТОП АКТИВНЫХ ИГРОКОВ", "────────────"]
        for i, (u, n, c, r) in enumerate(rows, 1):
            lines.append(f"{i}. [id{u}|{n if n != 'Не установлен' else 'Игрок'}] — {c} сообщ. (⭐{r})")
        await m.answer("\n".join(lines))

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
        await m.answer(f"🗂 ДОСЬЕ [id{tid}|ИГРОКА]\n────────────\n" + "\n".join([f"▸ {t} (от [id{a}|адм])" for a, t in rows]))
       )
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
            return await m.answer(f"🔍 ПОИСК НИКА: {q}\n────────────\n" + "\n".join([f"▸ [id{u}|{n}]" for u, n in rows]))
        cursor.execute("SELECT user_id, nickname FROM users WHERE chat_id = ? AND user_id != ? AND nickname != 'Не установлен'", (cid, OWNER_ID))
        rows = cursor.fetchall()
        if not rows:
            return await m.answer("📭 В чате ещё не установлены ники.")
        await m.answer("📝 СПИСОК НИКОВ ЧАТА\n────────────\n" + "\n".join([f"{i}. [id{u}|{n}] — {get_user(cid, u)[1]}" for i, (u, n) in enumerate(rows, 1)]))

    elif cmd in ["+состав", "+админы", "+модеры", "+гсостав"]:
        if cmd == "+гсостав":
            cursor.execute("SELECT user_id, role_name, access FROM global_staff WHERE access >= 1 AND user_id != ? ORDER BY access DESC", (OWNER_ID,))
            rows = cursor.fetchall()
            if not rows:
                return await m.answer("📭 Глобальный состав пуст.")
            res = ["🌐 ГЛОБАЛЬНЫЙ СОСТАВ\n────────────"]
            for u, r, a in rows:
                res.append(f"🔹 [{a} ур. | {r}] — [id{u}|Админ]")
            return await m.answer("\n".join(res))
        cursor.execute("SELECT user_id, nickname FROM users WHERE chat_id = ? AND user_id != ?", (cid, OWNER_ID))
        st = []
        for u, n in cursor.fetchall():
            u_info = get_user(cid, u)
            if u_info[2] >= 1:
                st.append((u_info[2], f"🔹 [{u_info[2]} ур. | {u_info[1]}] — [id{u}|{n if n != 'Не установлен' else 'Без ника'}]"))
        if not st:
            return await m.answer("📭 Администрация чата не назначена.")
        st.sort(key=lambda x: x[0], reverse=True)
        await m.answer("🛡 СОСТАВ ЧАТА\n────────────\n" + "\n".join([x[1] for x in st]))

    elif cmd in ["+мутлист", "+преды", "+выги", "+баны", "+гбаны", "+чаты"]:
        if cmd == "+мутлист":
            if acc < 1:
                return await m.answer("❌ Нужен 1+ ур.")
            cursor.execute("SELECT user_id, nickname, mute_until FROM users WHERE chat_id = ? AND mute_until > ?", (cid, now))
            rows = cursor.fetchall()
            if not rows:
                return await m.answer("📭 Активных мутов нет.")
            return await m.answer("🔇 АКТИВНЫЕ МУТЫ\n────────────\n" + "\n".join([f"▸ [id{u}|{n}] — {format_left(mu, now)}" for u, n, mu in rows]))
        if cmd in ["+преды", "+выги"]:
            if acc < 1:
                return await m.answer("❌ Нужен 1+ ур.")
            cursor.execute("SELECT user_id, nickname, warns, preds FROM users WHERE chat_id = ? AND (warns > 0 OR preds > 0)", (cid,))
            rows = cursor.fetchall()
            if not rows:
                return await m.answer("📭 Нарушителей нет.")
            return await m.answer("⚠️ НАРУШИТЕЛИ\n────────────\n" + "\n".join([f"▸ [id{u}|{n}] — Выги: {w}/3 | Преды: {p}/2" for u, n, w, p in rows]))
        if cmd == "+баны":
            if acc < 2:
                return await m.answer("❌ Нужен 2+ ур.")
            cursor.execute("DELETE FROM local_bans WHERE chat_id = ? AND ban_until > 0 AND ban_until <= ?", (cid, now))
            conn.commit()
            cursor.execute("SELECT user_id, reason, ban_until FROM local_bans WHERE chat_id = ?", (cid,))
            rows = cursor.fetchall()
            if not rows:
                return await m.answer("📭 Локальный бан-лист пуст.")
            return await m.answer("⛔ БАНЫ ЧАТА\n────────────\n" + "\n".join([f"▸ [id{u}|Игрок] [{format_left(bu, now)}] — {r}" for u, r, bu in rows]))
        if cmd == "+гбаны":
            if acc < 3:
                return await m.answer("❌ Нужен 3+ ур.")
            cursor.execute("DELETE FROM global_bans WHERE ban_until > 0 AND ban_until <= ?", (now,))
            conn.commit()
            cursor.execute("SELECT user_id, reason, ban_until FROM global_bans")
            rows = cursor.fetchall()
            if not rows:
                return await m.answer("📭 Глобальный бан-лист пуст.")
            return await m.answer("🌐 ГЛОБАЛЬНЫЕ БАНЫ\n────────────\n" + "\n".join([f"▸ [id{u}|Игрок] [{format_left(bu, now)}] — {r}" for u, r, bu in rows]))
        if acc < 3:
            return await m.answer("❌ Нужен 3+ ур.")
        cursor.execute("SELECT COUNT(*) FROM known_chats")
        await m.answer(f"🌐 Бот активен в {cursor.fetchone()[0]} беседах.")
    elif cmd in ["+модер", "+админ", "+га", "+зга", "+спец", "+снять", "+гмодер", "+гадмин", "+гга", "+гзга", "+гспец", "+гснять"]:
        if acc < 2:
            return await m.answer("❌ Нужен 2+ ур.")
        tid = get_target(m, args)
        if not tid or tid == OWNER_ID or tid == m.from_id:
            return await m.answer("⚠️ Укажите корректного игрока.")
        is_glob = cmd.startswith("+г") and cmd not in ["+га", "+гснять"] or cmd == "+гснять"
        t_acc = get_global(tid)[1] if is_glob else get_user(cid, tid)[2]
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
        await m.answer(
            f"🎖 НАЗНАЧЕНИЕ РАНГА\n"
            f"────────────\n"
            f"👤 Игрок: [id{tid}|участник]\n"
            f"📌 Роль: {title} ({lvl} ур.)"
        )
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
        t_acc = get_global(tid)[1] if req == 3 else get_user(cid, tid)[2]
        if tid == OWNER_ID or (t_acc >= acc and m.from_id != OWNER_ID):
            return await m.answer("❌ Нельзя применить к этому админу.")

        idx_start = 1 if m.reply_message else 2
        ban_until = 0
        dur_label = "Навсегда (бесконечный)"
        if cmd in ["+бан", "+гбан"] and len(args) > idx_start:
            parsed = parse_duration(args[idx_start])
            if parsed:
                ban_until = now + parsed[0]
                dur_label = parsed[1]
                idx_start += 1
        reason = " ".join(args[idx_start:]) or "Не указана"

        if cmd == "+бан":
            cursor.execute("INSERT OR REPLACE INTO local_bans VALUES (?, ?, ?, ?)", (cid, tid, reason, ban_until))
            cursor.execute("UPDATE users SET access = 0, role_name = 'Участник' WHERE chat_id = ? AND user_id = ?", (cid, tid))
            conn.commit()
            await m.answer(
                f"⛔ БАН В ЧАТЕ\n"
                f"────────────\n"
                f"👤 Игрок: [id{tid}|участник]\n"
                f"⏱ Срок: {dur_label}\n"
                f"💬 Причина: {reason}"
            )
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
            srok_line = f"\n⏱ Срок: {dur_label}" if cmd == "+гбан" else ""
            await m.answer(
                f"🌐 ГЛОБАЛЬНАЯ МЕРА ({cmd})\n"
                f"────────────\n"
                f"👤 Игрок: [id{tid}|участник] ({k}/{len(chats)} чатов){srok_line}\n"
                f"💬 Причина: {reason}"
            )
        await send_log(f"[id{m.from_id}|Админ] применил {cmd} ({dur_label}) к [id{tid}|игроку]. Причина: {reason}")

    elif cmd in ["+ник", "/snick", "+снятьник", "+мут", "-мут"]:
        if acc < 1:
            return await m.answer("❌ Нужен 1+ ур.")
        tid = get_target(m, args)
        if not tid:
            return await m.answer("⚠️ Укажите игрока.")
        get_user(cid, tid)
        if cmd == "+снятьник":
            cursor.execute("UPDATE users SET nickname = 'Не установлен' WHERE chat_id = ? AND user_id = ?", (cid, tid))
            conn.commit()
            return await m.answer(f"✅ Ник сброшен для [id{tid}|игрока].")
        if cmd in ["+ник", "/snick"]:
            nn = get_tail(m, args, 2)
            if not nn:
                return await m.answer("⚠️ Укажите ник.\nПример: +ник @игрок Ivan_Petrov")
            cursor.execute("UPDATE users SET nickname = ? WHERE chat_id = ? AND user_id = ?", (nn, cid, tid))
            conn.commit()
            return await m.answer(f"✅ Ник установлен: {nn}")
        if cmd == "-мут":
            cursor.execute("UPDATE users SET mute_until = 0 WHERE chat_id = ? AND user_id = ?", (cid, tid))
            conn.commit()
            return await m.answer("🔊 Мут снят.")
        idx = 1 if m.reply_message else 2
        if len(args) <= idx:
            return await m.answer("⚠️ Пример: +мут @игрок 30м Флуд (или 2ч / 1д)")
        parsed = parse_duration(args[idx])
        if not parsed:
            return await m.answer("⚠️ Укажите корректное время (например: 30, 30м, 2ч, 1д).")
        reason = " ".join(args[idx+1:]) or "Не указана"
        cursor.execute("UPDATE users SET mute_until = ? WHERE chat_id = ? AND user_id = ?", (now + parsed[0], cid, tid))
        conn.commit()
        await m.answer(
            f"🔇 ВЫДАН МУТ\n"
            f"────────────\n"
            f"👤 Игрок: [id{tid}|участник]\n"
            f"⏱ Срок: {parsed[1]}\n"
            f"💬 Причина: {reason}"
        )
        await send_log(f"[id{m.from_id}|Админ] выдал мут ({parsed[1]}) [id{tid}|игроку].")

    elif cmd in ["+пред", "-пред", "+выг", "-выг", "/warn", "/unwarn", "+снятьвсе"]:
        req = 1 if cmd in ["+пред", "-пред"] else (3 if cmd == "+снятьвсе" else 2)
        if acc < req:
            return await m.answer(f"❌ Нужен {req}+ ур.")
        tid = get_target(m, args)
        if not tid:
            return await m.answer("⚠️ Укажите игрока.")
        tn, _, _, tw, tp, _, _, _ = get_user(cid, tid)
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
            await m.answer(
                f"🚫 ИСКЛЮЧЕНИЕ (3/3 ВЫГОВОРОВ)\n"
                f"────────────\n"
                f"👤 Игрок: [id{tid}|{tn}]\n"
                f"💬 Причина: {reason}"
            )
            try:
                await bot.api.messages.remove_chat_user(chat_id=m.chat_id, member_id=tid)
            except Exception:
                pass
        else:
            cursor.execute("UPDATE users SET warns = ?, preds = ? WHERE chat_id = ? AND user_id = ?", (tw, tp, cid, tid))
            conn.commit()
            await m.answer(
                f"⚠️ ВЫДАНО НАКАЗАНИЕ\n"
                f"────────────\n"
                f"👤 Игрок: [id{tid}|{tn}]\n"
                f"📊 Статус: Выги {tw}/3 | Преды {tp}/2\n"
                f"💬 Причина: {reason}"
            )
        await send_log(f"[id{m.from_id}|Админ] выдал {cmd} [id{tid}|игроку] ({tw}/3, {tp}/2).")
    elif cmd in ["+кик", "/kick", "+кикмолчунов", "+тишина", "+антикапс", "+антифлуд", "+антиссылка", "+автоочистка", "+созыв", "+очистить", "+инфочат"]:
        req = 3 if cmd == "+кикмолчунов" else 2
        if acc < req:
            return await m.answer(f"❌ Нужен {req}+ ур.")
        if cmd in ["+кик", "/kick"]:
            tid = get_target(m, args)
            if not tid:
                return await m.answer("⚠️ Укажите игрока.")
            reason = get_tail(m, args, 2) or "Не указана"
            await m.answer(
                f"👢 ИСКЛЮЧЕНИЕ ИЗ ЧАТА\n"
                f"────────────\n"
                f"👤 Игрок: [id{tid}|участник]\n"
                f"💬 Причина: {reason}"
            )
            try:
                await bot.api.messages.remove_chat_user(chat_id=m.chat_id, member_id=tid)
            except Exception:
                pass
        elif cmd == "+кикмолчунов":
            mem = await bot.api.messages.get_conversation_members(peer_id=cid)
            k = 0
            for i in mem.items:
                if i.member_id > 0 and i.member_id != OWNER_ID:
                    u_info = get_user(cid, i.member_id)
                    if u_info[2] == 0 and u_info[6] == 0:
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
            await m.answer(f"⚙️ Режим {cmd[1:]}: {'Включён ✅' if nv == 1 else 'Выключен ❌'}")
        elif cmd == "+созыв":
            mem = await bot.api.messages.get_conversation_members(peer_id=cid)
            tags = [f"[id{i.member_id}|•]" for i in mem.items if i.member_id > 0]
            await m.answer(f"📢 Внимание! {' '.join(args[1:]) or 'Общий сбор!'}\n" + "".join(tags))
        elif cmd == "+очистить":
            await m.answer("🧹 Чат очищен.\n" + "\n" * 25 + "✨ Продолжаем общение!")
        elif cmd == "+инфочат":
            cursor.execute("SELECT COUNT(*) FROM users WHERE chat_id = ?", (cid,))
            u_c = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM local_bans WHERE chat_id = ?", (cid,))
            b_c = cursor.fetchone()[0]
            await m.answer(
                f"ℹ️ ПАСПОРТ БЕСЕДЫ\n"
                f"────────────\n"
                f"🆔 ID: {cid} | Игроков: {u_c} | Банов: {b_c}\n"
                f"🛡 Защита: Тишина [{sil}] | Капс [{acaps}] | Флуд [{aflood}] | Ссылки [{alink}]\n"
                f"⚙️ Доп: Автоочистка [{aclean_sys}] | Автокик ливнувших [Вкл]"
            )

    elif cmd in ["+приветствие", "+устправила", "+сбросстатистики", "+чсбота", "-чсбота", "+логчат", "-логчат", "+рассылка"]:
        req = 4 if cmd in ["+чсбота", "-чсбота", "+логчат", "-логчат", "+рассылка"] else 3
        if acc < req:
            return await m.answer(f"❌ Нужен {req}+ ур.")
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
            cursor.execute("UPDATE chat_settings SET welcome_text = ? WHERE chat_id = ?", (txt, cid))
            conn.commit()
            await m.answer("✅ Приветствие обновлено.")
        elif cmd == "+устправила":
            cursor.execute("UPDATE chat_settings SET rules_text = ? WHERE chat_id = ?", (txt, cid))
            conn.commit()
            await m.answer("✅ Правила обновлены.")
        elif cmd == "+рассылка":
            cursor.execute("SELECT chat_id FROM known_chats")
            chats = cursor.fetchall()
            s = 0
            for (pid,) in chats:
                try:
                    await bot.api.messages.send(peer_id=pid, message=f"📣 ОБЪЯВЛЕНИЕ\n────────────\n{txt}", random_id=0)
                    s += 1
                except Exception:
                    pass
            await m.answer(f"✅ Отправлено в {s} из {len(chats)} чатов.")

bot.loop_wrapper.add_task(expiration_worker())
bot.run()
