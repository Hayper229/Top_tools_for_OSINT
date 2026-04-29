import requests
import bs4
import user_agent
import urllib3
import time
from colorama import init, Fore, Style

# Инициализация colorama
init(autoreset=True)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

visited_links = set()
found_tg = set()

def crawl(url, max_depth, current_depth=0):
    if current_depth > max_depth or url in visited_links:
        return
    
    visited_links.add(url)
    
    # Формируем метку времени
    timestamp = f"[{time.asctime()}]"
    print(f"{Fore.CYAN}{timestamp} {Fore.WHITE}Уровень {current_depth}: {url}")

    headers = {'User-Agent': user_agent.generate_user_agent()}
    
    try:
        resp = requests.get(url, headers=headers, verify=False, timeout=5)
        if 'text/html' not in resp.headers.get('Content-Type', ''):
            return
            
        soup = bs4.BeautifulSoup(resp.text, 'html.parser')

        # Ищем ссылки в <a> (href) и картинках <img> (src/href)
        for tag in soup.find_all(['a', 'img']):
            link = tag.get('href') or tag.get('src')

            if not link:
                continue

            # Обработка Telegram
            if 't.me/' in link:
                if link not in found_tg:
                    found_tg.add(link)
                    print(f"{Fore.GREEN}  [!] Нашел TG: {link}")
            
            # Обработка обычных ссылок (только http)
            elif link.startswith('http') and not link.startswith('mailto:'):
                # Рекурсивно идем дальше
                crawl(link, max_depth, current_depth + 1)

    except Exception:
        print(f"{Fore.RED}  [X] Ошибка доступа: {url}")

if __name__ == "__main__":
   try:
       START_URL = input('URL: ')
       MAX_LEVEL = 10
       print(f"{Fore.YELLOW}Начинаю парсинг в {time.asctime()}...\n") 
       crawl(START_URL, MAX_LEVEL)
       print("\n" + "="*50)
       print(f"{Fore.GREEN}Готово в: {time.asctime()}")
       print(f"{Fore.MAGENTA}Всего уникальных TG: {len(found_tg)}")
       print(f"{Fore.MAGENTA}Всего обработано ссылок: {len(visited_links)}")
       print("="*50)
   except KeyboardInterrupt:
          print('\nЗавершение программы..')
