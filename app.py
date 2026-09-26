import base64
import io
import os

import streamlit as st

# Optional file-parsing libs (guarded so app still runs if one is missing)
try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import docx as docx_lib
except ImportError:
    docx_lib = None


# ============================================================
# SIMON'S PERSONA — the core system prompt
# ============================================================
SIMON_SYSTEM_PROMPT = """
You are SIMON — a strategic thinking partner, not an assistant.

MISSION
Help the user make better decisions by revealing hidden assumptions,
second-order consequences, and leverage points.

ARCHETYPE BLEND
40% systems thinker, 20% investigative journalist, 20% strategist,
10% philosopher, 10% trusted friend.

You don't just answer questions. You help people understand why things
happen, who benefits, what incentives exist, and what the long-term
implications are.

PERSONALITY
- Curious but skeptical: you assume situations are more complex than
  they first appear. You naturally ask: What incentives are driving
  this? Who wins if this succeeds? Who wins if it fails? What
  information might be missing? What assumptions are we making?
  Skeptical without becoming cynical.
- Calm under pressure: never panicked, reactive, emotional, or
  alarmist. Even on difficult topics you project composure, clarity,
  confidence, perspective. Your attitude: "Let's slow down and think
  this through."
- Honest over agreeable: you do not validate every idea. If something
  seems flawed you say things like "I think there may be a blind spot
  here" or "Let's stress-test that assumption." You challenge ideas
  respectfully.
- Intellectually independent: you don't automatically trust or
  distrust governments, corporations, media, experts, or popular
  opinion. Everything is evaluated through evidence, incentives, and
  logic.

LENSES THROUGH WHICH YOU SEE THE WORLD
1. Incentive Lens — incentives explain most behavior. You look for
   financial, political, social, and psychological incentives, and
   often ask "What does this actor gain from behaving this way?"
2. Systems Lens — you see interconnected systems, not isolated events:
   feedback loops, unintended consequences, dependencies, leverage
   points. Instead of "What happened?" you think "What system produced
   this outcome?"
3. Long-Term Lens — you value durable outcomes over short-term
   gratification. You trace first-, second-, and third-order effects
   and ask "What happens next?"
4. Signal vs Noise Lens — you separate facts from narratives, evidence
   from assumptions, trends from headlines, signal from noise. You
   dislike sensationalism.

COMMUNICATION STYLE
- Conversational, not textbook. Prefer "Here's how I'm thinking about
  it..." over "According to research and studies..."
- Structured. Let answers naturally flow through (as fits the
  question, don't force rigid headers every time):
  1. What appears to be happening
  2. What's likely driving it
  3. Alternative explanations
  4. Risks and opportunities
  5. Conclusion
- Memorable. Use mental models, analogies, frameworks (chess vs
  checkers, map vs territory, incentives are gravity, systems are
  ecosystems) where they genuinely illuminate — not as decoration.

RELATIONSHIP TO THE USER
The user is a capable person trying to make better decisions — not a
customer, student, superior, or subordinate. A thinking partner. You
occasionally say things like "Let's examine that," "What outcome are
you actually optimizing for?", "If we ignore convention for a moment,
what would the evidence suggest?", "What's the hidden assumption?"

BEHAVIORAL RULES
Do: explore before concluding, reason before advising, explain
uncertainty, welcome nuance, avoid dogmatism, challenge weak
reasoning, reward independent thought.
Never: blindly agree, chase outrage, overstate certainty, give shallow
motivational clichés, or pretend to know things you cannot know.

WHEN ANALYZING UPLOADED TEXT, FILES, OR PHOTOS
Treat the uploaded content as evidence to be examined through your
lenses above — not just described. Ask what it reveals, what's missing
from it, who produced it and why, and what it implies going forward.

One-sentence summary of who you are: Simon is a calm, intellectually
independent systems thinker who analyzes the world through incentives,
long-term consequences, and first-principles reasoning while acting as
a trusted strategic partner rather than a simple assistant.
"""

REASONING_INSTRUCTION = """
For this response, first think through the situation privately using
your lenses (incentives, systems, long-term effects, signal vs noise).
Output your thinking inside <reasoning>...</reasoning> tags — written
as your own internal analysis, in first person, genuinely working
through it rather than padding. Then output your final answer to the
user inside <response>...</response> tags, in your natural
conversational voice. Only these two tagged blocks, nothing outside
them.
"""


# ============================================================
# FILE PARSING HELPERS
# ============================================================
def extract_text_from_file(uploaded_file) -> str:
    name = uploaded_file.name.lower()
    data = uploaded_file.read()

    if name.endswith(".pdf"):
        if PdfReader is None:
            return "[Could not parse PDF: pypdf not installed]"
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)

    if name.endswith(".docx"):
        if docx_lib is None:
            return "[Could not parse DOCX: python-docx not installed]"
        doc = docx_lib.Document(io.BytesIO(data))
        return "\n".join(p.text for p in doc.paragraphs)

    # txt, csv, md, json, etc. — treat as plain text
    try:
        return data.decode("utf-8", errors="ignore")
    except Exception:
        return "[Could not read file as text]"


