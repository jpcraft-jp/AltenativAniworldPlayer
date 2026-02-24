import html
import requests
from bs4 import BeautifulSoup
import random
import time
from urllib.parse import quote
from aniworld.models import AniworldEpisode
from aniworld.config import Audio, Subtitles
from aniworld.models import AniworldEpisode
from aniworld.extractors import provider_functions
from urllib.parse import urljoin
import re

def extract_sessions(soup): 
    staffel_label = soup.find(lambda tag: tag.name == "strong" and "Staffeln:" in tag.text)
    if staffel_label:
        staffel_ul = staffel_label.find_parent('ul')
        if staffel_ul:
            # Wir nehmen den Link UND den Namen/Nummer der Staffel
            links = []
            for a in staffel_ul.find_all('a', href=True):
                links.append({
                    "name": a.text.strip(), 
                    "path": a['href']
                })
            return links
    return []

def extract_episodes(soup):
    out = []
    table = soup.find('table', class_='seasonEpisodesList')
    if not table:
        return []

    for tr in table.find_all('tr', attrs={'data-episode-id': True}):
        ep_id = tr.get('data-episode-id')
        cols = tr.find_all('td')
        
        # Wir brauchen mindestens 3 Spalten (Nummer, Titel, Hoster)
        if len(cols) >= 3:
            # 1. Folge Nummer (Index 0)
            nr_text = cols[0].text.strip()
            
            # 2. Titel (Index 1) - Hier war dein Fehler (du hattest Index 2)
            # Wir suchen das <a> Tag in der zweiten Zelle
            title_link = cols[1].find('a')
            name_de = ""
            name_en = ""
            
            if title_link:
                # Nutze .find(), da strong/span direkt im Link liegen
                strong_tag = title_link.find('strong')
                span_tag = title_link.find('span')
                name_de = strong_tag.text.strip() if strong_tag else ""
                name_en = span_tag.text.strip() if span_tag else ""

            # 3. Hoster (Index 2) - Icons extrahieren
            hoster_td = cols[2]
            # Wir holen die 'title' Attribute der <i> Tags (VOE, Filemoon, etc.)
            hoster_liste = [i['title'] for i in hoster_td.find_all('i', class_='icon') if i.has_attr('title')]

            out.append({
                "id": ep_id,
                "folge": int(nr_text.split()[-1]) if " " in nr_text else nr_text,
                "name": name_de,
                "name2": name_en,
                "hoster": hoster_liste
            })
    return out



