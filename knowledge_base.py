"""
Knowledge base for Simon: pulls content from a YouTube channel (via RSS +
transcripts) and a blog (via RSS), chunks it, embeds it with Gemini's free
embedding model, and retrieves the most relevant excerpts for a given query
so Simon can ground his answers in the persona's own published work.
"""

import re
import time

import numpy as np
import requests
import feedparser
import streamlit as st

MAX_ITEMS_PER_SOURCE = 15       # cap how many videos/posts we ingest
CHUNK_SIZE_CHARS = 1000         # rough chunk size for embedding
CHUNK_OVERLAP_CHARS = 150
SIMILARITY_THRESHOLD = 0.55     # below this, don't bother grounding
TOP_K = 4


# ------------------------------------------------------------------
# Fetching
# ------------------------------------------------------------------
def _fetch_youtube_items(channel_id: str) -> list:
    """Return [{'title', 'url', 'text'}] using channel RSS + transcripts."""
    if not channel_id:
        return []

    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
        resp = requests.get(feed_url, timeout=15)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
    except Exception:
        return []

    items = []
    for entry in parsed.entries[:MAX_ITEMS_PER_SOURCE]:
        video_id = entry.get("yt_videoid") or _extract_video_id(entry.get("link", ""))
        if not video_id:
            continue
        transcript_text = _fetch_youtube_transcript(video_id)
        if not transcript_text:
            continue
        items.append(
            {
                "title": entry.get("title", "Untitled video"),
                "url": entry.get("link", f"https://www.youtube.com/watch?v={video_id}"),
                "text": transcript_text,
                "source_type": "YouTube",
            }
        )
    return items


def _extract_video_id(url: str) -> str:
    match = re.search(r"v=([\w-]{6,})", url or "")
    return match.group(1) if match else ""


def _fetch_youtube_transcript(video_id: str) -> str:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        return ""
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join(seg["text"] for seg in transcript)
    except Exception:
        # Transcript disabled, unavailable, or fetch blocked — skip silently
        return ""


def _fetch_blog_items(rss_url: str) -> list:
    """Return [{'title', 'url', 'text'}] from a blog RSS/Atom feed."""
    if not rss_url:
        return []

    try:
        resp = requests.get(rss_url, timeout=15)
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
    except Exception:
        return []

    items = []
    for entry in parsed.entries[:MAX_ITEMS_PER_SOURCE]:
        text = ""
        if "content" in entry and entry.content:
            text = entry.content[0].get("value", "")
        elif "summary" in entry:
            text = entry.summary

        text = _strip_html(text)

        # If the feed only gives a short summary, try to pull the full article
        if len(text) < 400 and entry.get("link"):
            fetched = _fetch_article_text(entry.link)
            if fetched:
                text = fetched

        if not text.strip():
            continue

        items.append(
            {
                "title": entry.get("title", "Untitled post"),
                "url": entry.get("link", ""),
                "text": text,
                "source_type": "Blog",
            }
        )
    return items


def _fetch_article_text(url: str) -> str:
    try:
        from bs4 import BeautifulSoup

        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)
    except Exception:
        return ""


def _strip_html(html: str) -> str:
    try:
        from bs4 import BeautifulSoup

        return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
    except Exception:
        return re.sub("<[^<]+?>", "", html or "")


def _parse_manual_tweets(raw_text: str) -> list:
    """Manual paste box: one tweet per line, or blank-line separated."""
    if not raw_text or not raw_text.strip():
        return []
    blocks = [b.strip() for b in re.split(r"\n\s*\n", raw_text) if b.strip()]
    return [
        {
            "title": f"Tweet {i + 1}",
            "url": "",
            "text": block,
            "source_type": "Twitter/X",
        }
        for i, block in enumerate(blocks)
    ]


# ------------------------------------------------------------------
# Chunking
# ------------------------------------------------------------------
def _chunk_text(text: str, size: int = CHUNK_SIZE_CHARS, overlap: int = CHUNK_OVERLAP_CHARS) -> list:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= size:
        return [text] if text else []
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


