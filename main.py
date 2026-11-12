import sqlite3, re, time
from vkbottle.bot import Bot, Message

TOKEN = "vk1.a.nSVDeqVxBl5NwrIv-1FiT_lfVkQ5FTVcnVbgDjX7tNUIL-2uUQWxqUsyvZxkXB9expe5MeE51yCh6474-Wr2kaEfbJ09PJIBu6wL28VjeRKFsLFVrYu0GLFr5INSOcgps7tKxtAB-d2x_3s1xfH59TYTPcRz9bSX3PPcBfZgdWbOThKheFnUG72Xb9lM2T0YO0c_QBKJdQUOYILFq9tmQw"
OWNER_ID = 807140123

bot = Bot(token=TOKEN)
conn = sqlite3.connect("rp_manager_network.db")
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS known_chats (chat_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS global_staff (user_id INTEGER PRIMARY KEY, role_name TEXT DEFAULT 'Участник', access INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS users (chat_id INTEGER, user_id INTEGER, nickname TEXT DEFAULT 'Не установлен', role_name TEXT DEFAULT 'Участник', access INTEGER DEFAULT 0, warns INTEGER DEFAULT 0, preds INTEGER DEFAULT 0, mute_until INTEGER DEFAULT 0, msgs INTEGER DEFAULT 0, PRIMARY KEY (chat_id, user_id))")
cursor.execute("CREATE TABLE IF NOT EXISTS chat_settings (chat_id INTEGER PRIMARY KEY, silence INTEGER DEFAULT 0, welcome_text TEXT DEFAULT 'Добро пожаловать в беседу!')")
cursor.execute("CREATE TABLE IF NOT EXISTS local_bans (chat_id INTEGER, user_id INTEGER, reason TEXT, PRIMARY KEY (chat_id, user_id))")
cursor.execute("CREATE TABLE IF NOT EXISTS global_bans (user_id INTEGER PRIMARY KEY, reason TEXT)")
try:
    cursor.execute("ALTER TABLE users ADD COLUMN msgs INTEGER DEFAULT 0")
except Exception:
    pass
conn.commit()

def register_chat(cid: int):
    cursor.execute("INSERT OR IGNORE INTO known_chats (chat_id) VALUES (?)", (cid,))
    conn.commit()

def get_chat_settings(cid: int):
    register_chat(cid)
    cursor.execute("SELECT silence, welcome_text FROM chat_settings WHERE chat_id = ?", (cid,))
    r = cursor.fetchone()
    if not r:
        cursor.execute("INSERT INTO chat_settings (chat_id) VALUES (?)", (cid,))
        conn.commit()
        return (0, "Добро пожаловать в беседу!")
    return r

def get_global(uid: int):
    if uid == OWNER_ID: return ("Основатель", 5)
    cursor.execute("SELECT role_name, access FROM global_staff WHERE user_id = ?", (uid,))
    r = cursor.fetchone()
    return r if r else ("Участник", 0)

def get_user(cid: int, uid: int):
    register_chat(cid)
    cursor.execute("SELECT nickname, role_name, access, warns, preds, mute_until, msgs FROM users WHERE chat_id = ? AND user_id = ?", (cid, uid))
    r = cursor.fetchone()
    if not r:
        cursor.execute("INSERT INTO users (chat_id, user_id) VALUES (?, ?)", (cid, uid))
        conn.commit()
        nick, l_role, l_acc, warns, preds, mute, msgs = ("Не установлен", "Участник", 0, 0, 0, 0, 0)
    else:
        nick, l_role, l_acc, warns, preds, mute, msgs = r
    g_role, g_acc = get_global(uid)
    if g_acc >= l_acc and g_acc > 0:
        return (nick, f"{g_role} [Глобал]", g_acc, warns, preds, mute, msgs)
def check_ban(cid: int, uid: int):
    cursor.execute("SELECT reason FROM global_bans WHERE user_id = ?", (uid,))
    gb = cursor.fetchone()
    if gb: return ("Глобальный бан", gb[0])
    cursor.execute("SELECT reason FROM local_bans WHERE chat_id = ? AND user_id = ?", (cid, uid))
    lb = cursor.fetchone()
    if lb: return ("Бан чата", lb[0])
    return None

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
            ban_info = check_ban(cid, uid)
            if ban_info and uid != OWNER_ID:
                btype, breason = ban_info
                await m.answer(f"╭── ⛔ ДОСТУП ЗАКРЫТ ──╮\n• Игрок: [id{uid}|участник]\n• Статус: {btype}\n• Причина: {breason}\n╰────────────────────╯")
                try: await bot.api.messages.remove_chat_user(chat_id=m.chat_id, user_id=uid)
                except Exception: pass
                return
            get_user(cid, uid)
            _, w = get_chat_settings(cid)
            await m.answer(f"╭── 👋 НОВЫЙ УЧАСТНИК ──╮\nПриветствуем, [id{uid}|игрок]!\n{w}\n╰─────────────────────╯")
        return

    if not m.text or m.from_id < 0: return

    if m.from_id != OWNER_ID:
        ban_info = check_ban(cid, m.from_id)
        if ban_info:
            try: await bot.api.messages.remove_chat_user(chat_id=m.chat_id, user_id=m.from_id)
            except Exception: pass
            return

    args = m.text.strip().split()
    cmd = args[0].lower()
    nick, role, acc, warns, preds, mute, msgs = get_user(cid, m.from_id)
    sil, _ = get_chat_settings(cid)

    cursor.execute("UPDATE users SET msgs = msgs + 1 WHERE chat_id = ? AND user_id = ?", (cid, m.from_id))
    conn.commit()
    return (nick, l_role, l_acc, warns, preds, mute, msgs)
    if not cmd.startswith(("+", "/", "!", "-")):
        if (mute > int(time.time()) or sil == 1) and acc < 1:
            try: await bot.api.messages.delete(peer_id=cid, cmids=[m.conversation_message_id], delete_for_all=True)
            except Exception: pass
        return

    if cmd in ["/help", "!помощь", "/помощь", "+помощь", "+команды"]:
        await m.answer(
            "╭── 📋 МЕНЮ КОМАНД ──╮\n"
            "👤 Общие:\n"
            "• +стата [@user] | +топ | +ники\n"
            "• +состав | +гсостав\n\n"
            "🛡 [1 ур. Модератор]:\n"
            "• +ник | +мут / -мут | +пред / -пред\n\n"
            "⚔️ [2 ур. Администратор]:\n"
            "• +выг / -выг | +кик | +бан / -бан | +баны\n"
            "• +тишина | +созыв | +очистить\n\n"
            "👑 [3 ур. ГА/ЗГА]:\n"
            "• +гкик | +гбан / -гбан | +гбаны\n"
            "• +снятьвсе | +приветствие | +чаты\n\n"
            "🎖 Ранги (строго ниже своего):\n"
            "• +модер (1) | +админ (2) | +га/+зга (3) | +спец (4) | +снять\n"
            "• Глобал: +гмодер, +гадмин, +гга/+гзга, +гспец, +гснять\n"
            "• +рассылка [текст] (4+ ур.)\n"
            "╰────────────────────╯"
        )

    elif cmd in ["+стата", "+профиль", "/stats", "!стата"]:
        tid = get_target(m, args) or m.from_id
        tn, tr, ta, tw, tp, tm, tmsgs = get_user(cid, tid)
        now = int(time.time())
        ms = f"Активен ({(tm - now) // 60 + 1} мин.)" if tm > now else "Нет"
        await m.answer(
            f"╭── 📊 ПРОФИЛЬ ИГРОКА ──╮\n"
            f"• Игрок: [id{tid}|{tn if tn != 'Не установлен' else 'Участник'}]\n"
            f"• Ник: {tn}\n"
            f"• Ранг: {tr} ({ta} ур.)\n"
            f"• Сообщений: {tmsgs + (1 if tid == m.from_id else 0)}\n"
            f"• Выговоры: {tw}/3 | Преды: {tp}/2\n"
            f"• Мут: {ms}\n"
            f"╰───────────────────────╯"
        )

    elif cmd in ["+топ", "/top", "!топ"]:
        cursor.execute("SELECT user_id, nickname, msgs FROM users WHERE chat_id = ? AND msgs > 0 ORDER BY msgs DESC LIMIT 10", (cid,))
        rows = cursor.fetchall()
        if not rows: return await m.answer("📭 Статистика сообщений пока пуста.")
        medals = ["🥇", "🥈", "🥉"]
        lines = ["╭── 🏆 ТОП АКТИВА ЧАТА ──╮"]
        for i, (u, n, cnt) in enumerate(rows, 1):
            ico = medals[i - 1] if i <= 3 else f"{i}."
            name = n if n != "Не установлен" else "Участник"
            lines.append(f"{ico} [id{u}|{name}] — {cnt} сообщ.")
        lines.append("╰───────────────────────╯")
        await m.answer("\n".join(lines))
    elif cmd in ["+ники", "/nicks", "!ники"]:
        cursor.execute("SELECT user_id, nickname FROM users WHERE chat_id = ? AND nickname != 'Не установлен'", (cid,))
        rows = cursor.fetchall()
        if not rows: return await m.answer("📭 Ников в этом чате пока нет.")
        res = ["╭── 📝 СПИСОК НИКОВ ──╮"]
        for i, (u, n) in enumerate(rows, 1):
            res.append(f"{i}. [id{u}|{n}] — {get_user(cid, u)[1]}")
        res.append("╰─────────────────────╯")
        await m.answer("\n".join(res))

    elif cmd in ["+состав", "+админы", "+модеры"]:
        cursor.execute("SELECT user_id, nickname FROM users WHERE chat_id = ?", (cid,))
        st = []
        for u, n in cursor.fetchall():
            _, r, a, _, _, _, _ = get_user(cid, u)
            if a >= 1:
                st.append((a, f"• [{a} ур. | {r}] — [id{u}|{n if n != 'Не установлен' else 'Без ника'}]"))
        if not st: return await m.answer("📭 Состав администрации пуст.")
        st.sort(key=lambda x: x[0], reverse=True)
        await m.answer("╭── 🛡 СОСТАВ ЧАТА ──╮\n" + "\n".join([x[1] for x in st]) + "\n╰────────────────────╯")

    elif cmd == "+гсостав":
        cursor.execute("SELECT user_id, role_name, access FROM global_staff WHERE access >= 1 ORDER BY access DESC")
        res = [f"╭── 🌐 ГЛОБАЛЬНЫЙ СОСТАВ ──╮\n• [5 ур. | Основатель] — [id{OWNER_ID}|Создатель]"]
        for u, r, a in cursor.fetchall():
            if u != OWNER_ID:
                res.append(f"• [{a} ур. | {r}] — [id{u}|Админ]")
        res.append("╰─────────────────────────╯")
        await m.answer("\n".join(res))

    elif cmd == "+баны":
        if acc < 2: return await m.answer("❌ Нужен 2+ ур. (Админ).")
        cursor.execute("SELECT user_id, reason FROM local_bans WHERE chat_id = ?", (cid,))
        rows = cursor.fetchall()
        if not rows: return await m.answer("📭 Локальный бан-лист пуст.")
        res = ["╭── ⛔ БАН-ЛИСТ ЧАТА ──╮"] + [f"• [id{u}|Игрок] — {r}" for u, r in rows] + ["╰──────────────────────╯"]
        await m.answer("\n".join(res))

    elif cmd == "+гбаны":
        if acc < 3: return await m.answer("❌ Нужен 3+ ур. (ГА/ЗГА).")
        cursor.execute("SELECT user_id, reason FROM global_bans")
        rows = cursor.fetchall()
        if not rows: return await m.answer("📭 Глобальный бан-лист пуст.")
        res = ["╭── ⛔ ГЛОБАЛЬНЫЙ БАН-ЛИСТ ──╮"] + [f"• [id{u}|Игрок] — {r}" for u, r in rows] + ["╰───────────────────────────╯"]
        await m.answer("\n".join(res))

    elif cmd == "+чаты":
        if acc < 3: return await m.answer("❌ Нужен 3+ ур. (ГА/ЗГА).")
        cursor.execute("SELECT COUNT(*) FROM known_chats")
        await m.answer(f"🌐 Бот активен в **{cursor.fetchone()[0]}** чатах.")
    elif cmd in ["+модер", "+админ", "+га", "+зга", "+спец", "+снять"]:
        if acc < 2: return await m.answer("❌ Нужен 2+ ур. (Админ) для выдачи должностей.")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        if tid == OWNER_ID or tid == m.from_id: return await m.answer("❌ Нельзя изменить ранг себе или Основателю.")
        _, _, t_acc, _, _, _, _ = get_user(cid, tid)
        if t_acc >= acc and m.from_id != OWNER_ID:
            return await m.answer("❌ Нельзя изменить ранг пользователю вашего уровня или выше.")
        roles = {"+модер": (1, "Модератор"), "+админ": (2, "Администратор"), "+га": (3, "ГА/ЗГА"), "+зга": (3, "ГА/ЗГА"), "+спец": (4, "Спец. адм"), "+снять": (0, "Участник")}
        lvl, title = roles[cmd]
        if lvl >= acc and m.from_id != OWNER_ID:
            return await m.answer("❌ Вы можете выдавать должности только ниже своего уровня.")
        cursor.execute("UPDATE users SET access = ?, role_name = ? WHERE chat_id = ? AND user_id = ?", (lvl, title, cid, tid))
        conn.commit()
        await m.answer(f"╭── 🎖 НАЗНАЧЕНИЕ ──╮\n• Игрок: [id{tid}|участник]\n• Новый ранг: **{title}** ({lvl} ур.)\n╰───────────────────╯")

    elif cmd in ["+гмодер", "+гадмин", "+гга", "+гзга", "+гспец", "+гснять"]:
        if acc < 2: return await m.answer("❌ Нужен 2+ ур. (Админ) для выдачи глобальных должностей.")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        if tid == OWNER_ID or tid == m.from_id: return await m.answer("⚠️ Нельзя изменить ранг себе или Основателю.")
        _, t_acc = get_global(tid)
        if t_acc >= acc and m.from_id != OWNER_ID:
            return await m.answer("❌ Нельзя изменить глобальный ранг пользователю вашего уровня или выше.")
        roles = {"+гмодер": (1, "Модератор"), "+гадмин": (2, "Администратор"), "+гга": (3, "ГА/ЗГА"), "+гзга": (3, "ГА/ЗГА"), "+гспец": (4, "Спец. адм"), "+гснять": (0, "Участник")}
        lvl, title = roles[cmd]
        if lvl >= acc and m.from_id != OWNER_ID:
            return await m.answer("❌ Вы можете выдавать глобальные должности только ниже своего уровня.")
        cursor.execute("INSERT OR REPLACE INTO global_staff (user_id, role_name, access) VALUES (?, ?, ?)", (tid, title, lvl))
        if lvl == 0: cursor.execute("UPDATE users SET access = 0, role_name = 'Участник' WHERE user_id = ?", (tid,))
        conn.commit()
        cursor.execute("SELECT COUNT(*) FROM known_chats")
        cnt = cursor.fetchone()[0]
        await m.answer(f"╭── 🌐 ГЛОБАЛ РАНГ ──╮\n• Игрок: [id{tid}|участник]\n• Ранг: **{title}** ({lvl} ур.)\n• Охват: все **{cnt}** чатов\n╰────────────────────╯")

    elif cmd == "+бан":
        if acc < 2: return await m.answer("❌ Нужен 2+ ур. (Админ).")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        _, _, t_acc, _, _, _, _ = get_user(cid, tid)
        if tid == OWNER_ID or (t_acc >= acc and m.from_id != OWNER_ID):
            return await m.answer("❌ Нельзя забанить этого администратора.")
        reason = get_tail(m, args, 2) or "Не указана"
        cursor.execute("INSERT OR REPLACE INTO local_bans (chat_id, user_id, reason) VALUES (?, ?, ?)", (cid, tid, reason))
        cursor.execute("UPDATE users SET access = 0, role_name = 'Участник' WHERE chat_id = ? AND user_id = ?", (cid, tid))
        conn.commit()
        await m.answer(f"╭── ⛔ БАН ЧАТА ──╮\n• Игрок: [id{tid}|участник]\n• Причина: {reason}\n╰─────────────────╯")
        try: await bot.api.messages.remove_chat_user(chat_id=m.chat_id, user_id=tid)
        except Exception: await m.answer("⚠️ Занесён в бан-лист, но у бота нет прав админа для кика.")

    elif cmd == "-бан":
        if acc < 2: return await m.answer("❌ Нужен 2+ ур. (Админ).")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        cursor.execute("DELETE FROM local_bans WHERE chat_id = ? AND user_id = ?", (cid, tid))
        conn.commit()
        await m.answer(f"✅ Локальный бан снят с [id{tid}|участника].")

    elif cmd in ["+гбан", "-гбан", "+гкик"]:
        if acc < 3: return await m.answer("❌ Нужен 3+ ур. (ГА/ЗГА).")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        if cmd == "-гбан":
            cursor.execute("DELETE FROM global_bans WHERE user_id = ?", (tid,))
            conn.commit()
            return await m.answer(f"✅ Глобальный бан снят с [id{tid}|участника].")
        if tid == OWNER_ID or (get_global(tid)[1] >= acc and m.from_id != OWNER_ID):
            return await m.answer("❌ Нельзя применить к этому администратору.")
        reason = get_tail(m, args, 2) or "Не указана"
        if cmd == "+гбан":
            cursor.execute("INSERT OR REPLACE INTO global_bans (user_id, reason) VALUES (?, ?)", (tid, reason))
        cursor.execute("DELETE FROM global_staff WHERE user_id = ?", (tid,))
        cursor.execute("UPDATE users SET access = 0, role_name = 'Участник' WHERE user_id = ?", (tid,))
        conn.commit()
        cursor.execute("SELECT chat_id FROM known_chats")
        chats = cursor.fetchall()
        kicked = 0
        for (pid,) in chats:
            try:
                await bot.api.messages.remove_chat_user(chat_id=pid - 2000000000, user_id=tid)
                kicked += 1
            except Exception: pass
        title_box = "⛔ ГЛОБАЛЬНЫЙ БАН" if cmd == "+гбан" else "🚫 ГЛОБАЛЬНЫЙ КИК"
        await m.answer(f"╭── {title_box} ──╮\n• Игрок: [id{tid}|участник]\n• Исключён из: **{kicked}** из {len(chats)} чатов\n• Причина: {reason}\n╰───────────────────────╯")
    elif cmd in ["+ник", "/snick"]:
        if acc < 1: return await m.answer("❌ Нужен 1+ ур. (Модер).")
        tid = get_target(m, args)
        nn = get_tail(m, args, 2)
        if not tid or not nn: return await m.answer("⚠️ Пример: +ник @user Ivan_Ivanov")
        get_user(cid, tid)
        cursor.execute("UPDATE users SET nickname = ? WHERE chat_id = ? AND user_id = ?", (nn, cid, tid))
        conn.commit()
        await m.answer(f"✅ Установлен ник: **{nn}**")

    elif cmd in ["+мут", "-мут"]:
        if acc < 1: return await m.answer("❌ Нужен 1+ ур. (Модер).")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        if cmd == "-мут":
            cursor.execute("UPDATE users SET mute_until = 0 WHERE chat_id = ? AND user_id = ?", (cid, tid))
            conn.commit()
            return await m.answer("🔊 Мут снят.")
        try:
            idx = 1 if m.reply_message else 2
            mins = int(args[idx])
            reason = " ".join(args[idx+1:]) or "Не указана"
        except Exception: return await m.answer("⚠️ Пример: +мут @user 30 Флуд")
        cursor.execute("UPDATE users SET mute_until = ? WHERE chat_id = ? AND user_id = ?", (int(time.time()) + mins * 60, cid, tid))
        conn.commit()
        await m.answer(f"🔇 [id{tid}|Участник] получил мут на **{mins} мин.**\n• Причина: {reason}")

    elif cmd in ["+пред", "-пред"]:
        if acc < 1: return await m.answer("❌ Нужен 1+ ур. (Модер).")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        tn, _, _, tw, tp, _, _ = get_user(cid, tid)
        if cmd == "-пред":
            if tp > 0:
                cursor.execute("UPDATE users SET preds = ? WHERE chat_id = ? AND user_id = ?", (tp - 1, cid, tid))
                conn.commit()
                return await m.answer(f"✅ Пред снят ({tp - 1}/2).")
            return await m.answer("ℹ️ Предов нет.")
        reason = get_tail(m, args, 2) or "Не указана"
        tp += 1
        if tp >= 2:
            tp, tw = 0, tw + 1
            if tw >= 3:
                cursor.execute("UPDATE users SET warns = 0, preds = 0 WHERE chat_id = ? AND user_id = ?", (cid, tid))
                conn.commit()
                await m.answer(f"🚫 [id{tid}|{tn}] 2/2 преда → 3/3 выговоров и кик!\n• Причина: {reason}")
                try: await bot.api.messages.remove_chat_user(chat_id=m.chat_id, user_id=tid)
                except Exception: pass
            else:
                cursor.execute("UPDATE users SET warns = ?, preds = 0 WHERE chat_id = ? AND user_id = ?", (tw, cid, tid))
                conn.commit()
                await m.answer(f"⚠️ [id{tid}|{tn}] 2/2 преда → выговор ({tw}/3)!\n• Причина: {reason}")
        else:
            cursor.execute("UPDATE users SET preds = ? WHERE chat_id = ? AND user_id = ?", (tp, cid, tid))
            conn.commit()
            await m.answer(f"🔸 [id{tid}|{tn}] получил пред ({tp}/2).\n• Причина: {reason}")

    elif cmd in ["+выг", "-выг", "/warn", "/unwarn"]:
        if acc < 2: return await m.answer("❌ Нужен 2+ ур. (Админ).")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        tn, _, _, tw, _, _, _ = get_user(cid, tid)
        if cmd in ["-выг", "/unwarn"]:
            if tw > 0:
                cursor.execute("UPDATE users SET warns = ? WHERE chat_id = ? AND user_id = ?", (tw - 1, cid, tid))
                conn.commit()
                return await m.answer(f"✅ Выговор снят ({tw - 1}/3).")
            return await m.answer("ℹ️ Выговоров нет.")
        reason = get_tail(m, args, 2) or "Не указана"
        tw += 1
        if tw >= 3:
            cursor.execute("UPDATE users SET warns = 0 WHERE chat_id = ? AND user_id = ?", (cid, tid))
            conn.commit()
            await m.answer(f"🚫 [id{tid}|{tn}] получил 3/3 выговоров и исключён!\n• Причина: {reason}")
            try: await bot.api.messages.remove_chat_user(chat_id=m.chat_id, user_id=tid)
            except Exception: pass
        else:
            cursor.execute("UPDATE users SET warns = ? WHERE chat_id = ? AND user_id = ?", (tw, cid, tid))
            conn.commit()
            await m.answer(f"⚠️ [id{tid}|{tn}] получил выговор ({tw}/3).\n• Причина: {reason}")

    elif cmd == "+снятьвсе":
        if acc < 3: return await m.answer("❌ Нужен 3+ ур. (ГА/ЗГА).")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        cursor.execute("UPDATE users SET warns = 0, preds = 0, mute_until = 0 WHERE chat_id = ? AND user_id = ?", (cid, tid))
        conn.commit()
        await m.answer(f"✨ Все выговоры, преды и мут сняты с [id{tid}|участника].")

    elif cmd in ["+кик", "/kick"]:
        if acc < 2: return await m.answer("❌ Нужен 2+ ур. (Админ).")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        reason = get_tail(m, args, 2) or "Не указана"
        await m.answer(f"👢 [id{tid}|Участник] исключён.\n• Причина: {reason}")
        try: await bot.api.messages.remove_chat_user(chat_id=m.chat_id, user_id=tid)
        except Exception: await m.answer("⚠️ Нет прав администратора.")

    elif cmd == "+тишина":
        if acc < 2: return await m.answer("❌ Нужен 2+ ур. (Админ).")
        ns = 0 if sil == 1 else 1
        cursor.execute("UPDATE chat_settings SET silence = ? WHERE chat_id = ?", (ns, cid))
        conn.commit()
        await m.answer("🔇 **Режим тишины включён!**" if ns == 1 else "🔊 **Режим тишины выключен!**")

    elif cmd == "+созыв":
        if acc < 2: return await m.answer("❌ Нужен 2+ ур. (Админ).")
        text = " ".join(args[1:]) or "Общий сбор!"
        try:
            mem = await bot.api.messages.get_conversation_members(peer_id=cid)
            tags = [f"[id{i.member_id}|•]" for i in mem.items if i.member_id > 0]
            await m.answer(f"📢 **Внимание!** {text}\n" + "".join(tags))
        except Exception: await m.answer("⚠️ Нет прав администратора.")

    elif cmd == "+очистить":
        if acc < 2: return await m.answer("❌ Нужен 2+ ур. (Админ).")
        await m.answer("🧹 **Чат очищен администратором.**\n" + "\n" * 25 + "✨ Продолжаем общение!")

    elif cmd == "+приветствие":
        if acc < 3: return await m.answer("❌ Нужен 3+ ур. (ГА/ЗГА).")
        text = " ".join(args[1:])
        if not text: return await m.answer("⚠️ Введите текст приветствия.")
        cursor.execute("UPDATE chat_settings SET welcome_text = ? WHERE chat_id = ?", (text, cid))
        conn.commit()
        await m.answer(f"✅ Приветствие сохранено:\n«{text}»")

    elif cmd == "+рассылка":
        if acc < 4: return await m.answer("❌ Нужен 4+ ур. (Спец. адм / Основатель).")
        text = " ".join(args[1:])
        if not text: return await m.answer("⚠️ Укажите текст рассылки.")
        cursor.execute("SELECT chat_id FROM known_chats")
        chats = cursor.fetchall()
        sent = 0
        for (pid,) in chats:
            try:
                await bot.api.messages.send(peer_id=pid, message=f"╭── 📣 ОБЪЯВЛЕНИЕ СЕТИ ──╮\n{text}\n╰────────────────────────╯", random_id=0)
                sent += 1
            except Exception: pass
        await m.answer(f"✅ Рассылка отправлена в **{sent}** из {len(chats)} чатов.")

bot.run()