def get_all_episodes(slug):
    base_url = "https://aniworld.to"
    start_url = f"{base_url}/anime/stream/{slug}"
    
    # Damit der Server denkt, wir sind ein normaler User
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    full_data = {}
    
    response = requests.get(start_url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        sessions = extract_sessions(soup)
        
        for session in sessions:
            print(f"Scrape {session['name']}...")
            url = f"{base_url}{session['path']}"
            
            try:
                res = requests.get(url, headers=headers, timeout=10)
                if res.status_code == 200:
                    s_soup = BeautifulSoup(res.text, 'html.parser')
                    full_data[session['name']] = extract_episodes(s_soup)
                
                # WICHTIG: Kurze Pause zwischen 1 und 3 Sekunden würfeln
                wait_time = random.uniform(1.0, 3.0)
                time.sleep(wait_time)
                
            except requests.exceptions.RequestException as e:
                print(f"Fehler bei {session['name']}: {e}")
                continue # Weiter zur nächsten Staffel, falls eine mal klemmt
        
        return full_data
        print("Fertig!")
        
def get_sessions_by_slug(slug):
    base_url = "https://aniworld.to"
    url = f"{base_url}/anime/stream/{slug}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        return extract_sessions(soup)
    else:
        print(f"Fehler beim Abrufen der Sessions: Status Code {response.status_code}")
        return []

def get_episodes_by_link(link):
    base_url = "https://aniworld.to"
    url = f"{base_url}{link}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        soup = BeautifulSoup(response.text, 'html.parser')
        return extract_episodes(soup)
    else:
        print(f"Fehler beim Abrufen der Episoden: Status Code {response.status_code}")
        return []



def extract_cast(soup: BeautifulSoup):
    cast_info = {
        "actors": [],
        "directors": [],
        "producers": []
    }
    
    cast_container_ul = soup.find("div", class_="cast").find("ul")
    if not cast_container_ul:
        return None
    

    for outer_li in cast_container_ul.find_all("li", recursive=False):
        strong_tag = outer_li.find("strong")
        if not strong_tag:
            continue

        label = strong_tag.get_text(strip=True)

        # Wir suchen das <ul> mit den Namen
        inner_ul = outer_li.find("ul")
        if not inner_ul:
            continue

        # Wir sammeln alle Namen in einer Liste, aber NUR wenn ein <a> und <span> da ist
        names = []
        for inner_li in inner_ul.find_all("li"):
            # Sicherer Check: Existiert das a-Tag und hat es einen Namen?
            name_tag = inner_li.find("span", itemprop="name")
            if name_tag:
                name = html.unescape(name_tag.get_text(strip=True))
                names.append(name)

        # Zuweisung basierend auf dem Label
        if "Regisseure:" in label:
            cast_info["directors"] = names
        elif "Schauspieler:" in label:
            cast_info["actors"] = names
        elif "Produzent:" in label:
            cast_info["producers"] = names
    
    return cast_info
    
def get_details(target):
    base_url = "https://aniworld.to"
    
    # Flexibler URL-Bau: Falls 'target' schon ein Link ist, nutzen; sonst als Slug bauen
    if target.startswith("/"):
        anime_url = f"{base_url}{target}"
    else:
        anime_url = f"{base_url}/anime/stream/{target}"
        
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url=anime_url, headers=headers, timeout=10)
        if response.status_code != 200:
            return {"error": f"AniWorld returned status {response.status_code}"}
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # --- Metadata Extraction ---
        # Titel (meistens in h1)
        title = soup.find('h1').get_text(strip=True) if soup.find('h1') else "Unknown"
        
        # Beschreibung (Plot)
        description = soup.find('p', class_='seri_des')
        description_text = description.get_attribute_list("data-full-description", "Keine Beschreibung gefunden.")
        
        # Cover-URL
        img_tag = soup.find('div', class_='seriesCoverBox').find("img")
        cover_url = f"{base_url}{img_tag['data-src']}" 
        
        # Genres
        genres = [a.get_text(strip=True) for a in soup.select('.genres ul li a')]
        
        # Rating & Jahr (aus dem Stats-Bereich)
        rating_val = soup.find('span', {'itemprop': 'ratingValue'})
        year = f"{soup.find('span', {"itemprop": "startDate"}).find("a").get_text(strip=True)}/{soup.find("span", {"itemprop": "endDate"}).find("a").get_text(strip=True)}"

        series_id = soup.find("div", class_="add-series")["data-series-id"]
        
        
        cast = extract_cast(soup)
        
        
        
        return {
            "title": title,
            "description": description_text,
            "cover": cover_url,
            "genres": genres,
            "rating": int(rating_val.get_text(strip=True)) if rating_val else "N/A",
            "year": year if year else "N/A",
            "slug": target.split('/')[-1],
            "series_id": int(series_id) if series_id else "notFound",
            "cast": cast
        }
        
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def search_anime(keyword):
    url = f"https://aniworld.to/ajax/seriesSearch?keyword={quote(keyword)}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers)
        returns = []
        if response.status_code == 200:
            for item in response.json():
                description = html.unescape(item['description'])
                name = html.unescape(item['name'])
                cover = item['cover'].replace("150x225", "220x330")
                returns.append({"cover": f"https://aniworld.to{cover}", "name": name, "link": item['link'], "description": description})
            return returns
        else:
            print(f"Fehler bei der Suche: Status Code {response.status_code}")
            return None
    except requests.exceptions.RequestException as e:
        print(f"Fehler bei der Suche: {e}")
        return None



