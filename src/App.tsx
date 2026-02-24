import './App.css'
import "./AnimeCard.css"
import { useState, useRef, useEffect } from 'react'
import Hls from 'hls.js'
import menu from "./assets/menu.svg"
import close from "./assets/close.svg"

// 1. Namen groß schreiben!
function MainPage() {
  return (
    <main className="main-content">
      <h1>Willkommen zurück!</h1>
      <p>Wähle einen Anime aus deiner Liste von über 90 Titeln.</p>
    </main>
  )
}

interface VideoPlayerProps {
  slug: string;
  videoPath: string;
  onNextEpisode?: () => void; // Neue Prop für den Button/Auto-Next
}

const VideoPlayer: React.FC<VideoPlayerProps> = ({ slug, videoPath, onNextEpisode }) => {
  const videoRef = useRef<HTMLVideoElement>(null);
  const hlsRef = useRef<Hls | null>(null);
  const storageKey = `progress_${slug}_${videoPath.replace(/\//g, "_")}`;

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const masterUrl = `http://localhost:5000/api/video/stream/master/${slug}/${videoPath}`;
    
    // Cleanup alte Instanz
    if (hlsRef.current) {
      hlsRef.current.destroy();
    }

    if (Hls.isSupported()) {
      const hls = new Hls();
      hls.loadSource(masterUrl);
      hls.attachMedia(video);
      hlsRef.current = hls;

      hls.on(Hls.Events.MANIFEST_PARSED, () => {
        // Fortschritt wiederherstellen
        const savedTime = localStorage.getItem(storageKey);
        if (savedTime) video.currentTime = parseFloat(savedTime);
        
        // Autoplay (stummgeschaltet startet zuverlässiger)
        video.play().catch(() => console.log("User muss erst klicken"));
      });
    } 
    else if (video.canPlayType('application/vnd.apple.mpegurl')) {
      // Safari Support
      video.src = masterUrl;
    }

    // Fortschritt speichern
    const saveProgress = () => {
      if (video.currentTime > 5) {
        localStorage.setItem(storageKey, video.currentTime.toString());
      }
    };

    video.addEventListener('timeupdate', saveProgress);
    video.addEventListener('ended', () => onNextEpisode?.());

    return () => {
      video.removeEventListener('timeupdate', saveProgress);
      if (hlsRef.current) hlsRef.current.destroy();
    };
  }, [slug, videoPath]);

  return (
    <div className="native-player-container" style={{ width: '100%', position: 'relative' }}>
      <video
        ref={videoRef}
        controls
        playsInline
        style={{
          width: '100%',
          aspectRatio: '16 / 9',
          backgroundColor: '#000',
          borderRadius: '12px',
          boxShadow: '0 4px 20px rgba(0,0,0,0.5)'
        }}
      />
      
      {onNextEpisode && (
        <button 
          onClick={onNextEpisode}
          style={{
            position: 'absolute',
            right: '20px',
            bottom: '60px',
            zIndex: 10,
            padding: '10px 15px',
            background: 'rgba(255,255,255,0.2)',
            border: 'none',
            color: 'white',
            borderRadius: '50%',
            cursor: 'pointer',
            backdropFilter: 'blur(5px)'
          }}
        >
          ➔
        </button>
      )}
    </div>
  );
};

interface AnimeSearchResult {
  name: string;
  link: string;
  cover: string;
  description: string;
}

interface AnimeCardProps extends AnimeSearchResult {
  onClick: () => void;
}

function AnimeCard({ name, cover, description, onClick }: AnimeCardProps) {
  return (
    <div onClick={() => onClick()} className='AnimeCard'>
      <img onClick={() => onClick()} src={`${cover}`} alt="cover" className='AnimeCover' />
      <div onClick={() => onClick()} className='AnimeDetails'>
        <h3 onClick={() => onClick()} className='AnimeTitle'>{name}</h3>
        <p onClick={() => onClick()}>{description}</p>
      </div>
    </div>
  )
}

interface AnimeData {
  title: string,
  description: string,
  cover: string,
  genres: string[],
  rating: number,
  year: string,
  slug: string,
  series_id: number,
  cast: {
    actors: string[],
    directors: string[],
    producers: string[]
  }
}

interface Sessions {
  sessions: {
    name: string,
    path: string,
    selected?: boolean
  }[]
}

