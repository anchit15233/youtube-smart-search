import streamlit as st

st.set_page_config(page_title="YouTube Smart Search (MVP)", page_icon="🔎")
st.title("🔎 YouTube Smart Search – MVP")

query = st.text_input("Enter a topic (e.g. linear algebra, biryani recipe)")

max_minutes = st.slider("Max duration (minutes)", 5, 60, 30)
need_captions = st.checkbox("Must have subtitles/captions")

if st.button("Search"):
    st.write(f"🔎 Showing demo results for: {query}")
    # Just demo results for now
    st.markdown("**1. Linear Algebra Basics (12 min)** – Captions ✅")
    st.markdown("**2. Visualizing Eigenvalues (20 min)** – Captions ❌")
    st.markdown("**3. Beginner Guide to Vectors (15 min)** – Captions ✅")

