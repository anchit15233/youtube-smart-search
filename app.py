import streamlit as st
import requests
from dateutil import parser
import re

st.set_page_config(page_title="YouTube Smart Search", page_icon="🔎")
st.title("🔎 YouTube Smart Search – Level + Exam Filters")

api_key = st.secrets.get("YOUTUBE_API_KEY")

# ---------- UI ----------
query = st.text_input("Enter a topic (e.g. linear algebra, biryani recipe)")
c1, c2, c3 = st.columns(3)
with c1:
    max_minutes = st.slider("Max duration (minutes)", 5, 60, 30)
with c2:
    level_pref = st.selectbox("Level", ["Any", "Beginner", "Intermediate", "Advanced"])
with c3:
    need_captions = st.checkbox("Must have subtitles/captions")

exam_pref = st.multiselect(
    "Exam focus (optional)",
    ["NEET", "JEE", "GATE", "IIT JAM", "CAT"],
    default=[]
)

# ---------- Helpers ----------
def iso8601_to_seconds(iso_dur: str) -> int:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_dur or "")
    if not m: return 0
    h = int(m.group(1) or 0); mn = int(m.group(2) or 0); s = int(m.group(3) or 0)
    return h*3600 + mn*60 + s

# Level classification (rule-based)
BEGINNER_KWS = {"beginner","intro","introduction","basics","from scratch","for beginners","no prerequisite","no prerequisites","getting started","crash course"}
ADVANCED_KWS = {"advanced","proof","rigorous","derivation","theorem","spectral theorem","measure theory","graduate","research"}
INTERMEDIATE_HINTS = {"intermediate","in-depth","detailed","comprehensive"}
PRACTICAL_PLUS = {"example","examples","exercise","project","hands-on","step-by-step","application","apply","practice"}
THEORY_PLUS = {"theorem","axiom","proof","derivation","lemma"}

def classify_level(text: str) -> str:
    t = text.lower()
    if any(k in t for k in BEGINNER_KWS): return "Beginner"
    if any(k in t for k in ADVANCED_KWS): return "Advanced"
    if any(k in t for k in INTERMEDIATE_HINTS): return "Intermediate"
    theory_hits = sum(t.count(k) for k in THEORY_PLUS)
    practical_hits = sum(t.count(k) for k in PRACTICAL_PLUS)
    if theory_hits - practical_hits >= 2: return "Advanced"
    if practical_hits >= 2: return "Beginner"
    return "Intermediate"

# Exam keywords (title/description)
EXAM_KWS = {
    "NEET": {"neet","neet ug","neet 2025","biology neet","physics neet","chemistry neet","ncert","pyq","previous year","mock test","neet preparation","neet exam","neet syllabus"},
    "JEE": {"jee","jee main","jee mains","jee advanced","jee adv","iit jee","mains","advanced","pyq","previous year","mock test","rank booster","ncert"},
    "GATE": {"gate","gate exam","gate 2025","gate previous year","pyq","mock test","gate syllabus","gate preparation"},
    "IIT JAM": {"iit jam","jam exam","jam physics","jam chemistry","jam mathematics","pyq","previous year","mock"},
    "CAT": {"cat","cat exam","cat 2025","verbal ability","dilr","quant","mock","previous year","slot 1","slot 2","slot 3"}
}

def detect_exams(text: str):
    t = text.lower()
    hits = []
    for exam, kws in EXAM_KWS.items():
        if any(k in t for k in kws):
            hits.append(exam)
    return hits  # list of exams this video seems relevant for

@st.cache_data(ttl=900, show_spinner=False)
def yt_search(api_key: str, q: str, max_results: int = 25):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {"part": "snippet", "q": q, "type": "video", "maxResults": max_results, "key": api_key}
    r = requests.get(url, params=params, timeout=20); r.raise_for_status()
    items = r.json().get("items", [])
    return [it["id"]["videoId"] for it in items]

@st.cache_data(ttl=900, show_spinner=False)
def yt_videos(api_key: str, ids: list[str]):
    if not ids: return []
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {"part": "contentDetails,statistics,snippet", "id": ",".join(ids), "key": api_key}
    r = requests.get(url, params=params, timeout=20); r.raise_for_status()
    return r.json().get("items", [])

# ---------- Main ----------
if st.button("Search") and query:
    if not api_key:
        st.error("No API key found. Add YOUTUBE_API_KEY in Settings → Secrets, then rerun.")
        st.stop()

    try:
        video_ids = yt_search(api_key, query, max_results=25)
        items = yt_videos(api_key, video_ids)
    except requests.HTTPError as e:
        st.error(f"API error: {e}"); st.stop()
    except requests.RequestException as e:
        st.error(f"Network error: {e}"); st.stop()

    results = []
    for v in items:
        vid = v.get("id")
        sn = v.get("snippet", {})
        cd = v.get("contentDetails", {})
        stats = v.get("statistics", {})

        title = sn.get("title", "Untitled")
        desc = (sn.get("description") or "")
        text = f"{title}\n{desc}"

        dur_s = iso8601_to_seconds(cd.get("duration", "PT0S"))
        has_captions = cd.get("caption", "false") == "true"
        level = classify_level(text)
        exams = detect_exams(text)

        if dur_s <= max_minutes*60 and (not need_captions or has_captions):
            results.append({
                "title": title,
                "channel": sn.get("channelTitle", "Unknown"),
                "published": parser.parse(sn["publishedAt"]).date().isoformat() if sn.get("publishedAt") else "",
                "video_id": vid,
                "duration_min": max(1, dur_s // 60),
                "has_captions": has_captions,
                "views": int(stats.get("viewCount", 0)) if stats.get("viewCount") else 0,
                "level": level,
                "exams": exams,
                "why_text": text[:400]
            })

    # Apply filters
    def level_match(l): return (level_pref == "Any") or (l == level_pref)
    def exam_match(es): 
        return (not exam_pref) or any(e in es for e in exam_pref)

    filtered = [r for r in results if level_match(r["level"]) and exam_match(r["exams"])]

    if not filtered:
        st.info("No videos matched your filters. Try relaxing Level/Exams or increasing duration.")
    else:
        # Ranking: captions, exam match count, level match, shorter, views
        def rank_key(r):
            caps = 1 if r["has_captions"] else 0
            exam_hits = sum(1 for e in r["exams"] if e in exam_pref) if exam_pref else 0
            lvl = 1 if level_match(r["level"]) else 0
            return (-caps, -exam_hits, -lvl, r["duration_min"], -r["views"])
        filtered.sort(key=rank_key)

        for i, r in enumerate(filtered, 1):
            url = f"https://www.youtube.com/watch?v={r['video_id']}"
            caps = "✅" if r["has_captions"] else "❌"
            exams_badge = (" · " + ", ".join(r["exams"])) if r["exams"] else ""
            st.markdown(
                f"**{i}. [{r['title']}]({url})**  \n"
                f"_Level: {r['level']}{exams_badge} · Captions {caps}_  \n"
                f"Channel: {r['channel']} · {r['duration_min']} min · Views: {r['views']:,} · Published: {r['published']}"
            )
            with st.expander("Why this matched"):
                exams_txt = ", ".join(r["exams"]) if r["exams"] else "None detected"
                st.write(
                    f"- **Level** → {r['level']}\n"
                    f"- **Exams detected** → {exams_txt}\n"
                    f"- **Captions** → {caps}\n"
                    f"- **Snippet scanned**:\n\n{r['why_text']}..."
                )