interface Episode {
  folge: number;
  id: string;
  name: string;
  name2: string;
  hoster: string[];
}




function Anime() {
  const href = location.hash.replace("#", "");
  const [animeData, setAnimeData] = useState<AnimeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [sessionList, setSessionList] = useState<Sessions | null>(null);
  const [activeSessionPath, setActiveSessionPath] = useState<string | null>(null);
  const [activeEpisodeNumber, setActiveEpisodeNumber] = useState<number>(1);
  
  // HIER: Nur die DATEN speichern, nicht das DIV
  const [episodes, setEpisodes] = useState<Episode[]>([]);
  const [episodesLoading, setEpisodesLoading] = useState(false);

  // Effekt 1: Anime Details & Sessions laden
  useEffect(() => {
    if (!href) return;
    const fetchData = async () => {
      setLoading(true);
      try {
        const [detailRes, sessionRes] = await Promise.all([
          fetch(`http://localhost:5000/api/details?slug=${encodeURIComponent(href)}`),
          fetch(`http://localhost:5000/api/sessions?slug=${encodeURIComponent(href)}`, { method: 'POST' })
        ]);
        const detailData = await detailRes.json();
        const sessData = await sessionRes.json();
        setAnimeData(detailData);
        setSessionList(sessData);
        if (sessData?.sessions?.length > 0) {
          setActiveSessionPath(sessData.sessions[0].path);
        }
      } catch (e) { console.error(e); } finally { setLoading(false); }
    };
    fetchData();
  }, [href]);

  // Effekt 2: Episoden laden, wenn sich activeSessionPath ändert
  useEffect(() => {
    if (!activeSessionPath) return;
    const fetchEpisodes = async () => {
      setEpisodesLoading(true);
      try {
        // API Endpoint wie von dir gewünscht
        const res = await fetch(`http://localhost:5000/api/episodes?link=${encodeURIComponent(activeSessionPath)}`, {method: "POST"});
        const data = await res.json();
        setEpisodes(data.episodes || []);
      } catch (e) { console.error(e); } finally { setEpisodesLoading(false); }
    };
    fetchEpisodes();
  }, [activeSessionPath]);

  if (loading) return <main className="main-content">Lade Anime Details...</main>;
  if (!animeData) return <main className="main-content">Anime nicht gefunden.</main>;
  const sessionSlug = activeSessionPath?.split("/").at(-1) || "";

  const handleNext = () => {
  const nextEp = activeEpisodeNumber + 1;
  // Check ob die Folge in deiner episodes-Liste existiert
  if (episodes.some(e => e.folge === nextEp)) {
    setActiveEpisodeNumber(nextEp);
  }
};

  return (
    <main className="main-content">
      <div className='AnimeSiteDetails'>
        <img src={animeData.cover} alt="Cover" className="detail-cover" />
        <div className='detail-text-box'>
          <h3 className='AnimeDetailTitle'>{animeData.title} <span className='year'>({animeData.year})</span></h3>
          <div className='grenes'>
            {animeData.genres.map((genre) => (
              <div key={genre} className={`genre-badge ${genre.toLowerCase()}`}>
                <p>{genre}</p>
              </div>
            ))}
          </div>
          <div className='detail-description-box'><p className="description">{animeData.description}</p></div>
        </div>
      </div>

      <div className='AnimeEpisodesAndSessions'>
        <div className='session-list'>
          {sessionList?.sessions.map((session) => (
            <div
              key={session.path}
              className={`session-item ${activeSessionPath === session.path ? "selected" : ""}`}
              onClick={() => setActiveSessionPath(session.path)} // Nur Path setzen, useEffect regelt den Rest!
            >
              <h4>{session.name === "Filme" ? "Filme" : `Staffel ${session.name}`}</h4>
            </div>
          ))}
        </div>

        {/* Hier werden die Episoden gerendert */}
        {episodesLoading ? (
          <div className="loading-ep">Lade Episoden...</div>
        ) : (
          <div className="session-list">
            {episodes?.map((ep) => (
              <div key={ep.id} className={`session-item ${activeEpisodeNumber === ep.folge ? "selected" : ""}`} onClick={() => {setActiveEpisodeNumber(ep.folge)}}>
                <h4>{ep.folge}</h4>
              </div>
            ))}
          </div>
        )}
      </div>
        <div className='EpisodeVideoPlayer-box'> 
          <VideoPlayer slug={animeData.slug} videoPath={`${sessionSlug}/${sessionSlug === "filme" ? `film-${activeEpisodeNumber}` : `episode-${activeEpisodeNumber}`}`} onNextEpisode={handleNext}></VideoPlayer>
        </div>
    </main>
  );
}




