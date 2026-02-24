from bs4 import BeautifulSoup
import requests


def get_aniworld_session(email, password):
    session = requests.Session()

    # Deine Browser-Identität (Chrome 145)
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
        'Origin': 'https://aniworld.to',
        'Referer': 'https://aniworld.to/login',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    }

    try:
        # 1. Schritt: Cookies initialisieren
        print("Initialisiere Cookies...")
        session.get("https://aniworld.to/login", headers=headers)

        # 2. Schritt: Login POST
        payload = {
            'email': email,
            'password': password
        }

        print("Sende Login...")
        session.post("https://aniworld.to/login", data=payload, headers=headers)

        # 3. Schritt: Account-Seite abrufen
        print("Rufe Account-Seite ab...")
        account_res = session.get("https://aniworld.to/account", headers=headers)

        # Validierung: Sind wir wirklich drin?
        is_logged_in = "logout" in account_res.text

        # Das Format, das du in deiner debug_login.json hast
        debug_data = [
            dict(account_res.headers),          # Response Headers
            dict(account_res.request.headers)   # Request Headers (mit deinen Tokens/Cookies)
        ]

        return session, debug_data, is_logged_in

    except Exception as e:
        print(f"Fehler beim Login: {e}")
        return None, None, False




def get_watchlist_and_subscribed_from_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    watchlist = []
    
    items = soup.find_all('div', class_='col-md-15')
    
    for item in items:
        link_tag = item.find('a')
        if not link_tag:
            continue
            
        # 1. Name extrahieren (aus dem h3 Tag)
        name = item.find('h3').get_text(strip=True)
        
        # 2. Link extrahieren (/anime/stream/...)
        link = link_tag['href']
        
        # 3. Genre (aus dem small Tag)
        genre = item.find('small').get_text(strip=True)
        
        # 4. Cover-URL extrahieren
        img_tag = item.find('img')
        cover_url = img_tag['src'] if img_tag else None
        
        # Alles in ein Dictionary packen
        watchlist.append({
            "name": name,
            "slug": link.split('/')[-1],
            "full_link": f"https://aniworld.to{link}",
            "genre": genre,
            "cover": f"https://aniworld.to{cover_url}" if cover_url else None
        })
        
    return watchlist

def wachlist(cookies):
    url = "https://aniworld.to/account/watchlist"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
        'Origin': 'https://aniworld.to',
        'Referer': 'https://aniworld.to/login',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Cookie': cookies
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print("Watchlist erfolgreich abgerufen!")
            
            return get_watchlist_and_subscribed_from_html(response.text)
        
        else:
            print(f"Fehler beim Abrufen der Watchlist: Status Code {response.status_code}")
            return None
    except Exception as e:
        print(f"Fehler beim Abrufen der Watchlist: {e}")
        return None
    
def subscribed(cookies):
    url = "https://aniworld.to/account/subscribed"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
        'Origin': 'https://aniworld.to',
        'Referer': 'https://aniworld.to/login',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Cookie': cookies
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            print("Abonnierte Serien erfolgreich abgerufen!")
            return get_watchlist_and_subscribed_from_html(response.text)
        
        else:
            print(f"Fehler beim Abrufen der abonnierten Serien: Status Code {response.status_code}")
            return None
    except Exception as e:
        print(f"Fehler beim Abrufen der abonnierten Serien: {e}")
        return None
    
def setIsWathed(cookies, episode_id):
    url = f"https://aniworld.to/ajax/watchEpisode"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Cookie': cookies
    }
    try:
        response = requests.post(url, headers=headers, data={'episode': episode_id})
        if response.status_code == 200:
            data = response.json()
            return data.get('status', False)
        else:
            print(f"Fehler beim Abrufen des Watch-Status: Status Code {response.status_code}")
            return None
    except Exception as e:
        print(f"Fehler beim Abrufen des Watch-Status: {e}")
        return None


def setWechlist(cookies, slug):
    url = f"https://aniworld.to/anime/stream/{slug}/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Cookie': cookies
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            add_series_div = soup.find('div', class_='add-series')
            series_id = add_series_div.get('data-series-id')
            response = requests.post(f"https://aniworld.to/ajax/setWatchList", headers=headers, data={'series': series_id})
            print(f"{slug} erfolgreich zur Watchlist getoggelt!")
        else:
            print(f"Fehler beim Hinzufügen zur Watchlist: Status Code {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Fehler beim Hinzufügen zur Watchlist: {e}")
        
def setSubsscribed(cookies, slug):
    url = f"https://aniworld.to/anime/stream/{slug}/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Cookie': cookies
    }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            add_series_div = soup.find('div', class_='add-series')
            series_id = add_series_div.get('data-series-id')
            response = requests.post(f"https://aniworld.to/ajax/setFavourite", headers=headers, data={'series': series_id})
            print(f"{slug} erfolgreich als abonniert getoggelt!")
        else:
            print(f"Fehler beim Markieren als abonniert: Status Code {response.status_code}")
    except requests.exceptions.RequestException as e:
        print(f"Fehler beim Markieren als abonniert: {e}")

    
    
    
    
# bsp anwendung:
if __name__ == "__main__":
    email_input = 'g9hpzvhp8@mozmail.com'
    pass_input = 'Xn]?z!4J5f#.4c#'
    active_session, session_debug, success = get_aniworld_session(email_input, pass_input)
    if success:
        print("Login war ERFOLGREICH!")
        request_headers = session_debug[1]
        cookies = request_headers.get('Cookie')
        test = wachlist(cookies)
        print(test)
    else:
        print("Login fehlgeschlagen.")