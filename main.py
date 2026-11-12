import sqlite3, re, time
from vkbottle.bot import Bot, Message

TOKEN = "vk1.a.nSVDeqVxBl5NwrIv-1FiT_lfVkQ5FTVcnVbgDjX7tNUIL-2uUQWxqUsyvZxkXB9expe5MeE51yCh6474-Wr2kaEfbJ09PJIBu6wL28VjeRKFsLFVrYu0GLFr5INSOcgps7tKxtAB-d2x_3s1xfH59TYTPcRz9bSX3PPcBfZgdWbOThKheFnUG72Xb9lM2T0YO0c_QBKJdQUOYILFq9tmQw"
OWNER_ID = 807140123

bot = Bot(token=TOKEN)
conn = sqlite3.connect("rp_manager_network.db")
cursor = conn.cursor()

cursor.execute("CREATE TABLE IF NOT EXISTS known_chats (chat_id INTEGER PRIMARY KEY)")
cursor.execute("CREATE TABLE IF NOT EXISTS global_staff (user_id INTEGER PRIMARY KEY, role_name TEXT DEFAULT 'Участник', access INTEGER DEFAULT 0)")
cursor.execute("CREATE TABLE IF NOT EXISTS users (chat_id INTEGER, user_id INTEGER, nickname TEXT DEFAULT 'Не установлен', role_name TEXT DEFAULT 'Участник', access INTEGER DEFAULT 0, warns INTEGER DEFAULT 0, preds INTEGER DEFAULT 0, mute_until INTEGER DEFAULT 0, PRIMARY KEY (chat_id, user_id))")
cursor.execute("CREATE TABLE IF NOT EXISTS chat_settings (chat_id INTEGER PRIMARY KEY, silence INTEGER DEFAULT 0, welcome_text TEXT DEFAULT 'Добро пожаловать в беседу!')")
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
    if uid == OWNER_ID: return ("Владелец проекта", 5)
    cursor.execute("SELECT role_name, access FROM global_staff WHERE user_id = ?", (uid,))
    r = cursor.fetchone()
    return r if r else ("Участник", 0)

