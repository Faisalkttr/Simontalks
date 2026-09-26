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

## 4. Testing locally (optional)

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
- Swap `llama-3.3-70b-versatile` or `gemini-2.0-flash` for other
  available free-tier models if you want to experiment.
