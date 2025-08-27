import streamlit as st
import requests
from dateutil import parser
import re

st.set_page_config(page_title="YouTube Smart Search", page_icon="🔎")
st.title("🔎 YouTube Smart Search – Study-first Filters")

api_key = st.secrets.get("YOUTUBE_API_KEY")

# ================= UI =================
query = st.text_input("Enter a topic (e.g., linear algebra, vectors, photosynthesis)")

c1, c2, c3 = st.columns(3)
with c1:
    max_minutes = st.slider("Max duration (minutes)", 5, 120, 30)
with c2:
    level_pref = st.selectbox("Level", ["Any", "Beginner", "Intermediate", "Advanced"])
with c3:
    need_captions = st.checkbox("Must have subtitles")

exam_pref = st.multiselect(
    "Exam focus (optional)",
    ["NEET", "JEE", "GATE", "IIT JAM", "CAT"],
    default=[]
)

content_choices = [
    "Concept Lecture",
    "Question Practice / PYQ",
    "Revision / Notes",
    "Full / Crash Course",
    "Syllabus / Strategy",
    "Guidance / Motivation",
]
content_pref = st.multiselect(
    "Content Type (choose one or more)",
    content_choices,
    default=["Concept Lecture", "Question Practice / PYQ", "Revision / Notes", "Full / Crash Course", "Syllabus / Strategy"]
)

show_guidance = st.checkbox("Show Guidance/Motivation", value=False)
include_playlists = st.checkbox("Include Playlists (for full/crash courses)", value=True)

# ================= Helpers =================
def iso8601_to_seconds(iso_dur: str) -> int:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_dur or "")
    if not m: return 0
    h = int(m.group(1) or 0); mn = int(m.group(2) or 0); s = int(m.group(3) or 0)
    return h*3600 + mn*60 + s

# Level classification
BEGINNER_KWS = {"beginner","intro","introduction","basics","from scratch","for beginners","no prerequisite","no prerequisites","getting started","crash course"}
ADVANCED_KWS = {"advanced","proof","rigorous","derivation","theorem","spectral theorem","measure theory","graduate","research"}
INTERMEDIATE_HINTS = {"intermediate","in-depth","detailed","comprehensive"}

def classify_level(text: str) -> str:
    t = text.lower()
    if any(k in t for k in BEGINNER_KWS): return "Beginner"
    if any(k in t for k in ADVANCED_KWS): return "Advanced"
    if any(k in t for k in INTERMEDIATE_HINTS): return "Intermediate"
    return "Intermediate"

# Exam keywords
EXAM_KWS = {
    "NEET": {"neet","neet ug","neet 2025","biology neet","physics neet","chemistry neet","ncert","pyq","previous year","mock test","neet preparation","neet exam","neet syllabus"},
    "JEE": {"jee","jee main","jee mains","jee advanced","jee adv","iit jee","mains","advanced","pyq","previous year","mock test","rank booster","ncert"},
    "GATE": {"gate","gate exam","gate 2025","gate previous year","pyq","mock test","gate syllabus","gate preparation"},
    "IIT JAM": {"iit jam","jam exam","jam physics","jam chemistry","jam mathematics","pyq","previous year","mock"},
    "CAT": {"cat","cat exam","cat 2025","verbal ability","dilr","quant","mock","previous year","slot 1","slot 2","slot 3"}
}
def detect_exams(text: str):
    t = text.lower()
    return [exam for exam, kws in EXAM_KWS.items() if any(k in t for k in kws)]

# Content Type classification
CT = {
    "Concept Lecture": {"lecture","concept","class","lesson","chapter","topic","explain","intuitive","visualize","derivation"},
    "Question Practice / PYQ": {"pyq","previous year","questions","problems","mcq","practice","worksheet","test","mock","quiz","paper","solutions","solution"},
    "Revision / Notes": {"revision","revise","short notes","notes","formula","summary","cheat sheet","one shot","mind map"},
    "Full / Crash Course": {"full course","complete course","crash course","0 to advanced","beginner to advanced","complete playlist","entire syllabus","bootcamp"},
    "Syllabus / Strategy": {"syllabus","blueprint","roadmap","strategy","planner","study plan","time table"},
    "Guidance / Motivation": {"motivation","motivational","journey","rank","strategy talk","how i","how to crack","tips","do this","don’t do","topper talk","mindset"},
}
def classify_content_type(text: str) -> str:
    t = text.lower()
    scores = {name: 0 for name in CT}
    for name, kws in CT.items():
        for k in kws:
            if k in t:
                scores[name] += 1
    ordered = sorted(scores.items(), key=lambda x: (-x[1],
        0 if x[0]=="Concept Lecture" else 1 if x[0]=="Question Practice / PYQ" else 2))
    top, score = ordered[0]
    return top if score > 0 else "Concept Lecture"

def level_match(found: str) -> bool:
    return level_pref == "Any" or found == level_pref

def exams_match(found_list: list[str]) -> bool:
    return (not exam_pref) or any(e in found_list for e in exam_pref)

def content_match(ct: str) -> bool:
    if not show_guidance and ct == "Guidance / Motivation":
        return False
    if not content_pref:
        return True
    return ct in content_pref

# ================= YouTube API =================
@st.cache_data(ttl=900, show_spinner=False)
def yt_search(api_key: str, q: str, type_: str, max_results: int = 30):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {"part": "snippet", "q": q, "type": type_, "maxResults": max_results, "key": api_key}
    r = requests.get(url, params=params, timeout=20); r.raise_for_status()
    return r.json().get("items", [])

