import sqlite3, re, time
from vkbottle.bot import Bot, Message

TOKEN = "vk1.a.nSVDeqVxBl5NwrIv-1FiT_lfVkQ5FTVcnVbgDjX7tNUIL-2uUQWxqUsyvZxkXB9expe5MeE51yCh6474-Wr2kaEfbJ09PJIBu6wL28VjeRKFsLFVrYu0GLFr5INSOcgps7tKxtAB-d2x_3s1xfH59TYTPcRz9bSX3PPcBfZgdWbOThKheFnUG72Xb9lM2T0YO0c_QBKJdQUOYILFq9tmQw"
OWNER_ID = 807140123

bot = Bot(token=TOKEN)
conn = sqlite3.connect("rp_manager_network.db")
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS known_chats (chat_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS global_staff (user_id INTEGER PRIMARY KEY, role_name TEXT DEFAULT 'Участник', access INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS users (chat_id INTEGER, user_id INTEGER, nickname TEXT DEFAULT 'Не установлен', role_name TEXT DEFAULT 'Участник', access INTEGER DEFAULT 0, warns INTEGER DEFAULT 0, preds INTEGER DEFAULT 0, mute_until INTEGER DEFAULT 0, msgs INTEGER DEFAULT 0, rep INTEGER DEFAULT 0, PRIMARY KEY (chat_id, user_id))")
cursor.execute("CREATE TABLE IF NOT EXISTS chat_settings (chat_id INTEGER PRIMARY KEY, silence INTEGER DEFAULT 0, welcome_text TEXT DEFAULT 'Добро пожаловать в беседу!', rules_text TEXT DEFAULT 'Правила не установлены.', anticaps INTEGER DEFAULT 0, antiflood INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS local_bans (chat_id INTEGER, user_id INTEGER, reason TEXT, PRIMARY KEY (chat_id, user_id))")
cursor.execute("CREATE TABLE IF NOT EXISTS global_bans (user_id INTEGER PRIMARY KEY, reason TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS user_notes (chat_id INTEGER, user_id INTEGER, author_id INTEGER, note_text TEXT, created_at INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS bot_blacklist (user_id INTEGER PRIMARY KEY, reason TEXT)")
cursor.execute("CREATE TABLE IF NOT EXISTS bot_config (key TEXT PRIMARY KEY, value TEXT)")

for q in ["ALTER TABLE users ADD COLUMN msgs INTEGER DEFAULT 0", "ALTER TABLE users ADD COLUMN rep INTEGER DEFAULT 0", "ALTER TABLE chat_settings ADD COLUMN rules_text TEXT DEFAULT 'Правила не установлены.'", "ALTER TABLE chat_settings ADD COLUMN anticaps INTEGER DEFAULT 0", "ALTER TABLE chat_settings ADD COLUMN antiflood INTEGER DEFAULT 0"]:
    try: cursor.execute(q)
    except Exception: pass
conn.commit()
last_msg_time = {}
def register_chat(cid: int):
    cursor.execute("INSERT OR IGNORE INTO known_chats (chat_id) VALUES (?)", (cid,))
    conn.commit()

def get_chat_settings(cid: int):
    register_chat(cid)
    cursor.execute("SELECT silence, welcome_text, rules_text, anticaps, antiflood FROM chat_settings WHERE chat_id = ?", (cid,))
    r = cursor.fetchone()
    if not r:
        cursor.execute("INSERT INTO chat_settings (chat_id) VALUES (?)", (cid,))
        conn.commit()
        return (0, "Добро пожаловать в беседу!", "Правила не установлены.", 0, 0)
    return r

def get_global(uid: int):
    if uid == OWNER_ID: return ("Основатель", 5)
    cursor.execute("SELECT role_name, access FROM global_staff WHERE user_id = ?", (uid,))
    r = cursor.fetchone()
    return r if r else ("Участник", 0)

def get_user(cid: int, uid: int):
    register_chat(cid)
    cursor.execute("SELECT nickname, role_name, access, warns, preds, mute_until, msgs, rep FROM users WHERE chat_id = ? AND user_id = ?", (cid, uid))
    r = cursor.fetchone()
    if not r:
        cursor.execute("INSERT INTO users (chat_id, user_id) VALUES (?, ?)", (cid, uid))
        conn.commit()
        nick, lr, la, w, p, m, ms, rep = ("Не установлен", "Участник", 0, 0, 0, 0, 0, 0)
    else: nick, lr, la, w, p, m, ms, rep = r
    gr, ga = get_global(uid)
    return (nick, f"{gr} [Глобал]", ga, w, p, m, ms, rep) if ga >= la and ga > 0 else (nick, lr, la, w, p, m, ms, rep)

async def send_log(text: str):
    cursor.execute("SELECT value FROM bot_config WHERE key = 'log_chat'")
    r = cursor.fetchone()
    if r and r[0]:
        try: await bot.api.messages.send(peer_id=int(r[0]), message=f"╔══ 📜 ЛОГ ══╗\n{text}\n╚════════════╝", random_id=0)
        except Exception: pass

def check_ban(cid: int, uid: int):
    cursor.execute("SELECT reason FROM global_bans WHERE user_id = ?", (uid,))
    gb = cursor.fetchone()
    if gb: return ("Глобальный бан", gb[0])
    cursor.execute("SELECT reason FROM local_bans WHERE chat_id = ? AND user_id = ?", (cid, uid))
    lb = cursor.fetchone()
    return ("Бан чата", lb[0]) if lb else None

def get_target(m: Message, args: list):
    if m.reply_message: return m.reply_message.from_id
    if len(args) > 1:
        match = re.search(r"\[id(\d+)\|", args[1])
        if match: return int(match.group(1))
        if args[1].isdigit(): return int(args[1])
    return None

def get_tail(m: Message, args: list, start: int = 2):
    return " ".join(args[1:]) if m.reply_message else " ".join(args[start:])
@bot.on.chat_message()
async def handler(m: Message):
    cid = m.peer_id
    register_chat(cid)
    if m.action and m.action.type.value == "chat_invite_user":
        uid = m.action.member_id
        if uid and uid > 0:
            ban = check_ban(cid, uid)
            if ban and uid != OWNER_ID:
                await m.answer(f"╔══ ⛔ ДОСТУП ЗАКРЫТ ══╗\n┃ Игрок: [id{uid}|участник]\n┃ Статус: {ban[0]} ({ban[1]})\n╚══════════════════════╝")
                try: await bot.api.messages.remove_chat_user(chat_id=m.chat_id, member_id=uid)
                except Exception: pass
                return
            get_user(cid, uid)
            _, w, _, _, _ = get_chat_settings(cid)
            await m.answer(f"╔══ 👋 ПРИВЕТСТВИЕ ══╗\n┃ Добро пожаловать, [id{uid}|игрок]!\n┃ {w}\n╚════════════════════╝")
        return

    if not m.text or m.from_id < 0: return
    if m.from_id != OWNER_ID and check_ban(cid, m.from_id):
        try: await bot.api.messages.remove_chat_user(chat_id=m.chat_id, member_id=m.from_id)
        except Exception: pass
        return

    args = m.text.strip().split()
    if not args: return
    cmd = args[0].lower()
    nick, role, acc, warns, preds, mute, msgs, rep = get_user(cid, m.from_id)
    sil, _, rules_text, acaps, aflood = get_chat_settings(cid)
    now = int(time.time())

    if acc < 1 and not cmd.startswith(("+", "/", "!", "-")):
        if mute > now or sil == 1:
            try: await bot.api.messages.delete(peer_id=cid, cmids=[m.conversation_message_id], delete_for_all=True)
            except Exception: pass
            return
        if aflood == 1:
            prev = last_msg_time.get((cid, m.from_id), 0)
            last_msg_time[(cid, m.from_id)] = time.time()
            if time.time() - prev < 1.5:
                try: await bot.api.messages.delete(peer_id=cid, cmids=[m.conversation_message_id], delete_for_all=True)
                except Exception: pass
                return
        if acaps == 1 and len(m.text) >= 8:
            let = [c for c in m.text if c.isalpha()]
            if let and sum(1 for c in let if c.isupper()) / len(let) > 0.75:
                try: await bot.api.messages.delete(peer_id=cid, cmids=[m.conversation_message_id], delete_for_all=True)
                except Exception: pass
                return

    cursor.execute("UPDATE users SET msgs = msgs + 1 WHERE chat_id = ? AND user_id = ?", (cid, m.from_id))
    conn.commit()
    if not cmd.startswith(("+", "/", "!", "-")): return
    if m.from_id != OWNER_ID:
        cursor.execute("SELECT 1 FROM bot_blacklist WHERE user_id = ?", (m.from_id,))
        if cursor.fetchone(): return

    if cmd in ["/help", "!помощь", "/помощь", "+помощь", "+команды"]:
        await m.answer(
            "╔══ 📋 КОМАНДЫ БОТА ══╗\n"
            "┃ 👤 [0+]: +стата, +топ, +правила, +реп/-реп, +ники, +состав, +гсостав\n"
            "┃ 🛡 [1+ Модер]: +ник, +снятьник, +найтиник, +мут/-мут, +мутлист, +пред/-пред, +преды, +выги, +заметка, +заметки\n"
            "┃ ⚔️ [2+ Админ]: +выг/-выг, +кик, +бан/-бан, +баны, +тишина, +антикапс, +антифлуд, +созыв, +очистить, +инфочат\n"
            "┃ 👑 [3+ ГА/ЗГА]: +гкик, +гбан/-гбан, +гбаны, +снятьвсе, +кикмолчунов, +приветствие, +устправила, +сбросстатистики, +чаты\n"
            "┃ 🎖 Ранги (ниже себя): +модер(1), +админ(2), +га/+зга(3), +спец(4), +снять | Глобал: +гмодер, +гадмин, +гга/+гзга, +гспец, +гснять\n"
            "┃ ⚡ [4+]: +рассылка, +логчат/-логчат, +чсбота/-чсбота\n"
            "╚═════════════════════╝"
        )
    elif cmd in ["+правила", "/rules"]:
        await m.answer(f"╔══ 📖 ПРАВИЛА ══╗\n{rules_text}\n╚════════════════╝")

    elif cmd in ["+стата", "+профиль", "/stats", "!стата"]:
        tid = get_target(m, args) or m.from_id
        tn, tr, ta, tw, tp, tm, tmsgs, trep = get_user(cid, tid)
        ms = f"Активен ({(tm - now) // 60 + 1} мин.)" if tm > now else "Нет"
        cursor.execute("SELECT COUNT(*) FROM user_notes WHERE chat_id = ? AND user_id = ?", (cid, tid))
        ncnt = cursor.fetchone()[0]
        await m.answer(f"╔══ 📊 ПРОФИЛЬ ══╗\n┃ 👤 [id{tid}|{tn}]\n┃ 🎖 {tr} ({ta} ур.) | ⭐ Реп: {trep}\n┃ 💬 Сообщений: {tmsgs + (1 if tid == m.from_id else 0)}\n┃ ⚠️ Выги: {tw}/3 | Преды: {tp}/2\n┃ 🗒 Досье: {ncnt} | 🔇 Мут: {ms}\n╚════════════════╝")

    elif cmd in ["+реп", "-реп"]:
        tid = get_target(m, args)
        if not tid or tid == m.from_id: return await m.answer("⚠️ Укажите другого игрока.")
        get_user(cid, tid)
        d = 1 if cmd == "+реп" else -1
        cursor.execute("UPDATE users SET rep = rep + ? WHERE chat_id = ? AND user_id = ?", (d, cid, tid))
        conn.commit()
        await m.answer(f"⭐ Репутация [id{tid}|игрока] изменена! Теперь: **{get_user(cid, tid)[7]}**")

    elif cmd in ["+топ", "/top", "!топ"]:
        cursor.execute("SELECT user_id, nickname, msgs, rep FROM users WHERE chat_id = ? AND msgs > 0 ORDER BY msgs DESC LIMIT 10", (cid,))
        rows = cursor.fetchall()
        if not rows: return await m.answer("📭 Статистика пуста.")
        lines = ["╔══ 🏆 ТОП АКТИВА ══╗"] + [f"┃ {i}. [id{u}|{n if n != 'Не установлен' else 'Игрок'}] — {c} сообщ. (⭐{r})" for i, (u, n, c, r) in enumerate(rows, 1)] + ["╚═══════════════════╝"]
        await m.answer("\n".join(lines))

    elif cmd in ["+заметка", "+заметки"]:
        if acc < 1: return await m.answer("❌ Нужен 1+ ур.")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите игрока.")
        if cmd == "+заметка":
            note = get_tail(m, args, 2)
            if not note: return await m.answer("⚠️ Введите текст заметки.")
            cursor.execute("INSERT INTO user_notes VALUES (?, ?, ?, ?, ?)", (cid, tid, m.from_id, note, now))
            conn.commit()
            return await m.answer(f"🗒 Заметка добавлена в досье [id{tid}|игрока].")
        cursor.execute("SELECT author_id, note_text FROM user_notes WHERE chat_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 10", (cid, tid))
        rows = cursor.fetchall()
        if not rows: return await m.answer("📭 Досье пусто.")
        await m.answer(f"╔══ 🗂 ДОСЬЕ [id{tid}|ИГРОКА] ══╗\n" + "\n".join([f"┃ • {t} (от [id{a}|адм])" for a, t in rows]) + "\n╚════════════════════════╝")

    elif cmd in ["+ники", "/nicks", "!ники", "+найтиник"]:
        if cmd == "+найтиник":
            if acc < 1: return await m.answer("❌ Нужен 1+ ур.")
            q = " ".join(args[1:]).strip()
            if not q: return await m.answer("⚠️ Укажите часть ника.")
            cursor.execute("SELECT user_id, nickname FROM users WHERE chat_id = ? AND nickname LIKE ?", (cid, f"%{q}%"))
            rows = cursor.fetchall()
            if not rows: return await m.answer("🔍 Ничего не найдено.")
            return await m.answer(f"╔══ 🔍 ПОИСК: {q} ══╗\n" + "\n".join([f"┃ • [id{u}|{n}]" for u, n in rows]) + "\n╚══════════════════╝")
        cursor.execute("SELECT user_id, nickname FROM users WHERE chat_id = ? AND nickname != 'Не установлен'", (cid,))
        rows = cursor.fetchall()
        if not rows: return await m.answer("📭 Ников пока нет.")
        await m.answer("╔══ 📝 СПИСОК НИКОВ ══╗\n" + "\n".join([f"┃ {i}. [id{u}|{n}] — {get_user(cid, u)[1]}" for i, (u, n) in enumerate(rows, 1)]) + "\n╚═════════════════════╝")
    elif cmd in ["+состав", "+админы", "+модеры", "+гсостав"]:
        if cmd == "+гсостав":
            cursor.execute("SELECT user_id, role_name, access FROM global_staff WHERE access >= 1 ORDER BY access DESC")
            res = [f"╔══ 🌐 ГЛОБАЛ СОСТАВ ══╗\n┃ [5 ур. | Основатель] — [id{OWNER_ID}|Создатель]"] + [f"┃ [{a} ур. | {r}] — [id{u}|Админ]" for u, r, a in cursor.fetchall() if u != OWNER_ID] + ["╚══════════════════════╝"]
            return await m.answer("\n".join(res))
        cursor.execute("SELECT user_id, nickname FROM users WHERE chat_id = ?", (cid,))
        st = [(get_user(cid, u)[2], f"┃ [{get_user(cid, u)[2]} ур. | {get_user(cid, u)[1]}] — [id{u}|{n if n != 'Не установлен' else 'Без ника'}]") for u, n in cursor.fetchall() if get_user(cid, u)[2] >= 1]
        if not st: return await m.answer("📭 Состав пуст.")
        st.sort(key=lambda x: x[0], reverse=True)
        await m.answer("╔══ 🛡 СОСТАВ ЧАТА ══╗\n" + "\n".join([x[1] for x in st]) + "\n╚════════════════════╝")

    elif cmd in ["+мутлист", "+преды", "+выги", "+баны", "+гбаны", "+чаты"]:
        if cmd == "+мутлист":
            if acc < 1: return await m.answer("❌ Нужен 1+ ур.")
            cursor.execute("SELECT user_id, nickname, mute_until FROM users WHERE chat_id = ? AND mute_until > ?", (cid, now))
            rows = cursor.fetchall()
            if not rows: return await m.answer("📭 Активных мутов нет.")
            return await m.answer("╔══ 🔇 МУТЫ ══╗\n" + "\n".join([f"┃ • [id{u}|{n}] — {(mu - now)//60 + 1} мин." for u, n, mu in rows]) + "\n╚═════════════╝")
        if cmd in ["+преды", "+выги"]:
            if acc < 1: return await m.answer("❌ Нужен 1+ ур.")
            cursor.execute("SELECT user_id, nickname, warns, preds FROM users WHERE chat_id = ? AND (warns > 0 OR preds > 0)", (cid,))
            rows = cursor.fetchall()
            if not rows: return await m.answer("📭 Нарушителей нет.")
            return await m.answer("╔══ ⚠️ НАРУШИТЕЛИ ══╗\n" + "\n".join([f"┃ • [id{u}|{n}] — Выги: {w}/3 | Преды: {p}/2" for u, n, w, p in rows]) + "\n╚═══════════════════╝")
        if cmd == "+баны":
            if acc < 2: return await m.answer("❌ Нужен 2+ ур.")
            cursor.execute("SELECT user_id, reason FROM local_bans WHERE chat_id = ?", (cid,))
            rows = cursor.fetchall()
            if not rows: return await m.answer("📭 Локальный бан-лист пуст.")
            return await m.answer("╔══ ⛔ БАНЫ ЧАТА ══╗\n" + "\n".join([f"┃ • [id{u}|Игрок] — {r}" for u, r in rows]) + "\n╚══════════════════╝")
        if cmd == "+гбаны":
            if acc < 3: return await m.answer("❌ Нужен 3+ ур.")
            cursor.execute("SELECT user_id, reason FROM global_bans")
            rows = cursor.fetchall()
            if not rows: return await m.answer("📭 Глобальный бан-лист пуст.")
            return await m.answer("╔══ ⛔ ГЛОБАЛ БАНЫ ══╗\n" + "\n".join([f"┃ • [id{u}|Игрок] — {r}" for u, r in rows]) + "\n╚════════════════════╝")
        if acc < 3: return await m.answer("❌ Нужен 3+ ур.")
        cursor.execute("SELECT COUNT(*) FROM known_chats")
        await m.answer(f"🌐 Бот активен в **{cursor.fetchone()[0]}** чатах.")

    elif cmd in ["+модер", "+админ", "+га", "+зга", "+спец", "+снять", "+гмодер", "+гадмин", "+гга", "+гзга", "+гспец", "+гснять"]:
        if acc < 2: return await m.answer("❌ Нужен 2+ ур.")
        tid = get_target(m, args)
        if not tid or tid == OWNER_ID or tid == m.from_id: return await m.answer("⚠️ Укажите корректного игрока.")
        is_glob = cmd.startswith("+г") and cmd not in ["+га", "+гснять"] or cmd == "+гснять"
        t_acc = get_global(tid)[1] if is_glob else get_user(cid, tid)[2]
        if t_acc >= acc and m.from_id != OWNER_ID: return await m.answer("❌ Нельзя изменить ранг равного или старшего.")
        rmap = {"модер": (1, "Модератор"), "админ": (2, "Администратор"), "га": (3, "ГА/ЗГА"), "зга": (3, "ГА/ЗГА"), "спец": (4, "Спец. адм"), "снять": (0, "Участник")}
        key = cmd[2:] if is_glob else cmd[1:]
        lvl, title = rmap[key]
        if lvl >= acc and m.from_id != OWNER_ID: return await m.answer("❌ Можно выдавать ранг только ниже своего.")
        if is_glob:
            cursor.execute("INSERT OR REPLACE INTO global_staff VALUES (?, ?, ?)", (tid, title, lvl))
            if lvl == 0: cursor.execute("UPDATE users SET access = 0, role_name = 'Участник' WHERE user_id = ?", (tid,))
        else:
            cursor.execute("UPDATE users SET access = ?, role_name = ? WHERE chat_id = ? AND user_id = ?", (lvl, title, cid, tid))
        conn.commit()
        await m.answer(f"🎖 Игроку [id{tid}|участнику] выдан {'глобальный ' if is_glob else ''}ранг: **{title}** ({lvl} ур.).")
        await send_log(f"┃ [id{m.from_id}|Админ] выдал ранг **{title}** ({lvl} ур.) игроку [id{tid}|участнику].")
    elif cmd in ["+бан", "-бан", "+гбан", "-гбан", "+гкик"]:
        req = 3 if cmd.startswith(("+г", "-г")) else 2
        if acc < req: return await m.answer(f"❌ Нужен {req}+ ур.")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите игрока.")
        if cmd == "-бан":
            cursor.execute("DELETE FROM local_bans WHERE chat_id = ? AND user_id = ?", (cid, tid))
            conn.commit()
            return await m.answer(f"✅ Локальный бан снят с [id{tid}|участника].")
        if cmd == "-гбан":
            cursor.execute("DELETE FROM global_bans WHERE user_id = ?", (tid,))
            conn.commit()
            return await m.answer(f"✅ Глобальный бан снят с [id{tid}|участника].")
        t_acc = get_global(tid)[1] if req == 3 else get_user(cid, tid)[2]
        if tid == OWNER_ID or (t_acc >= acc and m.from_id != OWNER_ID): return await m.answer("❌ Нельзя применить к этому админу.")
        reason = get_tail(m, args, 2) or "Не указана"
        if cmd == "+бан":
            cursor.execute("INSERT OR REPLACE INTO local_bans VALUES (?, ?, ?)", (cid, tid, reason))
            cursor.execute("UPDATE users SET access = 0, role_name = 'Участник' WHERE chat_id = ? AND user_id = ?", (cid, tid))
            conn.commit()
            await m.answer(f"⛔ [id{tid}|Игрок] забанен в чате. Причина: {reason}")
            try: await bot.api.messages.remove_chat_user(chat_id=m.chat_id, member_id=tid)
            except Exception: pass
        else:
            if cmd == "+гбан": cursor.execute("INSERT OR REPLACE INTO global_bans VALUES (?, ?)", (tid, reason))
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
                except Exception: pass
            await m.answer(f"⛔ Применён {cmd} к [id{tid}|игроку] ({k}/{len(chats)} чатов). Причина: {reason}")
        await send_log(f"┃ [id{m.from_id}|Админ] применил {cmd} к [id{tid}|игроку]. Причина: {reason}")

    elif cmd in ["+ник", "/snick", "+снятьник", "+мут", "-мут"]:
        if acc < 1: return await m.answer("❌ Нужен 1+ ур.")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите игрока.")
        get_user(cid, tid)
        if cmd == "+снятьник":
            cursor.execute("UPDATE users SET nickname = 'Не установлен' WHERE chat_id = ? AND user_id = ?", (cid, tid))
            conn.commit()
            return await m.answer(f"✅ Ник сброшен для [id{tid}|игрока].")
        if cmd in ["+ник", "/snick"]:
            nn = get_tail(m, args, 2)
            if not nn: return await m.answer("⚠️ Укажите ник.")
            cursor.execute("UPDATE users SET nickname = ? WHERE chat_id = ? AND user_id = ?", (nn, cid, tid))
            conn.commit()
            return await m.answer(f"✅ Ник установлен: **{nn}**")
        if cmd == "-мут":
            cursor.execute("UPDATE users SET mute_until = 0 WHERE chat_id = ? AND user_id = ?", (cid, tid))
            conn.commit()
            return await m.answer("🔊 Мут снят.")
        try:
            idx = 1 if m.reply_message else 2
            mins = int(args[idx])
            reason = " ".join(args[idx+1:]) or "Не указана"
        except Exception: return await m.answer("⚠️ Пример: +мут @user 30 Флуд")
        cursor.execute("UPDATE users SET mute_until = ? WHERE chat_id = ? AND user_id = ?", (now + mins * 60, cid, tid))
        conn.commit()
        await m.answer(f"🔇 [id{tid}|Игрок] в муте на **{mins} мин.** Причина: {reason}")
        await send_log(f"┃ [id{m.from_id}|Админ] выдал мут ({mins} мин.) [id{tid}|игроку].")
    elif cmd in ["+пред", "-пред", "+выг", "-выг", "/warn", "/unwarn", "+снятьвсе"]:
        req = 1 if cmd in ["+пред", "-пред"] else (3 if cmd == "+снятьвсе" else 2)
        if acc < req: return await m.answer(f"❌ Нужен {req}+ ур.")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите игрока.")
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
            if tp >= 2: tp, tw = 0, tw + 1
        else: tw += 1
        if tw >= 3:
            cursor.execute("UPDATE users SET warns = 0, preds = 0 WHERE chat_id = ? AND user_id = ?", (cid, tid))
            conn.commit()
            await m.answer(f"🚫 [id{tid}|{tn}] 3/3 выговоров и кик! Причина: {reason}")
            try: await bot.api.messages.remove_chat_user(chat_id=m.chat_id, member_id=tid)
            except Exception: pass
        else:
            cursor.execute("UPDATE users SET warns = ?, preds = ? WHERE chat_id = ? AND user_id = ?", (tw, tp, cid, tid))
            conn.commit()
            await m.answer(f"⚠️ [id{tid}|{tn}] Выги: {tw}/3 | Преды: {tp}/2. Причина: {reason}")
        await send_log(f"┃ [id{m.from_id}|Админ] выдал {cmd} [id{tid}|игроку] ({tw}/3, {tp}/2).")

    elif cmd in ["+кик", "/kick", "+кикмолчунов", "+тишина", "+антикапс", "+антифлуд", "+созыв", "+очистить", "+инфочат"]:
        req = 3 if cmd == "+кикмолчунов" else 2
        if acc < req: return await m.answer(f"❌ Нужен {req}+ ур.")
        if cmd in ["+кик", "/kick"]:
            tid = get_target(m, args)
            if not tid: return await m.answer("⚠️ Укажите игрока.")
            reason = get_tail(m, args, 2) or "Не указана"
            await m.answer(f"👢 [id{tid}|Игрок] исключён. Причина: {reason}")
            try: await bot.api.messages.remove_chat_user(chat_id=m.chat_id, member_id=tid)
            except Exception: pass
        elif cmd == "+кикмолчунов":
            mem = await bot.api.messages.get_conversation_members(peer_id=cid)
            k = 0
            for i in mem.items:
                if i.member_id > 0 and i.member_id != OWNER_ID and get_user(cid, i.member_id)[2] == 0 and get_user(cid, i.member_id)[6] == 0:
                    try:
                        await bot.api.messages.remove_chat_user(chat_id=m.chat_id, member_id=i.member_id)
                        k += 1
                    except Exception: pass
            await m.answer(f"🧹 Исключено молчунов: **{k}**.")
        elif cmd in ["+тишина", "+антикапс", "+антифлуд"]:
            col = {"+тишина": ("silence", sil), "+антикапс": ("anticaps", acaps), "+антифлуд": ("antiflood", aflood)}[cmd]
            nv = 0 if col[1] == 1 else 1
            cursor.execute(f"UPDATE chat_settings SET {col[0]} = ? WHERE chat_id = ?", (nv, cid))
            conn.commit()
            await m.answer(f"⚙️ Режим **{cmd[1:]}**: {'Включён ✅' if nv == 1 else 'Выключен ❌'}")
        elif cmd == "+созыв":
            mem = await bot.api.messages.get_conversation_members(peer_id=cid)
            tags = [f"[id{i.member_id}|•]" for i in mem.items if i.member_id > 0]
            await m.answer(f"📢 **Внимание!** {' '.join(args[1:]) or 'Общий сбор!'}\n" + "".join(tags))
        elif cmd == "+очистить":
            await m.answer("🧹 **Чат очищен.**\n" + "\n" * 25 + "✨ Продолжаем общение!")
        elif cmd == "+инфочат":
            cursor.execute("SELECT COUNT(*) FROM users WHERE chat_id = ?", (cid,))
            u_c = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM local_bans WHERE chat_id = ?", (cid,))
            b_c = cursor.fetchone()[0]
            await m.answer(f"╔══ ℹ️ ПАСПОРТ ЧАТА ══╗\n┃ ID: `{cid}` | Игроков: {u_c} | Банов: {b_c}\n┃ Тишина: {sil} | Капс: {acaps} | Флуд: {aflood}\n╚════════════════════╝")

    elif cmd in ["+приветствие", "+устправила", "+сбросстатистики", "+чсбота", "-чсбота", "+логчат", "-логчат", "+рассылка"]:
        req = 4 if cmd in ["+чсбота", "-чсбота", "+логчат", "-логчат", "+рассылка"] else 3
        if acc < req: return await m.answer(f"❌ Нужен {req}+ ур.")
        if cmd == "+сбросстатистики":
            cursor.execute("UPDATE users SET msgs = 0 WHERE chat_id = ?", (cid,))
            conn.commit()
            return await m.answer("🔄 Счётчики сообщений в чате обнулены.")
        if cmd in ["+логчат", "-логчат"]:
            if cmd == "-логчат": cursor.execute("DELETE FROM bot_config WHERE key = 'log_chat'")
            else: cursor.execute("INSERT OR REPLACE INTO bot_config VALUES ('log_chat', ?)", (str(cid),))
            conn.commit()
            return await m.answer("📜 Чат логов обновлён.")
        if cmd in ["+чсбота", "-чсбота"]:
            tid = get_target(m, args)
            if not tid or tid == OWNER_ID: return await m.answer("⚠️ Укажите игрока.")
            if cmd == "-чсбота": cursor.execute("DELETE FROM bot_blacklist WHERE user_id = ?", (tid,))
            else: cursor.execute("INSERT OR REPLACE INTO bot_blacklist VALUES (?, ?)", (tid, "ЧС бота"))
            conn.commit()
            return await m.answer(f"🚫 ЧС бота обновлён для [id{tid}|игрока].")
        txt = " ".join(args[1:])
        if not txt: return await m.answer("⚠️ Введите текст.")
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
                    await bot.api.messages.send(peer_id=pid, message=f"╔══ 📣 ОБЪЯВЛЕНИЕ ══╗\n{txt}\n╚═══════════════════╝", random_id=0)
                    s += 1
                except Exception: pass
            await m.answer(f"✅ Отправлено в **{s}** из {len(chats)} чатов.")

bot.run()