function SearchPage() {
  const [keyword, setKeyword] = useState('');
  const [results, setResults] = useState<AnimeSearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchiner, setSerchinger] = useState(false)

  async function searchAnime(e: React.FormEvent) {
    e.preventDefault(); // Verhindert das Neuladen der Seite
    if (!keyword.trim()) return;

    setLoading(true);
    try {
      // WICHTIG: Nutze die URL deines Flask-Backends
      // Wir senden keyword als Query-Parameter, da dein Backend request.args.get nutzt
      const response = await fetch(`http://localhost:5000/api/search?keyword=${encodeURIComponent(keyword)}`, {
        method: 'GET', // Dein Backend erwartet POST laut Code oben
      });

      const data = await response.json();
      setResults(data.results || []);
    } catch (error) {
      console.error("Suche fehlgeschlagen:", error);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="main-content search-container">
      <h1>Anime Suche</h1>

      <form onSubmit={searchAnime} className="search-form">
        <div className='search-bar-box'>
          <label htmlFor="keyword" className={`search-placeholder ${searchiner || keyword ? "open" : ""}`}>Search</label>
          <input
            onFocus={() => setSerchinger(true)}
            onBlur={() => setSerchinger(false)}
            type="text"
            className="search-input"
            id='keyword'
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
        </div>
        <button type="submit" className="search-button">
          {loading ? 'Suche...' : 'Suchen'}
        </button>
      </form>

      <div className="results-grid">
        {results.map((anime, index) => (
          <AnimeCard
            onClick={() => { window.setCurrentPage("anime"); location.hash = anime.link }}
            key={index}
            name={anime.name}
            cover={anime.cover}
            description={anime.description}
            link={anime.link}
          />
        ))}
      </div>
    </main>
  );
}


declare global {
  interface Window {
    setCurrentPage: (name: string) => void
  }
}

function App() {
  const [sidebar, setSidebar] = useState(false);
  // 2. Nutze einen String als ID für die aktuelle Seite
  const [currentPage, setCurrentPage] = useState('anime');

  useEffect(() => {
    window.setCurrentPage = (name) => {
      setCurrentPage(name)
    }
  }, [])

  const menuItems = [
    { id: 'main', label: 'Home' },
    { id: 'search', label: 'Anime Suche' },
    { id: 'trending', label: 'Trending' },
    { id: 'watchlist', label: 'Meine Liste' },
  ];

  // Helper-Funktion zum Rendern des Contents
  const renderContent = () => {
    switch (currentPage) {
      case 'search': return <SearchPage />;
      case 'main': return <MainPage />;
      case "anime": return <Anime />
      default: return <MainPage />;
    }
  };

  return (
    <div className="app-container">
      <div className='hadbar'>
        <img
          src={menu}
          alt="menu"
          className='hadbar_icon'
          onClick={() => setSidebar(true)}
        />
        <span onClick={() => setCurrentPage("main")} className="brand-name">AniWatchings <span className="dev-tag">v1.0</span></span>
      </div>

      <div className={`sidebar ${sidebar ? "open" : ""}`}>
        <div className="sidebar-header">
          <img
            src={close}
            alt="close"
            id='sidebar_icon_close'
            onClick={() => setSidebar(false)}
          />
        </div>

        <div className='menueintragbox'>
          <div className='menueintrag title-section'>
            <h2 id='menutitle'>Navigation</h2>
          </div>

          {menuItems.map((item) => (
            <div
              key={item.id}
              onClick={() => {
                setCurrentPage(item.id); // Seite wechseln
                setSidebar(false);       // Sidebar schließen
              }}
              className={`menueintrag link-item ${currentPage === item.id ? 'active' : ''}`}
            >
              {item.label}
            </div>
          ))}
        </div>
      </div>

      {sidebar && <div className="overlay" onClick={() => setSidebar(false)} />}

      {/* Hier wird die Seite dynamisch gerendert */}
      {renderContent()}

    </div>
  )
}

export default App