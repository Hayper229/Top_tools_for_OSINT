import asyncio
import re
import random
import os
import argparse
from datetime import datetime
from pyrogram import Client, errors, enums
from pyrogram.raw import functions
from rich.console import Console
from rich.table import Table
from rich.progress import Progress

# --- [КОНФИГУРАЦИЯ] ---
API_ID = API_ID
API_HASH = 'API_HASH'
console = Console()

INVITE_REGEX = r'(?:https?://)?t\.me/(?:joinchat/|\+)[a-zA-Z0-9_-]+'
ADMIN_REGEX = r'@[\w\d_]+'

async def get_admin_info(app, username):
    try:
        await asyncio.sleep(random.uniform(1.0, 2.0))
        user = await app.get_users(username)
        
        if user.status == enums.UserStatus.ONLINE:
            status = "Online"
        elif user.last_online_date:
            status = user.last_online_date.strftime("%Y-%m-%d %H:%M")
        else:
            status = "Recently/Hidden"
            
        return f"{user.id} | {status}"
    except:
        return "N/A | Hidden"

async def sniff_passive(app, link):
    try:
        # Извлекаем хэш ссылки
        invite_hash = link.split('/')[-1].replace('+', '').replace('joinchat/', '')
        await asyncio.sleep(random.uniform(2.0, 4.0))
        
        # Прямой вызов API через Pyrogram для проверки инвайта
        result = await app.invoke(functions.messages.CheckChatInvite(hash=invite_hash))
        
        # Обработка результата (ChatInvite или ChatInviteAlready)
        # В Pyrogram raw-результаты приходят в виде объектов ChatInvite
        title = getattr(result, "title", "Private Chat")
        members = getattr(result, "participants_count", 0)
        about = getattr(result, "about", "")
        
        contacts = list(set(re.findall(ADMIN_REGEX, about)))
        admin_details = []
        for adm in contacts:
            intel = await get_admin_info(app, adm)
            admin_details.append(f"{adm} ({intel})")
            
        return {
            "title": title,
            "members": members,
            "admins": " | ".join(admin_details) if admin_details else "None",
            "link": link
        }
    except:
        return None

async def process_links(app, links, source_name):
    table = Table(title=f"Results: {source_name}", title_style="bold magenta")
    table.add_column("Invite Link", style="blue")
    table.add_column("Members", style="green")
    table.add_column("Admin Intel (ID | Last Seen)", style="cyan")

    report_lines = []
    with Progress(transient=True) as progress:
        task = progress.add_task("[magenta]Analyzing links...", total=len(links))
        for link in links:
            info = await sniff_passive(app, link)
            if info:
                table.add_row(info['link'], str(info['members']), info['admins'])
                report_lines.append(f"Link: {info['link']} | admin_intel: {info['admins']} | title: {info['title']}")
            progress.update(task, advance=1)

    console.print(table)
    
    filename = "intel_links.txt"
    with open(filename, "w", encoding="utf-8") as f:
        f.write("\n".join(report_lines))
    
    if report_lines:
        target_user = "YOUR_USERNAME"
        try:
            caption = f"Source: {source_name}\nFound valid: {len(report_lines)}\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            await app.send_document(target_user, filename, caption=caption)
            console.print(f"[bold green]✅ Results sent to @{target_user}[/bold green]")
        except Exception as e:
            console.print(f"[bold red]❌ Error sending to @{target_user}: {e}[/bold red]")

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--target", help="Username канала")
    parser.add_argument("-f", "--file", help="Путь к файлу")
    parser.add_argument("-l", "--limit", type=int, default=3_000_000)
    args = parser.parse_args()

    # В Pyrogram сессия создается автоматически при первом запуске
    async with Client("my_account", api_id=API_ID, api_hash=API_HASH) as app:
        links_to_check = set()
        
        if args.target:
            try:
                target = args.target.replace("@", "")
                chat = await app.get_chat(target)
                targets = [chat.id]
                
                # Поиск привязанного чата (Linked Chat)
                full_chat = await app.get_chat(chat.id)
                if full_chat.linked_chat:
                    console.print(f"[cyan]Found linked chat: {full_chat.linked_chat.title}[/cyan]")
                    targets.append(full_chat.linked_chat.id)
                
                for t_id in targets:
                    console.print(f"[magenta]Scanning ID: {t_id}...[/magenta]")
                    async for message in app.get_chat_history(t_id, limit=args.limit):
                        if message.text or message.caption:
                            text = message.text or message.caption
                            found = re.findall(INVITE_REGEX, text)
                            for l in found:
                                links_to_check.add(l if l.startswith('http') else f"https://{l}")
                source = args.target
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")
                return
                
        elif args.file and os.path.exists(args.file):
            with open(args.file, 'r') as f:
                for line in f:
                    if "t.me/" in line:
                        links_to_check.add(line.strip())
            source = args.file
        else:
            console.print("[red]Используй -t или -f[/red]")
            return

        if links_to_check:
            await process_links(app, list(links_to_check), source)
        else:
            console.print("[yellow]No links found.[/yellow]")

if __name__ == "__main__":
    asyncio.run(main())