# ------------------------------------------------------------------
# Embeddings (Gemini free embedding model)
# ------------------------------------------------------------------
def _embed_texts(texts: list, task_type: str) -> list:
    import google.generativeai as genai

    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    embeddings = []
    for t in texts:
        try:
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=t,
                task_type=task_type,
            )
            embeddings.append(np.array(result["embedding"]))
        except Exception:
            embeddings.append(None)
        time.sleep(0.05)  # be gentle on rate limits
    return embeddings


def _cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------
@st.cache_data(show_spinner=False, ttl=3600)
def build_knowledge_base(youtube_channel_id: str, blog_rss_url: str, manual_tweets_text: str, refresh_nonce: int):
    """Fetch, chunk, and embed all configured sources. Cached for an hour,
    or until refresh_nonce changes (bumped by the sidebar refresh button)."""
    raw_items = []
    raw_items += _fetch_youtube_items(youtube_channel_id.strip())
    raw_items += _fetch_blog_items(blog_rss_url.strip())
    raw_items += _parse_manual_tweets(manual_tweets_text)

    chunk_records = []
    for item in raw_items:
        for chunk in _chunk_text(item["text"]):
            chunk_records.append(
                {
                    "text": chunk,
                    "title": item["title"],
                    "url": item["url"],
                    "source_type": item["source_type"],
                }
            )

    if not chunk_records:
        return {"chunks": [], "embeddings": None, "stats": {"youtube": 0, "blog": 0, "twitter": 0}}

    texts = [c["text"] for c in chunk_records]
    embeddings = _embed_texts(texts, task_type="RETRIEVAL_DOCUMENT")

    # Drop any chunks whose embedding failed
    kept_chunks, kept_embeddings = [], []
    for c, e in zip(chunk_records, embeddings):
        if e is not None:
            kept_chunks.append(c)
            kept_embeddings.append(e)

    stats = {
        "youtube": sum(1 for c in kept_chunks if c["source_type"] == "YouTube"),
        "blog": sum(1 for c in kept_chunks if c["source_type"] == "Blog"),
        "twitter": sum(1 for c in kept_chunks if c["source_type"] == "Twitter/X"),
    }

    return {
        "chunks": kept_chunks,
        "embeddings": np.array(kept_embeddings) if kept_embeddings else None,
        "stats": stats,
    }


def retrieve_relevant_chunks(kb: dict, query: str, top_k: int = TOP_K) -> list:
    """Return the top-k most relevant chunk records for a query, or [] if
    nothing clears the similarity threshold."""
    if not kb or not kb.get("chunks") or kb.get("embeddings") is None:
        return []

    query_embeddings = _embed_texts([query], task_type="RETRIEVAL_QUERY")
    query_vec = query_embeddings[0]
    if query_vec is None:
        return []

    sims = [_cosine_sim(query_vec, chunk_vec) for chunk_vec in kb["embeddings"]]
    ranked = sorted(zip(kb["chunks"], sims), key=lambda x: x[1], reverse=True)

    results = [(c, s) for c, s in ranked[:top_k] if s >= SIMILARITY_THRESHOLD]
    return results


def format_grounding_block(results: list) -> str:
    """Turn retrieved chunks into a system-prompt-ready grounding block."""
    if not results:
        return ""

    lines = [
        "RELEVANT EXCERPTS FROM YOUR OWN PUBLISHED WORK "
        "(YouTube, blog, and/or Twitter/X). Use these as evidence to ground "
        "your answer where genuinely relevant. Cite naturally in your own "
        "voice (e.g., \"as I laid out in my video on X...\") and include the "
        "source URL when you cite one. Do not invent content beyond what's "
        "given here, and don't force a citation if nothing here is actually "
        "relevant to the question.\n"
    ]
    for chunk, score in results:
        url_part = f" ({chunk['url']})" if chunk["url"] else ""
        lines.append(f"\n[{chunk['source_type']}] \"{chunk['title']}\"{url_part}")
        lines.append(chunk["text"])
    return "\n".join(lines)