def markdown_to_json(md_text):
    data = {}
    current_category = None
    
    # Zeilenweise durchgehen
    for line in md_text.splitlines():
        line = line.strip()
        if not line:
            continue
            
        # Check: Ist es ein Hoster-Eintrag? (Beginnt mit -)
        if line.startswith("-"):
            # Wir splitten am Pfeil "->"
            parts = line.split("->")
            if len(parts) == 2 and current_category:
                # Name säubern (das "-" vorne weg)
                hoster_name = parts[0].replace("-", "").strip()
                link = parts[1].strip()
                
                data[current_category].append({
                    "name": hoster_name,
                    "link": link
                })
        else:
            # Es ist eine neue Kategorie (Sprache)
            current_category = line
            if current_category not in data:
                data[current_category] = []
                
    return data


def get_redirect_json(link):
    base_url = "https://aniworld.to"
    url = base_url + link
    
    episode = AniworldEpisode(url)
    
    streams_dict = markdown_to_json(str(episode.provider_data))
    return streams_dict


def check_hoster_validity(json_data, lang, sub, hoster):
    # 1. Den passenden Key im JSON finden
    # Logik: Wenn sub None/Leer -> "German audio", sonst "Japanese audio + German subtitles"
    if lang == "German" and (sub is None or sub == ""):
        search_key = "German audio"
    else:
        search_key = f"{lang} audio + {sub} subtitles"

    # 2. Prüfen, ob dieser Sprach-Key überhaupt im JSON existiert
    if search_key not in json_data:
        return False, f"Sprachkombination '{search_key}' nicht verfügbar."

    # 3. Die Liste der Hoster nach dem Namen durchsuchen
    hoster_list = json_data[search_key]
    # Wir nutzen 'any', um effizient zu prüfen
    is_valid = any(item['name'].lower() == hoster.lower() for item in hoster_list)

    if is_valid:
        # Den konkreten Link extrahieren
        link = next(item['link'] for item in hoster_list if item['name'].lower() == hoster.lower())
        return True, link
    
    return False, "Hoster für diese Sprache nicht gefunden."

def get_m3u8_link(link):
    episode_url = f"https://aniworld.to{link}"
    language = (Audio.GERMAN, Subtitles.NONE)
    provider_name = "VOE"
    episode = AniworldEpisode(episode_url)
    
    redirect_link = None
    for key, providers in episode.provider_data._data.items():
        if key[0].value == language[0].value and key[1].value == language[1].value:
            redirect_link = providers.get(provider_name)
            break

    if redirect_link:
        from aniworld.config import GLOBAL_SESSION
        try:
            real_hoster_url = GLOBAL_SESSION.get(redirect_link).url
            get_link_func = provider_functions[f"get_direct_link_from_{provider_name.lower()}"]
            return get_link_func(real_hoster_url)
        except Exception as e:
            print(f"Fehler: {e}")
    return None

    
    



def fix_m3u8_on_the_fly(content, base_url, proxy_url_prefix):
    """Beseitigt Hoster-Parameter und biegt Links auf das eigene Backend um."""
    fixed_lines = []
    for line in content.splitlines():
        line = line.strip()
        if not line: continue
        
        if not line.startswith('#'):
            # Absolute URL vom Hoster bauen
            full_url = line if line.startswith('http') else urljoin(base_url, line)
            # Wir hängen die originale Hoster-URL als Query-Parameter an unseren Proxy an
            # So müssen wir lokal absolut nichts zwischenspeichern!
            fixed_lines.append(f"{proxy_url_prefix}?remote_url={full_url}")
            
        elif 'URI="' in line:
            match = re.search(r'URI="([^"]+)"', line)
            if match:
                original_uri = match.group(1)
                full_url = original_uri if original_uri.startswith('http') else urljoin(base_url, original_uri)
                line = line.replace(original_uri, f"{proxy_url_prefix}?remote_url={full_url}")
            fixed_lines.append(line)
        else:
            fixed_lines.append(line)
    return "\n".join(fixed_lines)