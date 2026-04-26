# interface_app/ui/header.py

"""
Header UI component for the Streamlit interface.

Author: Siddhartha Gogoi

Purpose:
This file renders the compact hero header for the Survival Guidance Assistant.

It also injects app-level dark styling so the interface does not depend on
the user's Streamlit light/dark theme preference. Because apparently even
background color needs supervision now. For now, this keeps the header isolated 
from app.py so the main file does not become a landfill.
"""

import html as html_utils

import streamlit as st

from config import PAGE_TITLE, KNOWLEDGE_SOURCES


AUTHOR_NAME = "SIDDHARTHA GOGOI"
AUTHOR_LINKEDIN_URL = "https://www.linkedin.com/in/siddhartha-gogoi/"


def _build_playlist_links_html() -> str:
    """
    Build bullet links for the current YouTube playlists ingested into the
    knowledge base.

    Playlist names and URLs are stored in config.py.
    """

    playlist_items = ""

    for source in KNOWLEDGE_SOURCES:
        name = html_utils.escape(source["name"])
        url = html_utils.escape(source["url"], quote=True)

        playlist_items += (
            f'<li><a class="playlist-link" href="{url}" target="_blank">'
            f"{name}</a></li>"
        )

    return playlist_items


def render_header() -> None:
    """
    Render the application hero header.

    Important:
    CSS is kept in a normal triple-quoted string, not an f-string.
    This avoids Pylance/Python confusion with CSS curly braces.
    """

    playlist_links_html = _build_playlist_links_html()

    css = """
<style>
/* -----------------------------
   Softer forced dark app theme
   ----------------------------- */
.stApp {
    background: #172033 !important;
    color: #f8fafc !important;
    font-family: Inter, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
}

[data-testid="stAppViewContainer"] {
    background: #172033 !important;
}

/* Move app upward, but keep the author line visible */
.block-container {
    padding-top: 2.55rem !important;
    padding-bottom: 2rem !important;
}

/* Keep Streamlit top chrome quiet */
[data-testid="stHeader"] {
    background: rgba(23, 32, 51, 0.96) !important;
}

/* Generated answer readability */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stMarkdownContainer"] ol,
[data-testid="stMarkdownContainer"] ul {
    color: #f8fafc !important;
    opacity: 1 !important;
    font-weight: 500 !important;
}

/* Markdown table readability */
[data-testid="stMarkdownContainer"] table,
[data-testid="stMarkdownContainer"] table *,
[data-testid="stChatMessage"] table,
[data-testid="stChatMessage"] table * {
    color: #f8fafc !important;
    opacity: 1 !important;
    font-weight: 500 !important;
    border-color: rgba(248, 250, 252, 0.24) !important;
}

[data-testid="stMarkdownContainer"] table {
    border-collapse: collapse !important;
    background: rgba(255, 255, 255, 0.025) !important;
}

[data-testid="stMarkdownContainer"] th,
[data-testid="stChatMessage"] th {
    color: #ffffff !important;
    font-weight: 850 !important;
    background: rgba(255, 255, 255, 0.10) !important;
}

[data-testid="stMarkdownContainer"] td,
[data-testid="stChatMessage"] td {
    color: #f8fafc !important;
    font-weight: 550 !important;
    background: rgba(255, 255, 255, 0.045) !important;
}

/* Chat message readability */
[data-testid="stChatMessage"] {
    color: #f8fafc !important;
    opacity: 1 !important;
}

[data-testid="stChatMessage"] * {
    opacity: 1 !important;
}

/* Text area polish */
textarea {
    background: #30384b !important;
    color: #f8fafc !important;
    border-radius: 10px !important;
    border: 1px solid rgba(255, 255, 255, 0.26) !important;
}

textarea::placeholder {
    color: rgba(248, 250, 252, 0.62) !important;
}

/* Primary buttons */
button[kind="primary"],
div[data-testid="stButton"] button[kind="primary"] {
    background: #ff4b4b !important;
    color: #ffffff !important;
    border-radius: 10px !important;
    border: 1px solid #ff4b4b !important;
    font-weight: 750 !important;
}

/* Disabled buttons must remain visible */
div[data-testid="stButton"] button:disabled,
button:disabled {
    background: rgba(255, 255, 255, 0.13) !important;
    color: rgba(248, 250, 252, 0.82) !important;
    border: 1px solid rgba(248, 250, 252, 0.34) !important;
    opacity: 1 !important;
}

/* Streamlit alert boxes */
[data-testid="stAlert"] {
    opacity: 1 !important;
}

/* -----------------------------
   Hero header
   ----------------------------- */
.hero-card {
    background:
        linear-gradient(135deg, rgba(38, 50, 68, 0.98), rgba(48, 61, 82, 0.96)),
        radial-gradient(circle at top left, rgba(212, 175, 55, 0.16), transparent 36%);
    border: 1px solid rgba(212, 175, 55, 0.42);
    border-radius: 18px;

    /* Extra top padding prevents the author line from clipping into the top edge. */
    padding: 1.85rem 1.35rem 1.20rem 1.35rem;

    margin-bottom: 2.05rem;
    box-shadow: 0 12px 28px rgba(0, 0, 0, 0.22);
    overflow: visible !important;
    position: relative;
}

.hero-grid {
    display: grid;
    grid-template-columns: minmax(0, 1.9fr) minmax(280px, 0.9fr);
    gap: 1.35rem;
    align-items: start;
}

/* Author line: visible gold text, not a half-buried capsule */
.author-credit {
    display: block;
    color: #ffd166 !important;
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    padding: 0 !important;
    font-size: 0.76rem;
    font-weight: 900;
    letter-spacing: 0.085rem;
    text-transform: uppercase;
    margin: 0 0 0.72rem 0;
    opacity: 1 !important;
    text-shadow: 0 0 10px rgba(255, 209, 102, 0.22);
}

.author-credit a {
    color: #ffd166 !important;
    text-decoration: none !important;
}

.author-credit a:hover {
    color: #ffe58a !important;
    text-decoration: underline !important;
}

.hero-title {
    color: #ffffff;
    font-size: 1.88rem;
    font-weight: 850;
    letter-spacing: -0.035rem;
    line-height: 1.12;
    margin-bottom: 0.60rem;
}

.hero-subtitle {
    color: rgba(255, 255, 255, 0.90);
    font-size: 0.94rem;
    line-height: 1.50;
    max-width: 980px;
    margin-bottom: 0.95rem;
}

.hero-badge-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.48rem;
}

.hero-badge {
    color: #fff4cc;
    background: rgba(212, 175, 55, 0.16);
    border: 1px solid rgba(212, 175, 55, 0.45);
    border-radius: 999px;
    padding: 0.26rem 0.64rem;
    font-size: 0.72rem;
    font-weight: 750;
}

/* -----------------------------
   Playlist block on right
   ----------------------------- */
.playlist-panel {
    margin-top: 1.65rem;
    padding: 0.85rem 0.95rem;
    border-radius: 14px;
    background: rgba(255, 255, 255, 0.07);
    border: 1px solid rgba(212, 175, 55, 0.30);
}

.playlist-heading {
    color: #fff4cc;
    font-size: 0.86rem;
    font-weight: 850;
    line-height: 1.35;
    margin-bottom: 0.55rem;
}

.playlist-list {
    margin: 0;
    padding-left: 1.1rem;
    color: rgba(255, 255, 255, 0.90);
}

.playlist-list li {
    margin-bottom: 0.32rem;
    font-size: 0.84rem;
}

.playlist-link {
    color: #ffd166 !important;
    font-weight: 800;
    text-decoration: none !important;
}

.playlist-link:hover {
    color: #ffe58a !important;
    text-decoration: underline !important;
}

@media (max-width: 900px) {
    .hero-grid {
        grid-template-columns: 1fr;
    }

    .playlist-panel {
        margin-top: 0.35rem;
    }

    .hero-title {
        font-size: 1.5rem;
    }
}
</style>
"""

    html_body = f"""
<div class="hero-card">
<div class="hero-grid">

<div class="hero-left">
<div class="author-credit">
Authored by <a href="{AUTHOR_LINKEDIN_URL}" target="_blank">{AUTHOR_NAME}</a>
</div>

<div class="hero-title">🧭 {PAGE_TITLE}</div>

<div class="hero-subtitle">
Grounded survival answers from curated YouTube playlist knowledge.
<br><br>
Ask practical survival questions and get responses built from vectorized transcript content.
<br>
The assistant can connect relevant information across videos and across playlists when the knowledge base supports it.
</div>

<div class="hero-badge-row">
<span class="hero-badge">Playlist-grounded</span>
<span class="hero-badge">Cross-video intelligence</span>
<span class="hero-badge">Cross-playlist intelligence</span>
<span class="hero-badge">Conversational follow-ups</span>
</div>
</div>

<div class="playlist-panel">
<div class="playlist-heading">Current YouTube playlist ingested into knowledge base</div>
<ul class="playlist-list">
{playlist_links_html}
</ul>
</div>

</div>
</div>
"""

    st.markdown(css + html_body, unsafe_allow_html=True)