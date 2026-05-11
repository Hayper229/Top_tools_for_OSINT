import asyncio
import re
import os
import time
import argparse
import colorama
import logging
from datetime import datetime
from pyrogram import Client, errors, enums, filters
from pyrogram.raw import functions, types

# Глушим системный мусор Pyrogram, оставляем только твой оригинальный LIVE лог
logging.getLogger("pyrogram").setLevel(logging.CRITICAL)
logging.getLogger("asyncio").setLevel(logging.CRITICAL)

colorama.init(autoreset=True)

# --- [КОНФИГУРАЦИЯ] ---
api_id = API_ID
api_hash = 'API_HASH'
phone = '+PHONE_NUMBER'
ADMIN_TAG = 'YOUR_USERNAME'
MY_ID = YOUR_ID 

# Авто-очистка Username от символа @
if isinstance(ADMIN_TAG, str):
    ADMIN_TAG = ADMIN_TAG.lstrip('@')

PROXY_LIST = [
    ('IP', PORT, 'SECRET'),
    ('IP', PORT, 'SECRET')
]

client = None

async def init_client():
    global client
    for p_host, p_port, p_secret in PROXY_LIST:
        print(f"{colorama.Fore.CYAN}[*] Пробую прокси: {p_host}:{p_port}")
        try:
            proxy = {"hostname": p_host, "port": p_port, "secret": p_secret}
            cl = Client(f"session_{phone}", api_id=api_id, api_hash=api_hash, proxy=proxy, sleep_threshold=120)
            await cl.connect()
            if await cl.get_me():
                print(f"{colorama.Fore.GREEN}[+] OK: {p_host}")
                client = cl
                return
            await cl.disconnect()
        except: continue
    
    print(f"{colorama.Fore.YELLOW}[!] Прокси не подошли, использую прямое соединение")
    client = Client(f"session_{phone}", api_id=api_id, api_hash=api_hash)
    await client.start()

async def smart_join(target):
    try:
        chat = await client.join_chat(target)
        # --- [РЕЖИМ ПРИЗРАК] ---
        async for m in client.get_chat_history(chat.id, limit=10):
            if m.service and (m.new_chat_members or m.joined_by_invite):
                me = await client.get_me()
                is_me = False
                if m.new_chat_members:
                    for u in m.new_chat_members:
                        if u.id == me.id: is_me = True
                if is_me or m.joined_by_invite:
                    await client.delete_messages(chat.id, m.id)
                    print(f"{colorama.Fore.CYAN}[GHOST] Сервисное сообщение о входе удалено.")
                    break
    except: pass