@st.cache_data(ttl=900, show_spinner=False)
def yt_videos(api_key: str, ids: list[str]):
    if not ids: return []
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {"part": "contentDetails,statistics,snippet", "id": ",".join(ids), "key": api_key}
    r = requests.get(url, params=params, timeout=20); r.raise_for_status()
    return r.json().get("items", [])

@st.cache_data(ttl=900, show_spinner=False)
def yt_playlists(api_key: str, ids: list[str]):
    if not ids: return []
    url = "https://www.googleapis.com/youtube/v3/playlists"
    params = {"part": "snippet,contentDetails", "id": ",".join(ids), "key": api_key}
    r = requests.get(url, params=params, timeout=20); r.raise_for_status()
    return r.json().get("items", [])

# ================= Main =================
if st.button("Search") and query:
    if not api_key:
        st.error("No API key found. Add YOUTUBE_API_KEY in Settings → Secrets.")
        st.stop()

    # Fetch videos
    try:
        vids = yt_search(api_key, query, "video", 30)
        v_ids = [it["id"]["videoId"] for it in vids]
        v_items = yt_videos(api_key, v_ids)
    except requests.RequestException as e:
        st.error(f"YouTube API error (videos): {e}"); st.stop()

    results = []
    for v in v_items:
        vid = v.get("id")
        sn = v.get("snippet", {}) or {}
        cd = v.get("contentDetails", {}) or {}
        stats = v.get("statistics", {}) or {}

        title, desc = sn.get("title","Untitled"), sn.get("description","")
        text = f"{title}\n{desc}"

        dur_s = iso8601_to_seconds(cd.get("duration","PT0S"))
        has_captions = cd.get("caption","false")=="true"
        level = classify_level(text)
        exams = detect_exams(text)
        ctype = classify_content_type(text)

        if dur_s <= max_minutes*60 and (not need_captions or has_captions):
            if level_match(level) and exams_match(exams) and content_match(ctype):
                results.append({
                    "kind":"video","title":title,"channel":sn.get("channelTitle","Unknown"),
                    "published":parser.parse(sn["publishedAt"]).date().isoformat() if sn.get("publishedAt") else "",
                    "id":vid,"duration_min":max(1,dur_s//60),"has_captions":has_captions,
                    "views":int(stats.get("viewCount",0)) if stats.get("viewCount") else 0,
                    "level":level,"exams":exams,"ctype":ctype,"snippet":text[:500]
                })

    # Fetch playlists if enabled
    playlists = []
    if include_playlists:
        try:
            pls = yt_search(api_key, query+" playlist","playlist",10)
            p_ids = [it["id"]["playlistId"] for it in pls]
            p_items = yt_playlists(api_key, p_ids)
        except requests.RequestException: p_items=[]
        for p in p_items:
            pid = p.get("id")
            psn = p.get("snippet",{}) or {}
            pcd = p.get("contentDetails",{}) or {}
            title, desc = psn.get("title","Untitled"), psn.get("description","")
            text = f"{title}\n{desc}"
            level = classify_level(text)
            exams = detect_exams(text)
            ctype = classify_content_type(text)
            if level_match(level) and exams_match(exams) and content_match(ctype):
                playlists.append({
                    "kind":"playlist","title":title,"channel":psn.get("channelTitle","Unknown"),
                    "published":parser.parse(psn["publishedAt"]).date().isoformat() if psn.get("publishedAt") else "",
                    "id":pid,"itemCount":pcd.get("itemCount",0),
                    "level":level,"exams":exams,"ctype":ctype,"snippet":text[:500]
                })

    combined = results+playlists
    if not combined:
        st.info("No items matched your filters.")
    else:
        def rank_key(r):
            caps = 1 if (r["kind"]=="video" and r.get("has_captions")) else 0
            exam_hits = sum(1 for e in r.get("exams",[]) if e in exam_pref) if exam_pref else 0
            c_boost = 1 if (not content_pref or r["ctype"] in content_pref) else 0
            lvl = 1 if level_match(r.get("level","")) else 0
            dur = r.get("duration_min",999)
            views = r.get("views",0)
            is_playlist = 1 if r["kind"]=="playlist" and r["ctype"]=="Full / Crash Course" else 0
            return (-is_playlist,-c_boost,-caps,-exam_hits,-lvl,dur,-views)

        combined.sort(key=rank_key)

        for i,r in enumerate(combined,1):
            if r["kind"]=="video":
                url=f"https://www.youtube.com/watch?v={r['id']}"
                caps="✅" if r.get("has_captions") else "❌"
                exams_badge=(" · "+", ".join(r["exams"])) if r["exams"] else ""
                st.markdown(
                    f"**{i}. [{r['title']}]({url})**  \n"
                    f"_Type: {r['ctype']} · Level: {r['level']}{exams_badge} · Captions {caps}_  \n"
                    f"Channel: {r['channel']} · {r['duration_min']} min · Views: {r['views']:,} · Published: {r['published']}"
                )
            else:
                url=f"https://www.youtube.com/playlist?list={r['id']}"
                exams_badge=(" · "+", ".join(r["exams"])) if r["exams"] else ""
                st.markdown(
                    f"**{i}. [📚 {r['title']}]({url})**  \n"
                    f"_Playlist · Type: {r['ctype']} · Level: {r['level']}{exams_badge}_  \n"
                    f"Channel: {r['channel']} · Items: {r['itemCount']} · Published: {r['published']}"
                )
            with st.expander("Why this matched"):
                st.write(
                    f"- **Content type** → {r['ctype']}\n"
                    f"- **Level** → {r.get('level','')}\n"
                    f"- **Exams** → {', '.join(r.get('exams', [])) or 'None'}\n"
                    f"- **Snippet scanned**:\n\n{r['snippet']}..."
                )
