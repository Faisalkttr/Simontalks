# Simon — Strategic Thinking Partner Chatbot

A Streamlit chatbot with a custom persona ("Simon") who analyzes text,
uploaded files, and photos through incentive, systems, long-term, and
signal-vs-noise lenses. Runs entirely on free tiers.

- **Text chat** → routed to **Groq** (fast, free tier, Llama 3.3 70B)
- **Photo analysis** → routed to **Google Gemini** (free tier, vision-capable)
- **File analysis** (PDF, DOCX, TXT, CSV, MD, JSON) → text is extracted
  and sent to Groq as context
- **Reasoning toggle** in the sidebar shows/hides Simon's step-by-step
  thinking before the final answer

---

## 1. Get your two free API keys

### Groq (text)
1. Go to https://console.groq.com/keys
2. Sign up (free) and click "Create API Key"
3. Copy the key — you'll paste it in step 3 below

### Google Gemini (vision)
1. Go to https://aistudio.google.com/apikey
2. Sign in with a Google account and click "Create API key"
3. Copy the key

Both have generous free tiers suitable for personal/small-scale use.

---

## 2. Put the project on GitHub

1. Create a new **GitHub repository** (public or private both work)
2. Upload these files to it, keeping the folder structure:
   ```
   app.py
   requirements.txt
   .gitignore
   .streamlit/secrets.toml.example
   README.md
   ```
   (Do **not** upload a real `secrets.toml` — see `.gitignore`.)

You can do this via the GitHub website ("Add file → Upload files") or
via git:
```bash
git init
git add .
git commit -m "Simon chatbot"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/simon-bot.git
git push -u origin main
```

---

## 3. Deploy on Streamlit Community Cloud (free)

1. Go to https://share.streamlit.io and sign in with GitHub
2. Click **"New app"**
3. Pick your repo, branch (`main`), and main file path (`app.py`)
4. Before/after deploying, open **Settings → Secrets** and paste:
   ```toml
   GROQ_API_KEY = "your-actual-groq-key"
   GEMINI_API_KEY = "your-actual-gemini-key"
   ```
5. Click **Deploy**. You'll get a public URL like
   `https://your-app-name.streamlit.app`

That's it — fully free, fully hosted, auto-redeploys whenever you push
changes to GitHub.

---

## 4. Ground Simon in your own YouTube / blog / Twitter content

Simon can retrieve and cite excerpts from your actual published work
using free retrieval-augmented generation (RAG). This is configured in
the app's sidebar, no code changes needed:

- **YouTube Channel ID** — not your `@handle`. Find it via a tool like
  https://commentpicker.com/youtube-channel-id.html, or view the
  channel page source and search for `"channelId"`. The app pulls your
  latest videos via YouTube's free RSS feed and fetches transcripts
  where available (transcripts must exist/be enabled on the video).
- **Blog RSS feed URL** — most blog platforms expose one automatically,
  often at `/feed`, `/rss`, or `/rss.xml`.
- **Twitter/X content** — paste tweets or threads directly into the
  text box (separate entries with a blank line). Live/automatic
  fetching isn't reliably free since X restricted API access, so this
  stays manual — update it whenever you want fresh tweets included.

Click **"🔄 Refresh knowledge base"** in the sidebar any time you want
to re-fetch and re-index (otherwise it's cached for an hour). The
sidebar shows how many chunks were indexed from each source.

You can also set `YOUTUBE_CHANNEL_ID` and `BLOG_RSS_URL` in your
Streamlit secrets so the fields are pre-filled by default:
```toml
YOUTUBE_CHANNEL_ID = "UCxxxxxxxxxxxxxxxxxxxxxx"
BLOG_RSS_URL = "https://yourblog.com/feed"
```

**How grounding works:** on each message, Simon's app embeds your
question and compares it against embedded chunks of your content
(using Gemini's free embedding model). If anything scores above a
relevance threshold, those excerpts are handed to Simon as evidence —
he's instructed to cite them naturally and never invent content beyond
what's retrieved. If nothing relevant is found, he just answers
normally. After each grounded reply, a "📎 Drew on these sources"
expander shows exactly what was used.

**Caveats:**
- YouTube's free transcript API is occasionally rate-limited or
  blocked on cloud IPs; if a video's transcript can't be fetched, it's
  skipped silently rather than breaking the app.
- Only your latest ~15 items per source are indexed by default (adjust
  `MAX_ITEMS_PER_SOURCE` in `knowledge_base.py` if you want more —
  more items means more embedding calls per refresh).

## 5. Testing locally (optional)

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# edit secrets.toml with your real keys
streamlit run app.py
```

---

## Customizing Simon further

- Persona and behavior rules live in `SIMON_SYSTEM_PROMPT` near the
  top of `app.py` — edit the text there to adjust tone or rules.
- The reasoning format (what shows in the "🧠 Simon's reasoning"
  expander) is controlled by `REASONING_INSTRUCTION` in `app.py`.
- Swap `openai/gpt-oss-120b` or `gemini-2.0-flash` for other
  available free-tier models if you want to experiment. Groq
  periodically moves models between free/developer and Enterprise-only
  tiers — check the current list at
  https://console.groq.com/docs/models before changing the model ID
  in `app.py` (`call_groq` function).