async def get_messages(channel_link, limit=None):
    all_data = {"msgs": [], "users_map": {}, "main": None, "linked": None}
    try:
        await smart_join(channel_link)
        main_entity = await client.get_chat(channel_link)
        print(f"{colorama.Fore.YELLOW}[+] Цель: {main_entity.title}. Начинаю сбор сообщений...") 
        all_data["main"] = main_entity
        
        main_label = "CHANNEL" if main_entity.type == enums.ChatType.CHANNEL else "GROUP"
        main_color = "#da70d6" if main_entity.type == enums.ChatType.CHANNEL else "#FFD700"

        async def process_msgs(chat_obj, label, tag_color):
            async for m in client.get_chat_history(chat_obj.id, limit=limit):
                if m.text or m.caption:
                    text = m.text or m.caption
                    u_id_str = str(m.from_user.id) if m.from_user else f"PeerChannel(id={chat_obj.id})"
                    
                    # ТВОЙ ОРИГИНАЛЬНЫЙ СТИЛЬ
                    print(f"{colorama.Fore.WHITE}[{colorama.Fore.BLUE}{time.asctime()}{colorama.Fore.WHITE}] {colorama.Fore.WHITE}[{colorama.Fore.YELLOW}Message{colorama.Fore.WHITE}] "
                          f"{colorama.Fore.GREEN}{text.strip()[:80]}... "
                          f"{colorama.Fore.WHITE}[{colorama.Fore.YELLOW}UserID{colorama.Fore.WHITE}] "
                          f"[{colorama.Fore.MAGENTA}{u_id_str}{colorama.Fore.WHITE}] "
                          f"{colorama.Fore.WHITE}[{colorama.Fore.YELLOW}Date of Dispatch{colorama.Fore.WHITE}] "
                          f"[{colorama.Fore.MAGENTA}{m.date}{colorama.Fore.WHITE}]")
                    
                    msg_html = (
                        f"<div style='margin-bottom: 25px; border-bottom: 1px solid #333; padding-bottom: 10px;'>"
                        f"<span style='color: #00FF00;'>[</span><span style='color: {tag_color};'>{label}</span><span style='color: #00FF00;'>]</span> "
                        f"<span style='color: #00FF00;'>Message</span><span style='color: #FF0000;'>:</span> <span style='color: #FFFF00;'>{text}</span><br>"
                        f"<div style='margin-top: 10px; font-size: 0.9em;'>"
                        f"<span style='color: #00FF00;'>UserID</span><span style='color: #FF0000;'>:</span> <span style='color: #FFFF00;'>{u_id_str}</span><br>"
                        f"<span style='color: #00FF00;'>Date of Dispatch</span><span style='color: #FF0000;'>:</span> <span style='color: #FFFF00;'>{m.date}</span>"
                        f"</div></div>"
                    )
                    all_data["msgs"].append(msg_html)
                    
                    if m.from_user and m.from_user.id != MY_ID:
                        u = m.from_user
                        all_data["users_map"][u.id] = {
                            "name": f"{u.first_name or ''} {u.last_name or ''}".strip(),
                            "user": u.username or "Unknown",
                            "phone": u.phone_number or "Unknown",
                            "is_admin": False
                        }

        await process_msgs(main_entity, main_label, main_color)
        
        full = await client.get_chat(main_entity.id)
        if full.linked_chat:
            all_data["linked"] = full.linked_chat
            await smart_join(full.linked_chat.id)
            await process_msgs(full.linked_chat, "CHAT", "#FF8C00")
            
        return all_data
    except Exception as e:
        print(f"Ошибка: {e}")
        return all_data