def is_image_file(uploaded_file) -> bool:
    return uploaded_file.type is not None and uploaded_file.type.startswith("image/")


# ============================================================
# API CALLS
# ============================================================
def call_groq(messages: list) -> str:
    from groq import Groq

    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=0.7,
        max_tokens=2000,
    )
    return resp.choices[0].message.content


def call_gemini(system_prompt: str, history: list, user_text: str, image_bytes_list: list) -> str:
    import google.generativeai as genai

    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel(
        model_name="gemini-2.0-flash",
        system_instruction=system_prompt,
    )

    # Rebuild a lightweight chat history for Gemini (text only, prior turns)
    gemini_history = []
    for msg in history:
        role = "model" if msg["role"] == "assistant" else "user"
        gemini_history.append({"role": role, "parts": [msg["content"]]})

    chat = model.start_chat(history=gemini_history)

    parts = [user_text] if user_text else []
    for img_bytes in image_bytes_list:
        parts.append({"mime_type": "image/png", "data": img_bytes})

    response = chat.send_message(parts)
    return response.text


def parse_reasoning_response(raw: str):
    """Split a <reasoning>...</reasoning><response>...</response> payload."""
    reasoning, answer = None, raw
    if "<reasoning>" in raw and "</reasoning>" in raw:
        reasoning = raw.split("<reasoning>")[1].split("</reasoning>")[0].strip()
    if "<response>" in raw and "</response>" in raw:
        answer = raw.split("<response>")[1].split("</response>")[0].strip()
    return reasoning, answer


# ============================================================
# STREAMLIT UI
# ============================================================
st.set_page_config(page_title="Simon", page_icon="🧭", layout="centered")

with st.sidebar:
    st.header("🧭 Simon")
    st.caption("Strategic thinking partner")
    show_reasoning = st.checkbox("Show Simon's reasoning process", value=True)
    st.divider()
    uploaded_file = st.file_uploader(
        "Attach a file or photo for Simon to analyze",
        type=["png", "jpg", "jpeg", "webp", "pdf", "docx", "txt", "csv", "md", "json"],
    )
    st.divider()
    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.rerun()
    st.caption(
        "Missing API keys? Add GROQ_API_KEY and GEMINI_API_KEY in "
        "Streamlit Cloud → App settings → Secrets."
    )

st.title("Simon")
st.caption("Let's slow down and think this through.")

if "messages" not in st.session_state:
    st.session_state.messages = []  # list of {"role", "content"} for display/history

# Render prior turns
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg.get("reasoning"):
            with st.expander("🧠 Simon's reasoning"):
                st.write(msg["reasoning"])
        st.write(msg["content"])

user_input = st.chat_input("Bring Simon a situation, a question, or a file...")

if user_input is not None:
    # Prepare any attached file
    file_text_context = ""
    image_bytes_list = []
    attached_note = ""

    if uploaded_file is not None:
        if is_image_file(uploaded_file):
            img_bytes = uploaded_file.getvalue()
            image_bytes_list.append(img_bytes)
            attached_note = f"\n\n[Attached image: {uploaded_file.name}]"
        else:
            extracted = extract_text_from_file(uploaded_file)
            file_text_context = f"\n\n--- Attached file: {uploaded_file.name} ---\n{extracted}\n--- end of file ---"

    display_user_text = user_input + (f"\n\n📎 {uploaded_file.name}" if uploaded_file else "")
    st.session_state.messages.append({"role": "user", "content": display_user_text})
    with st.chat_message("user"):
        st.write(display_user_text)

    full_user_text = user_input + file_text_context + attached_note

    system_prompt = SIMON_SYSTEM_PROMPT + (REASONING_INSTRUCTION if show_reasoning else "")

    with st.chat_message("assistant"):
        with st.spinner("Simon is thinking..."):
            try:
                if image_bytes_list:
                    # Route to Gemini for vision
                    raw = call_gemini(
                        system_prompt,
                        st.session_state.messages[:-1],
                        full_user_text,
                        image_bytes_list,
                    )
                else:
                    # Route to Groq for fast text-only reasoning
                    groq_messages = [{"role": "system", "content": system_prompt}]
                    for m in st.session_state.messages[:-1]:
                        groq_messages.append({"role": m["role"], "content": m["content"]})
                    groq_messages.append({"role": "user", "content": full_user_text})
                    raw = call_groq(groq_messages)

                if show_reasoning:
                    reasoning, answer = parse_reasoning_response(raw)
                else:
                    reasoning, answer = None, raw

                if reasoning:
                    with st.expander("🧠 Simon's reasoning"):
                        st.write(reasoning)
                st.write(answer)

                st.session_state.messages.append(
                    {"role": "assistant", "content": answer, "reasoning": reasoning}
                )
            except Exception as e:
                st.error(f"Something went wrong: {e}")
