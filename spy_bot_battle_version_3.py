from telethon import TelegramClient, events, connection
from telethon.tl.functions.channels import JoinChannelRequest, GetFullChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, GetMessageReactionsListRequest
from telethon.tl.types import Channel, PeerUser, PeerChannel, User, ChannelParticipantsAdmins
import os
import colorama
import argparse
import asyncio
import time
from datetime import datetime, timezone

colorama.init(autoreset=True)

api_id = API_ID
api_hash = 'API_HASH'
phone = '+PHONE_NUMBER'
ADMIN_TAG = '@YOUR_USERNAME'
MY_ID = YOUR_ID

PROXY_LIST = [
    ('IP', PORT, 'SECRET'),
    ('IP', PORT, 'SECRET'),
    ('IP', PORT, 'SECRET')
]

client = None

async def init_client():
    global client
    for p_host, p_port, p_secret in PROXY_LIST:
        print(f"{colorama.Fore.CYAN}[*] Пробую прокси: {p_host}:{p_port}")
        try:
            proxy = (p_host, p_port, p_secret)
            cl = TelegramClient(phone, api_id, api_hash, proxy=proxy, 
                                connection=connection.ConnectionTcpMTProxyIntermediate,
                                connection_retries=1, retry_delay=1)
            await cl.connect()
            if cl.is_connected():
                print(f"{colorama.Fore.GREEN}[+] OK: {p_host}")
                client = cl
                return
            await cl.disconnect()
        except: continue
    client = TelegramClient(phone, api_id, api_hash)
    await client.connect()

async def smart_join(target):
    try:
        if 't.me/joinchat/' in target or 't.me/+' in target:
            hash_code = target.split('/')[-1].replace('+', '')
            await client(ImportChatInviteRequest(hash_code))
        else:
            entity = await client.get_entity(target)
            await client(JoinChannelRequest(entity))
    except: pass

async def get_messages(channel_link, limit=None):
    all_data = {"msgs": [], "users_map": {}, "main": None, "linked": None}
    try:
        await smart_join(channel_link)
        main_entity = await client.get_entity(channel_link)
        print(f"{colorama.Fore.YELLOW}[+] Цель: {main_entity.title}. Начинаю сбор сообщений...") 
        all_data["main"] = main_entity
        
        is_broadcast = isinstance(main_entity, Channel) and getattr(main_entity, 'broadcast', False)
        main_label = "CHANNEL" if is_broadcast else "GROUP"
        main_color = "#da70d6" if is_broadcast else "#FFD700"

        async def process_msgs(entity, label, tag_color):
            async for m in client.iter_messages(entity, limit=limit):
                if m.text:
                    u_id_str = str(m.from_id) if m.from_id else f"PeerChannel(channel_id={m.chat_id})"
                    
                    # ТВОЙ ОРИГИНАЛЬНЫЙ СТИЛЬ
                    print(f"{colorama.Fore.WHITE}[{colorama.Fore.BLUE}{time.asctime()}{colorama.Fore.WHITE}] {colorama.Fore.WHITE}[{colorama.Fore.YELLOW}Message{colorama.Fore.WHITE}] "
                          f"{colorama.Fore.GREEN}{m.text.strip()[:60]}... "
                          f"{colorama.Fore.WHITE}[{colorama.Fore.YELLOW}UserID{colorama.Fore.WHITE}] "
                          f"[{colorama.Fore.MAGENTA}{u_id_str}{colorama.Fore.WHITE}] "
                          f"{colorama.Fore.WHITE}[{colorama.Fore.YELLOW}Date of Dispatch{colorama.Fore.WHITE}] "
                          f"[{colorama.Fore.MAGENTA}{m.date}{colorama.Fore.WHITE}]")
                    
                    msg_html = (
                        f"<div style='margin-bottom: 25px; border-bottom: 1px solid #333; padding-bottom: 10px;'>"
                        f"<span style='color: #00FF00;'>[</span><span style='color: {tag_color};'>{label}</span><span style='color: #00FF00;'>]</span> "
                        f"<span style='color: #00FF00;'>Message</span><span style='color: #FF0000;'>:</span> <span style='color: #FFFF00;'>{m.text}</span><br>"
                        f"<div style='margin-top: 10px; font-size: 0.9em;'>"
                        f"<span style='color: #00FF00;'>UserID</span><span style='color: #FF0000;'>:</span> <span style='color: #FFFF00;'>{u_id_str}</span><br>"
                        f"<span style='color: #00FF00;'>Date of Dispatch</span><span style='color: #FF0000;'>:</span> <span style='color: #FFFF00;'>{m.date}</span>"
                        f"</div></div>"
                    )
                    all_data["msgs"].append(msg_html)
                    
                    if m.sender and isinstance(m.sender, User):
                        u = m.sender
                        if u.id == MY_ID: continue
                        f_name = f"{u.first_name or ''} {u.last_name or ''}".strip()
                        all_data["users_map"][u.id] = {
                            "name": f_name if f_name else "Unknown",
                            "user": u.username if u.username else "Unknown",
                            "phone": u.phone if u.phone else "Unknown"
                        }

        await process_msgs(main_entity, main_label, main_color)
        if is_broadcast:
            try:
                full = await client(GetFullChannelRequest(main_entity))
                if full.full_chat.linked_chat_id:
                    linked = await client.get_entity(full.full_chat.linked_chat_id)
                    all_data["linked"] = linked
                    await smart_join(linked)
                    await process_msgs(linked, "CHAT", "#FF8C00")
            except: pass
        return all_data
    except Exception as e:
        print(f"Ошибка: {e}")
        return all_data