async def func(args):
    if args.c:
        data = await get_messages(args.c, limit=None)
        if not data["main"]: return

        final_users = data["users_map"]
        target = data["linked"] if data["linked"] else data["main"]
        
        # КАСКАДНЫЙ СБОР
        try:
            # 1. Список участников + Пометка ADMIN
            async for member in client.get_chat_members(target.id):
                u = member.user
                if u.id != MY_ID:
                    is_admin = member.status in [enums.ChatMemberStatus.ADMINISTRATOR, enums.ChatMemberStatus.OWNER]
                    final_users[u.id] = {
                        "name": f"{u.first_name or ''} {u.last_name or ''}".strip(),
                        "user": u.username or "Unknown",
                        "phone": u.phone_number or "Unknown",
                        "is_admin": is_admin
                    }
            
            # 2. Реакции (деанон скрытых)
            async for m in client.get_chat_history(data["main"].id, limit=50):
                if m.reactions:
                    try:
                        res = await client.invoke(functions.messages.GetMessageReactionsList(
                            peer=await client.resolve_peer(data["main"].id), id=m.id, limit=100))
                        for r in res.users:
                            if r.id not in final_users and r.id != MY_ID:
                                final_users[r.id] = {
                                    "name": f"{r.first_name or ''} {r.last_name or ''}".strip(), 
                                    "user": r.username or "Unknown", "phone": r.phone or "Unknown", "is_admin": False}
                    except: pass

            # 3. Ответы (скрытые ID)
            async for m in client.get_chat_history(target.id, limit=500):
                if m.reply_to_message:
                    u = m.reply_to_message.from_user
                    if u and u.id not in final_users and u.id != MY_ID:
                        final_users[u.id] = {
                            "name": f"{u.first_name or ''} {u.last_name or ''}".strip(),
                            "user": u.username or "Unknown", "phone": u.phone_number or "Unknown", "is_admin": False}
        except: pass

        # Генерация HTML
        users_html = []
        for uid, info in final_users.items():
            u_disp = f"@{info['user']}" if info['user'] != "Unknown" else "Unknown"
            
            # Фиолетовая метка ADMIN
            admin_tag = ""
            if info.get("is_admin"):
                admin_tag = f" <span style='color: #FF0000;'>[</span><span style='color: #8A2BE2;'>ADMIN</span><span style='color: #FF0000;'>]</span>"
            
            line = (
                f"<div style='border-bottom: 1px solid #444; margin-bottom: 20px; padding-bottom: 10px;'>"
                f"<span style='color: #00FF00;'>User</span><span style='color: #FF0000;'>:</span> <span style='color: #FFFF00;'>{info['name']}</span>{admin_tag}<br>"
                f"<span style='color: #00FF00;'>Username</span><span style='color: #FF0000;'>:</span> <span style='color: #FFFF00;'>{u_disp}</span><br>"
                f"<span style='color: #00FF00;'>ID</span><span style='color: #FF0000;'>:</span> <span style='color: #FFFF00;'>{uid}</span><br>"
                f"<span style='color: #00FF00;'>Phone number</span><span style='color: #FF0000;'>:</span> <span style='color: #FFFF00;'>{info['phone']}</span>"
                f"</div>"
            )
            users_html.append(line)
        
        with open('report.html', 'w', encoding='utf-8') as f:
            f.write('<html lang="ru"><head><meta charset="utf-8"></head><body style="background-color: #0a0a0a; color: #00FF00; font-family: Consolas, monospace; padding: 20px;">')
            f.write(f"<h3><span style='color: #00FF00;'>Generated on</span><span style='color: #FF0000;'>:</span> <span style='color: #FFFF00;'>{time.asctime()}</span></h3>")
            f.write(f"<h2><span style='color: #00FF00;'>Total Messages</span><span style='color: #FF0000;'>:</span> <span style='color: #FFFF00;'>{len(data['msgs'])}</span></h2>")
            f.write(f"<h2><span style='color: #00FF00;'>Total Users</span><span style='color: #FF0000;'>:</span> <span style='color: #FFFF00;'>{len(users_html)}</span></h2><hr>")
            f.write("".join(data['msgs']))
            f.write("<h2><span style='color: #00FF00;'>Users</span><span style='color: #FF0000;'>:</span></h2>")
            f.write("".join(users_html))
            f.write("</body></html>")
        
        if os.path.exists('report.html'):
            cap = f"CH: {args.c}\nTotal messages: {len(data['msgs'])}\nTotal users: {len(users_html)}\nDate: {time.asctime()}"
            await client.send_document(ADMIN_TAG, 'report.html', caption=cap)
            os.remove('report.html')
            
            print(f"{colorama.Fore.WHITE}[{colorama.Fore.BLUE}{time.asctime()}{colorama.Fore.WHITE}] {colorama.Fore.GREEN}Отчет отправлен {colorama.Fore.YELLOW}{ADMIN_TAG}")
            print(f"{colorama.Fore.WHITE}[{colorama.Fore.BLUE}{time.asctime()}{colorama.Fore.WHITE}] {colorama.Fore.GREEN}Total users  {colorama.Fore.RED}-> {colorama.Fore.YELLOW}{len(users_html)}")
            print(f"{colorama.Fore.WHITE}[{colorama.Fore.BLUE}{time.asctime()}{colorama.Fore.WHITE}] {colorama.Fore.GREEN}Total messages  {colorama.Fore.RED}-> {colorama.Fore.YELLOW}{len(data['msgs'])}")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", help="target link")
    args = parser.parse_args()

    await init_client()
    if not client.is_connected:
        await client.start()

    if args.c:
        await func(args)
    
    print(f"{colorama.Fore.WHITE}[{colorama.Fore.BLUE}{time.asctime()}{colorama.Fore.WHITE}] Мониторинг запущен. Ctrl+C для выхода.")
    @client.on_message(filters.group | filters.channel)
    async def live_monitor(_, event):
        if event.text:
            u_id = str(event.from_user.id) if event.from_user else f"[{event.chat.id}]"
            print(f"{colorama.Fore.WHITE}[{colorama.Fore.BLUE}{time.asctime()}{colorama.Fore.WHITE}]{colorama.Fore.WHITE}[{colorama.Fore.CYAN}LIVE{colorama.Fore.WHITE}]{colorama.Fore.WHITE}[{colorama.Fore.YELLOW}UserID{colorama.Fore.WHITE}] [{colorama.Fore.MAGENTA}{u_id}{colorama.Fore.WHITE}]: "
                  f"{colorama.Fore.WHITE}[{colorama.Fore.YELLOW}Message{colorama.Fore.WHITE}] {colorama.Fore.GREEN}{event.text}")
    await asyncio.Event().wait()

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
