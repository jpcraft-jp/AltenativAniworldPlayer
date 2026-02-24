from flask import Flask, jsonify, request, abort, Response, stream_with_context
from flask_cors import CORS
from aniworld_compatibility import AniworldCompatibility
import aniworld
import requests
from urllib.parse import urljoin, quote
import re

app = Flask(__name__)
CORS(app)
LOCAL_API_BASE = "http://localhost:5000/api/video/stream"
aniworld = AniworldCompatibility()

@app.route('/')
def hello_world():
    return 'Hello, World!'

@app.route('/api/version')
def api_version():
    return jsonify({'version': '1.0.0'})

@app.route('/api/search', methods=['GET'])
def api_search():
    keyworld = request.args.get('keyword', '')
    print(keyworld)
    animelist = aniworld.aniworldkram.search_anime(keyworld)
    return jsonify({'results': animelist})

@app.route('/api/sessions', methods=['POST'])
def api_sessions():
    slug = request.args.get('slug', '')
    sessions = aniworld.aniworldkram.get_sessions_by_slug(slug)
    return jsonify({'sessions': sessions})

@app.route('/api/episodes', methods=['POST'])
def api_episodes():
    link = request.args.get('link', '')
    episodes = aniworld.aniworldkram.get_episodes_by_link(link)
    return jsonify({'episodes': episodes})

@app.route("/api/details", methods=["GET"])
def api_details():
    slug = request.args.get('slug')
    link = request.args.get('link')

    # Logik: Wenn Link da ist, extrahiere den Slug daraus (oder nutze den Link direkt)
    if link:
        pass
    
    elif slug:
        link = f"/anime/stream/{slug}"
    else:
        return jsonify({'error': 'Weder Slug noch Link angegeben'}), 400

    details = aniworld.aniworldkram.get_details(link)
    return jsonify(details)


def clean_url(url):
    """Entfernt Query-Parameter (?t=...) von einer URL."""
    return url.split('?')[0]
def patch_m3u8(content, base_url):
    """
    Unterscheidet zwischen Sub-Playlists und Video-Segmenten.
    """
    local_m3u8_api = "http://localhost:5000/api/video/stream/m3u8"
    
    fixed_lines = []
    
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
            
        if not line.startswith('#'):
            # Erstelle die volle URL zum Hoster (inkl. Parametern)
            full_url = line if line.startswith('http') else urljoin(base_url, line)
            
            # Prüfen: Ist es eine Playlist oder ein Segment?
            if ".m3u8" in line.split('?')[0]:
                # Rekursiver Aufruf: Diese Playlist muss auch gepatcht werden
                fixed_lines.append(f"{local_m3u8_api}?remote_url={quote(full_url)}")
            else:
                # Es ist ein .ts Segment -> Ab zum Streaming-Proxy
                fixed_lines.append(full_url)
                
        elif 'URI="' in line:
            # Das gleiche für URIs (z.B. in #EXT-X-STREAM-INF)
            match = re.search(r'URI="([^"]+)"', line)
            if match:
                original_uri = match.group(1)
                full_url = original_uri if original_uri.startswith('http') else urljoin(base_url, original_uri)
                
                if ".m3u8" in original_uri.split('?')[0]:
                    new_uri = f"{local_m3u8_api}?remote_url={quote(full_url)}"
                else:
                    new_uri = full_url
                    
                line = line.replace(original_uri, new_uri)
            fixed_lines.append(line)
        else:
            fixed_lines.append(line)
            
    return "\n".join(fixed_lines)


@app.route("/api/video/stream/master/<slug>/<session>/<episode>")
def masterm3u8(slug, session, episode):
    # 1. Den echten Master-Link über deinen Scraper extrahieren
    # Wir bauen den Pfad so zusammen, wie deine Library ihn erwartet
    episode_path = f"/anime/stream/{slug}/{session}/{episode}"
    
    try:
        master_url = aniworld.aniworldkram.get_m3u8_link(episode_path)
        
        if not master_url:
            return jsonify({'error': 'Master-Link konnte nicht gefunden werden (Provider evtl. offline)'}), 404

        # 2. Den Master-Inhalt vom Hoster laden
        # Wichtig: Referer mitsenden, sonst blockt der Hoster sofort
        headers = {"Referer": "https://voe.sx/"}
        r = requests.get(master_url, headers=headers, timeout=10)
        
        if r.status_code != 200:
            return abort(r.status_code)

        # 3. Den Inhalt patchen
        # Wir brauchen die base_url des Hosters, um relative Pfade in absolute umzuwandeln
        base_url = master_url.rsplit('/', 1)[0] + '/'
        
        # Wir nutzen deine bestehende patch_m3u8 Funktion
        fixed_m3u8 = patch_m3u8(r.text, base_url)
        
        # 4. Als Playlist an den Player zurückgeben
        return Response(fixed_m3u8, mimetype='application/vnd.apple.mpegurl')

    except Exception as e:
        print(f"Fehler in masterm3u8: {e}")
        return abort(500)

@app.route("/api/video/stream/m3u8")
def getm3u8files():
    remote_url = request.args.get("remote_url")
    if not remote_url:
        return abort(400, "Keine remote_url angegeben")
        
    try:
        # Den Master-Link vom Hoster laden
        headers = {
            "Referer": "https://voe.sx/",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        r = requests.get(remote_url, headers=headers, timeout=10)
        
        if r.status_code != 200:
            return abort(r.status_code)
            
        # Basis-URL extrahieren (alles vor dem letzten Slash)
        base_url = remote_url.rsplit('/', 1)[0] + '/'
        
        # Inhalt patchen
        fixed_m3u8 = patch_m3u8(r.text, base_url)
        
        return Response(fixed_m3u8, mimetype='application/vnd.apple.mpegurl')
        
    except Exception as e:
        print(f"Fehler beim M3U8-Patching: {e}")
        return abort(500)
    
    
""" @app.route('/api/video/stream/segment')
def serve_video_file():
    remote_url = request.args.get("remote_url")
    if not remote_url:
        return abort(400)

    try:
        # Request an den Hoster mit Referer-Header (wichtig für VOE)
        r = requests.get(remote_url, stream=True, headers={"Referer": "https://voe.sx/"}, timeout=15)
        
        # Falls der Hoster uns eine weitere Playlist (Sub-Playlist) schickt:
        content_type = r.headers.get('Content-Type', '').lower()
        if "mpegurl" in content_type or remote_url.split('?')[0].endswith('.m3u8'):
            base_url = remote_url.rsplit('/', 1)[0] + '/'
            return Response(patch_m3u8(r.text, base_url), mimetype='application/vnd.apple.mpegurl')

        # Eigentliche Videodaten (.ts) weiterleiten
        def generate():
            for chunk in r.iter_content(chunk_size=32768): # 32KB Chunks für stabilen Stream
                yield chunk

        return Response(
            stream_with_context(generate()),
            content_type=r.headers.get('Content-Type', 'video/MP2T'),
            status=r.status_code
        )
    except Exception as e:
        print(f"Streaming-Proxy-Fehler: {e}")
        return abort(502) """

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