async def func():
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", help="target link")
    argum = parser.parse_args()

    if argum.c:
        data = await get_messages(argum.c)
        if not data["main"]: return

        final_users = data["users_map"]
        target = data["linked"] if data["linked"] else data["main"]
        
        # КАСКАДНЫЙ СБОР (Методы поиска скрытых)
        try:
            # Метод 1: Прямой список
            async for u in client.iter_participants(target):
                if u.id != MY_ID:
                    final_users[u.id] = {"name": f"{u.first_name or ''} {u.last_name or ''}".strip(), "user": u.username or "Unknown", "phone": u.phone or "Unknown"}
            
            # Метод 2: Админы
            try:
                admins = await client.get_participants(target, filter=ChannelParticipantsAdmins)
                for u in admins:
                    if u.id != MY_ID:
                        final_users[u.id] = {"name": f"{u.first_name or ''} {u.last_name or ''}".strip(), "user": u.username or "Unknown", "phone": u.phone or "Unknown"}
            except: pass

            # Метод 3: Реакции (активные)
            try:
                async for m in client.iter_messages(data["main"], limit=50):
                    if m.reactions:
                        res = await client(GetMessageReactionsListRequest(peer=data["main"], id=m.id))
                        for r in res.reactions:
                            if isinstance(r.peer_id, PeerUser) and r.peer_id.user_id not in final_users:
                                u = await client.get_entity(r.peer_id)
                                if u.id != MY_ID:
                                    final_users[u.id] = {"name": f"{u.first_name or ''} {u.last_name or ''}".strip(), "user": u.username or "Unknown", "phone": u.phone or "Unknown"}
            except: pass
            
            # Метод 4: Чат обсуждения (если есть)
            if data["linked"]:
                async for u in client.iter_participants(data["linked"]):
                    if u.id != MY_ID:
                        final_users[u.id] = {"name": f"{u.first_name or ''} {u.last_name or ''}".strip(), "user": u.username or "Unknown", "phone": u.phone or "Unknown"}
        except: pass

        users_html = []
        for uid, info in final_users.items():
            u_disp = f"@{info['user']}" if info['user'] != "Unknown" else "Unknown"
            line = (
                f"<div style='border-bottom: 1px solid #444; margin-bottom: 20px; padding-bottom: 10px;'>"
                f"<span style='color: #00FF00;'>User</span><span style='color: #FF0000;'>:</span> <span style='color: #FFFF00;'>{info['name']}</span><br>"
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
            cap = f"CH: {argum.c}\nTotal messages: {len(data['msgs'])}\nTotal users: {len(users_html)}\nDate: {time.asctime()}"
            await client.send_file(ADMIN_TAG, 'report.html', caption=cap)
            os.remove('report.html')
            
            print(f"{colorama.Fore.WHITE}[{colorama.Fore.BLUE}{time.asctime()}{colorama.Fore.WHITE}] {colorama.Fore.GREEN}Отчет отправлен {colorama.Fore.YELLOW}{ADMIN_TAG}")
            print(f"{colorama.Fore.WHITE}[{colorama.Fore.BLUE}{time.asctime()}{colorama.Fore.WHITE}] {colorama.Fore.GREEN}Total users  {colorama.Fore.RED}-> {colorama.Fore.YELLOW}{len(users_html)}")
            print(f"{colorama.Fore.WHITE}[{colorama.Fore.BLUE}{time.asctime()}{colorama.Fore.WHITE}] {colorama.Fore.GREEN}Total messages  {colorama.Fore.RED}-> {colorama.Fore.YELLOW}{len(data['msgs'])}")

async def main():
    await init_client()
    async with client:
        await func()
        print(f"{colorama.Fore.WHITE}[{colorama.Fore.BLUE}{time.asctime()}{colorama.Fore.WHITE}] Мониторинг запущен. Ctrl+C для выхода.")
        @client.on(events.NewMessage)
        async def live_monitor(event):
            if event.message.text:
                u_id = str(event.from_id) if event.from_id else f"[{event.chat_id}]"
                print(f"{colorama.Fore.WHITE}[{colorama.Fore.BLUE}{time.asctime()}{colorama.Fore.WHITE}]{colorama.Fore.WHITE}[{colorama.Fore.CYAN}LIVE{colorama.Fore.WHITE}]{colorama.Fore.WHITE}[{colorama.Fore.YELLOW}UserID{colorama.Fore.WHITE}] [{colorama.Fore.MAGENTA}{u_id}{colorama.Fore.WHITE}]: "
                      f"{colorama.Fore.WHITE}[{colorama.Fore.YELLOW}Message{colorama.Fore.WHITE}] {colorama.Fore.GREEN}{event.message.text}")
        await client.run_until_disconnected()

if __name__ == '__main__':
    try: asyncio.run(main())
    except KeyboardInterrupt: pass
