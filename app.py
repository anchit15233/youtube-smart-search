import streamlit as st
import requests
from dateutil import parser

st.set_page_config(page_title="YouTube Smart Search (MVP)", page_icon="🔎")
st.title("🔎 YouTube Smart Search – Live YouTube Results")

api_key = st.secrets.get("YOUTUBE_API_KEY")

query = st.text_input("Enter a topic (e.g. linear algebra, biryani recipe)")
max_minutes = st.slider("Max duration (minutes)", 5, 60, 30)
need_captions = st.checkbox("Must have subtitles/captions")

def iso8601_to_seconds(iso_dur: str) -> int:
    import re
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso_dur or "")
    if not m: return 0
    h = int(m.group(1) or 0); mn = int(m.group(2) or 0); s = int(m.group(3) or 0)
    return h*3600 + mn*60 + s

@st.cache_data(ttl=900, show_spinner=False)
def yt_search(api_key: str, q: str, max_results: int = 25):
    url = "https://www.googleapis.com/youtube/v3/search"
    params = {"part": "snippet", "q": q, "type": "video", "maxResults": max_results, "key": api_key}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    items = r.json().get("items", [])
    return [it["id"]["videoId"] for it in items]

@st.cache_data(ttl=900, show_spinner=False)
def yt_videos(api_key: str, ids: list[str]):
    if not ids: return []
    url = "https://www.googleapis.com/youtube/v3/videos"
    params = {"part": "contentDetails,statistics,snippet", "id": ",".join(ids), "key": api_key}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json().get("items", [])

if st.button("Search") and query:
    if not api_key:
        st.error("No API key found. Add YOUTUBE_API_KEY in Settings → Secrets, then rerun.")
        st.stop()

    try:
        video_ids = yt_search(api_key, query, max_results=25)
        items = yt_videos(api_key, video_ids)
    except requests.HTTPError as e:
        st.error(f"API error: {e}. You may have hit quota or misconfigured the key.")
        st.stop()
    except requests.RequestException as e:
        st.error(f"Network error: {e}")
        st.stop()

    results = []
    for v in items:
        vid = v.get("id")
        sn = v.get("snippet", {})
        cd = v.get("contentDetails", {})
        stats = v.get("statistics", {})
        dur_s = iso8601_to_seconds(cd.get("duration", "PT0S"))
        has_captions = cd.get("caption", "false") == "true"

        if dur_s <= max_minutes * 60 and (not need_captions or has_captions):
            results.append({
                "title": sn.get("title", "Untitled"),
                "channel": sn.get("channelTitle", "Unknown"),
                "published": parser.parse(sn["publishedAt"]).date().isoformat() if sn.get("publishedAt") else "",
                "video_id": vid,
                "duration_min": max(1, dur_s // 60),
                "has_captions": has_captions,
                "views": int(stats.get("viewCount", 0)) if stats.get("viewCount") else 0
            })

    if not results:
        st.info("No videos matched your filters. Try relaxing them.")
    else:
        results.sort(key=lambda r: (-r["has_captions"], r["duration_min"], -r["views"]))
        for i, r in enumerate(results, 1):
            url = f"https://www.youtube.com/watch?v={r['video_id']}"
            caps = "✅" if r["has_captions"] else "❌"
            st.markdown(
                f"**{i}. [{r['title']}]({url})**  \n"
                f"Channel: {r['channel']} · {r['duration_min']} min · "
                f"Captions: {caps} · Views: {r['views']:,} · Published: {r['published']}"
            )

