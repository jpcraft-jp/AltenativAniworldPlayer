from aniworld.config import Audio, Subtitles
from aniworld.models import AniworldEpisode
from aniworld.extractors import provider_functions
import hashlib
import json
import re
import requests


LOCAL_API_BASE = "http://localhost:5000/api/video/stream"

def get_hash(text):
    """Erzeugt eine eindeutige ID (MD5) aus dem Link."""
    return hashlib.md5(text.encode()).hexdigest()

def clean_url(url):
    """Entfernt Query-Parameter (?t=...) von einer URL."""
    return url.split('?')[0]


def get_m3u8_link(link):
    """Extrahiert den originalen Master-Link direkt aus den Rohdaten."""
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
            print(f"Fehler beim Auflösen: {e}")
    return None

def rewrite_playlist(content, base_url, local_api_prefix):
    """Säubert URLs und schreibt sie auf localhost um."""
    fixed_lines = []
    for line in content.splitlines():
        line = line.strip()
        if not line: continue
        
        # Fall 1: Pfad (Sub-Playlist oder Segment)
        if not line.startswith('#'):
            full_url = clean_url(line if line.startswith('http') else base_url + line)
            file_name = full_url.split('/')[-1]
            fixed_lines.append(f"{local_api_prefix}/{file_name}")
            
        # Fall 2: URI-Attribut
        elif 'URI="' in line:
            match = re.search(r'URI="([^"]+)"', line)
            if match:
                original_uri = match.group(1)
                full_url = clean_url(original_uri if original_uri.startswith('http') else base_url + original_uri)
                file_name = full_url.split('/')[-1]
                line = line.replace(original_uri, f"{local_api_prefix}/{file_name}")
            fixed_lines.append(line)
        else:
            fixed_lines.append(line)
            
    return "\n".join(fixed_lines)

def process_episode(episode_link):
    episode_id = get_hash(episode_link)

    local_api_prefix = f"{LOCAL_API_BASE}/{episode_id}"

    print(f"Verarbeite: {episode_link} (ID: {episode_id})")
    
    master_url = get_m3u8_link(episode_link)
    if not master_url:
        print("Master URL konnte nicht gefunden werden.")
        return

    # Basis-URL vom Hoster (wichtig für Segmente)
    base_url = master_url.rsplit('/', 1)[0] + '/'

    response = requests.get(master_url)
    if response.status_code == 200:
        # 1. Master Playlist fixen
        fixed_master = rewrite_playlist(response.text, base_url, local_api_prefix)
        return fixed_master

        # 2. Sub-Playlists finden und fixen
        sub_playlists = re.findall(r'(index-[^? \n]+)', response.text)
        for sub in sub_playlists:
            # Download mit originalen Parametern
            sub_url_full = master_url.replace("master.m3u8", sub)
            sub_res = requests.get(sub_url_full)
            if sub_res.status_code == 200:
                fixed_sub = rewrite_playlist(sub_res.text, base_url, local_api_prefix)
                clean_sub_name = clean_url(sub).split('/')[-1]
                with open(episode_folder / clean_sub_name, "w", encoding="utf-8") as f:
                    f.write(fixed_sub)

        # 3. Index speichern
        update_index(episode_link, {
            "id": episode_id,
            "original_base_url": base_url,
            "local_path": str(episode_folder),
            "master_file": "master.m3u8"
        })
        
        print(f"Erfolg! Player-URL: {local_api_prefix}/master.m3u8")

if __name__ == "__main__":
    test_link = "/anime/stream/highschool-dxd/staffel-1/episode-1"
    process_episode(test_link)