def get_user(cid: int, uid: int):
    register_chat(cid)
    cursor.execute("SELECT nickname, role_name, access, warns, preds, mute_until FROM users WHERE chat_id = ? AND user_id = ?", (cid, uid))
    r = cursor.fetchone()
    if not r:
        cursor.execute("INSERT INTO users (chat_id, user_id) VALUES (?, ?)", (cid, uid))
        conn.commit()
        nick, l_role, l_acc, warns, preds, mute = ("Не установлен", "Участник", 0, 0, 0, 0)
    else: nick, l_role, l_acc, warns, preds, mute = r
    g_role, g_acc = get_global(uid)
    if g_acc >= l_acc and g_acc > 0: return (nick, f"{g_role} [Глобал]", g_acc, warns, preds, mute)
    return (nick, l_role, l_acc, warns, preds, mute)

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
            get_user(cid, uid)
            _, w = get_chat_settings(cid)
            await m.answer(f"👋 Приветствуем, [id{uid}|новый участник]!\n{w}")
        return
    if not m.text or m.from_id < 0: return
    args = m.text.strip().split()
    cmd = args[0].lower()
    nick, role, acc, warns, preds, mute = get_user(cid, m.from_id)
    sil, _ = get_chat_settings(cid)

    if not cmd.startswith(("+", "/", "!", "-")):
        if (mute > int(time.time()) or sil == 1) and acc < 2:
            try: await bot.api.messages.delete(peer_id=cid, cmids=[m.conversation_message_id], delete_for_all=True)
            except Exception: pass
        return

    if cmd in ["/help", "!помощь", "/помощь", "+помощь", "+команды"]:
        await m.answer("📋 КОМАНДЫ:\n👤 +стата, +ники, +состав, +гсостав\n🛡 (2+): +ник, +мут/-мут, +пред/-пред\n⚔️ (3+): +выг/-выг, +кик, +тишина, +созыв\n👑 (4+): +модер, +стмодер, +админ, +га, +снять, +приветствие\n🌐 Глобал (4+): +гмодер, +гстмодер, +гадмин, +гга, +гснять, +гдоступ, +гкик, +чаты")

    elif cmd in ["+стата", "+профиль", "/stats", "!стата"]:
        now = int(time.time())
        ms = f"Активен ({(mute - now) // 60 + 1} мин.)" if mute > now else "Нет"
        await m.answer(f"📊 Профиль [id{m.from_id}|участника]:\n• Ник: {nick}\n• Роль: {role} ({acc} ур.)\n• Выговоры: {warns}/3\n• Преды: {preds}/2\n• Мут: {ms}")

    elif cmd in ["+ники", "/nicks", "!ники"]:
        cursor.execute("SELECT user_id, nickname FROM users WHERE chat_id = ? AND nickname != 'Не установлен'", (cid,))
        rows = cursor.fetchall()
        if not rows: return await m.answer("📭 Ников пока нет.")
        res = ["📝 Список ников:\n"] + [f"{i}. [id{u}|{n}] — {get_user(cid, u)[1]}" for i, (u, n) in enumerate(rows, 1)]
        await m.answer("\n".join(res))

    elif cmd in ["+состав", "+админы", "+модеры"]:
        cursor.execute("SELECT user_id, nickname FROM users WHERE chat_id = ?", (cid,))
        st = []
        for u, n in cursor.fetchall():
            _, r, a, _, _, _ = get_user(cid, u)
            if a >= 2: st.append((a, f"• [{a} ур. | {r}] — [id{u}|{n if n != 'Не установлен' else 'Без ника'}]"))
        if not st: return await m.answer("📭 Состав пуст.")
        st.sort(key=lambda x: x[0], reverse=True)
        await m.answer("🛡 Состав чата:\n" + "\n".join([x[1] for x in st]))

    elif cmd == "+гсостав":
        cursor.execute("SELECT user_id, role_name, access FROM global_staff WHERE access >= 2 ORDER BY access DESC")
        res = [f"🌐 Глобальный состав:\n• [5 ур. | Владелец] — [id{OWNER_ID}|Создатель]"]
        for u, r, a in cursor.fetchall():
            if u != OWNER_ID: res.append(f"• [{a} ур. | {r}] — [id{u}|Админ]")
        await m.answer("\n".join(res))

    elif cmd == "+чаты":
        if acc < 4: return await m.answer("❌ Нужен 4+ ур.")
        cursor.execute("SELECT COUNT(*) FROM known_chats")
        await m.answer(f"🌐 Бот активен в **{cursor.fetchone()[0]}** чатах.")
    elif cmd in ["+модер", "+стмодер", "+админ", "+га", "+снять"]:
        req = 5 if cmd == "+га" else 4
        if acc < req: return await m.answer(f"❌ Нужен {req}+ ур.")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        roles = {"+модер": (2, "Модератор"), "+стмодер": (3, "Старший модератор"), "+админ": (3, "Администратор"), "+га": (4, "Главный администратор"), "+снять": (0, "Участник")}
        lvl, title = roles[cmd]
        get_user(cid, tid)
        cursor.execute("UPDATE users SET access = ?, role_name = ? WHERE chat_id = ? AND user_id = ?", (lvl, title, cid, tid))
        conn.commit()
        await m.answer(f"✅ В этом чате [id{tid}|участнику] выдана роль: **{title}** ({lvl} ур.).")

    elif cmd in ["+гмодер", "+гстмодер", "+гадмин", "+гга", "+гснять", "+гдоступ"]:
        req = 5 if cmd == "+гга" else 4
        if acc < req: return await m.answer(f"❌ Нужен {req}+ ур.")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        if tid == OWNER_ID: return await m.answer("⚠️ Нельзя изменить права Владельца.")
        if cmd == "+гдоступ":
            try:
                lvl = int(args[-1])
                rmap = {0: "Участник", 1: "Проверенный", 2: "Модератор", 3: "Старший модератор", 4: "Главный администратор", 5: "Владелец"}
                title = rmap[lvl]
            except Exception: return await m.answer("⚠️ Укажите уровень 0-5.")
        else:
            roles = {"+гмодер": (2, "Модератор"), "+гстмодер": (3, "Старший модератор"), "+гадмин": (3, "Администратор"), "+гга": (4, "Главный администратор"), "+гснять": (0, "Участник")}
            lvl, title = roles[cmd]
        cursor.execute("INSERT OR REPLACE INTO global_staff (user_id, role_name, access) VALUES (?, ?, ?)", (tid, title, lvl))
        if lvl == 0: cursor.execute("UPDATE users SET access = 0, role_name = 'Участник' WHERE user_id = ?", (tid,))
        conn.commit()
        cursor.execute("SELECT COUNT(*) FROM known_chats")
        cnt = cursor.fetchone()[0]
        await m.answer(f"🌐 Для [id{tid}|участника] установлена глобальная роль **{title}** ({lvl} ур.) во всех **{cnt}** чатах!")

    elif cmd == "+гкик":
        if acc < 4: return await m.answer("❌ Нужен 4+ ур.")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        if tid == OWNER_ID or (get_global(tid)[1] >= acc and m.from_id != OWNER_ID): return await m.answer("❌ Нельзя кикнуть этого админа.")
        reason = get_tail(m, args, 2) or "Не указана"
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
        await m.answer(f"🚫 **ГЛОБАЛЬНЫЙ КИК**\n• Игрок: [id{tid}|участник]\n• Кикнут из: **{kicked}** из {len(chats)} чатов\n• Причина: {reason}")
    elif cmd in ["+ник", "/snick"]:
        if acc < 2: return await m.answer("❌ Нужен 2+ ур.")
        tid = get_target(m, args)
        nn = get_tail(m, args, 2)
        if not tid or not nn: return await m.answer("⚠️ Пример: +ник @user Ivan_Ivanov")
        get_user(cid, tid)
        cursor.execute("UPDATE users SET nickname = ? WHERE chat_id = ? AND user_id = ?", (nn, cid, tid))
        conn.commit()
        await m.answer(f"✅ Установлен ник: {nn}")

    elif cmd == "+мут":
        if acc < 2: return await m.answer("❌ Нужен 2+ ур.")
        tid = get_target(m, args)
        try:
            idx = 1 if m.reply_message else 2
            mins = int(args[idx])
            reason = " ".join(args[idx+1:]) or "Не указана"
        except Exception: return await m.answer("⚠️ Пример: +мут @user 30 Флуд")
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        cursor.execute("UPDATE users SET mute_until = ? WHERE chat_id = ? AND user_id = ?", (int(time.time()) + mins * 60, cid, tid))
        conn.commit()
        await m.answer(f"🔇 [id{tid}|Участник] получил мут на {mins} мин. Причина: {reason}")

    elif cmd == "-мут":
        if acc < 2: return await m.answer("❌ Нужен 2+ ур.")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        cursor.execute("UPDATE users SET mute_until = 0 WHERE chat_id = ? AND user_id = ?", (cid, tid))
        conn.commit()
        await m.answer("🔊 Мут снят.")

    elif cmd == "+пред":
        if acc < 2: return await m.answer("❌ Нужен 2+ ур.")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        reason = get_tail(m, args, 2) or "Не указана"
        tn, _, _, tw, tp, _ = get_user(cid, tid)
        tp += 1
        if tp >= 2:
            tp, tw = 0, tw + 1
            if tw >= 3:
                cursor.execute("UPDATE users SET warns = 0, preds = 0 WHERE chat_id = ? AND user_id = ?", (cid, tid))
                conn.commit()
                await m.answer(f"🚫 [id{tid}|{tn}] 2/2 преда → 3/3 выговоров и кик! Причина: {reason}")
                try: await bot.api.messages.remove_chat_user(chat_id=m.chat_id, user_id=tid)
                except Exception: pass
            else:
                cursor.execute("UPDATE users SET warns = ?, preds = 0 WHERE chat_id = ? AND user_id = ?", (tw, cid, tid))
                conn.commit()
                await m.answer(f"⚠️ [id{tid}|{tn}] 2/2 преда → выговор ({tw}/3)! Причина: {reason}")
        else:
            cursor.execute("UPDATE users SET preds = ? WHERE chat_id = ? AND user_id = ?", (tp, cid, tid))
            conn.commit()
            await m.answer(f"🔸 [id{tid}|{tn}] получил пред ({tp}/2). Причина: {reason}")

    elif cmd == "-пред":
        if acc < 2: return await m.answer("❌ Нужен 2+ ур.")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        tn, _, _, _, tp, _ = get_user(cid, tid)
        if tp > 0:
            cursor.execute("UPDATE users SET preds = ? WHERE chat_id = ? AND user_id = ?", (tp - 1, cid, tid))
            conn.commit()
            await m.answer(f"✅ Пред снят ({tp - 1}/2).")
        else: await m.answer("ℹ️ Предов нет.")

    elif cmd in ["+выг", "/warn"]:
        if acc < 3: return await m.answer("❌ Нужен 3+ ур.")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        reason = get_tail(m, args, 2) or "Не указана"
        tn, _, _, tw, _, _ = get_user(cid, tid)
        tw += 1
        if tw >= 3:
            cursor.execute("UPDATE users SET warns = 0 WHERE chat_id = ? AND user_id = ?", (cid, tid))
            conn.commit()
            await m.answer(f"🚫 [id{tid}|{tn}] получил 3/3 выговоров и исключён! Причина: {reason}")
            try: await bot.api.messages.remove_chat_user(chat_id=m.chat_id, user_id=tid)
            except Exception: pass
        else:
            cursor.execute("UPDATE users SET warns = ? WHERE chat_id = ? AND user_id = ?", (tw, cid, tid))
            conn.commit()
            await m.answer(f"⚠️ [id{tid}|{tn}] получил выговор ({tw}/3). Причина: {reason}")

    elif cmd in ["-выг", "/unwarn"]:
        if acc < 3: return await m.answer("❌ Нужен 3+ ур.")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        tn, _, _, tw, _, _ = get_user(cid, tid)
        if tw > 0:
            cursor.execute("UPDATE users SET warns = ? WHERE chat_id = ? AND user_id = ?", (tw - 1, cid, tid))
            conn.commit()
            await m.answer(f"✅ Выговор снят ({tw - 1}/3).")
        else: await m.answer("ℹ️ Выговоров нет.")

    elif cmd in ["+кик", "/kick"]:
        if acc < 3: return await m.answer("❌ Нужен 3+ ур.")
        tid = get_target(m, args)
        if not tid: return await m.answer("⚠️ Укажите пользователя.")
        reason = get_tail(m, args, 2) or "Не указана"
        await m.answer(f"👢 [id{tid}|Участник] исключён. Причина: {reason}")
        try: await bot.api.messages.remove_chat_user(chat_id=m.chat_id, user_id=tid)
        except Exception: await m.answer("⚠️ Нет прав администратора.")

    elif cmd == "+тишина":
        if acc < 3: return await m.answer("❌ Нужен 3+ ур.")
        ns = 0 if sil == 1 else 1
        cursor.execute("UPDATE chat_settings SET silence = ? WHERE chat_id = ?", (ns, cid))
        conn.commit()
        await m.answer("🔇 **Режим тишины включён!**" if ns == 1 else "🔊 **Режим тишины выключен!**")

    elif cmd == "+созыв":
        if acc < 3: return await m.answer("❌ Нужен 3+ ур.")
        text = " ".join(args[1:]) or "Общий сбор!"
        try:
            mem = await bot.api.messages.get_conversation_members(peer_id=cid)
            tags = [f"[id{i.member_id}|•]" for i in mem.items if i.member_id > 0]
            await m.answer(f"📢 **Внимание!** {text}\n" + "".join(tags))
        except Exception: await m.answer("⚠️ Нет прав администратора.")

    elif cmd == "+приветствие":
        if acc < 4: return await m.answer("❌ Нужен 4+ ур.")
        text = " ".join(args[1:])
        if not text: return await m.answer("⚠️ Введите текст приветствия.")
        cursor.execute("UPDATE chat_settings SET welcome_text = ? WHERE chat_id = ?", (text, cid))
        conn.commit()
        await m.answer(f"✅ Приветствие сохранено:\n«{text}»")

bot.run()
