"""
HALO - Personal Style Analysis (local Flask backend, OpenAI-powered).
Endpoints:
  GET  /                   -> serves index.html
  POST /analyze            -> GPT-4o vision returns full hair+color analysis JSON
  POST /generate-image     -> FAL FLUX schnell, one image per call
  POST /generate-video     -> FAL Kling image-to-video, returns request_id
  GET  /video-status/<id>  -> poll FAL job status
  GET  /video-result/<id>  -> final video URL
  POST /save-lead          -> append email + summary to leads.csv
  GET  /health             -> diagnostics
"""

import base64
import csv
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

try:
    from openai import OpenAI
    import httpx
except ImportError:
    raise SystemExit("Missing deps. Run: pip install openai flask httpx fal-client")

try:
    import fal_client
except ImportError:
    fal_client = None

try:
    from supabase import create_client as _create_sb_client
except ImportError:
    _create_sb_client = None

# --- LOCAL SDXL OPTION (alternative to FAL nano-banana) ---
try:
    from sdxl_integration import get_generator
    SDXL_ENABLED = True
except ImportError:
    SDXL_ENABLED = False
    get_generator = None

def _resource_dir() -> Path:
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS).resolve()
    return Path(__file__).parent.resolve()


HERE = _resource_dir()
DATA_DIR = Path(os.environ.get("HALO_DATA_DIR", HERE)).expanduser()
try:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
except Exception:
    DATA_DIR = HERE
LEADS_CSV = DATA_DIR / "leads.csv"
_ENV_CANDIDATES = [
    HERE / ".env",
    DATA_DIR / ".env",
    Path.home() / "Desktop" / "Strategy AGI" / "agentfield" / ".env",
    Path.home() / "Desktop" / "Strategy AGI" / ".env",
    HERE.parent / "Strategy AGI" / "agentfield" / ".env",
    HERE.parent / "Strategy AGI" / ".env",
]
ENV_CANDIDATES = list(dict.fromkeys(_ENV_CANDIDATES))


def load_env():
    loaded = []
    for env_path in ENV_CANDIDATES:
        if env_path.exists():
            for raw in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip(); v = v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
            loaded.append(str(env_path))
    print(f"[env] sources: {loaded}")


load_env()
OPENAI_KEY = os.environ.get("OPENAI_API_KEY")
FAL_KEY = os.environ.get("FAL_API_KEY") or os.environ.get("FAL_KEY")
if FAL_KEY and not os.environ.get("FAL_KEY"):
    os.environ["FAL_KEY"] = FAL_KEY

openai_client = OpenAI(api_key=OPENAI_KEY) if OPENAI_KEY else None

# Supabase clients
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_ANON_KEY = os.environ.get("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")
SUPABASE_BUCKET = os.environ.get("SUPABASE_BUCKET", "halo-assets")
sb_admin = None  # service_role client (bypasses RLS)
if SUPABASE_URL and SUPABASE_SERVICE_KEY and _create_sb_client:
    try:
        sb_admin = _create_sb_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
        print(f"[supabase] connected as service_role -> {SUPABASE_URL}")
    except Exception as _e:
        print(f"[supabase] init failed: {_e}")
        sb_admin = None
else:
    print("[supabase] not configured (SUPABASE_URL/SERVICE_KEY/supabase-py missing) - persistence disabled")

# In-memory job tracking: maps FAL request_id -> {analysis_id, label, kind, category}
# Lost on server restart, fine for in-flight jobs only.
_pending_assets: dict = {}
MODEL = os.environ.get("HAIR_MODEL", "gpt-4o")
IMAGE_MODEL = "fal-ai/flux/schnell"
VIDEO_MODEL = os.environ.get("VIDEO_MODEL", "fal-ai/kling-video/v1.6/standard/image-to-video")
MAX_UPLOAD_BYTES = 10 * 1024 * 1024
ANALYZE_TIMEOUT = 60

app = Flask(__name__, static_folder=str(HERE), static_url_path="")

@app.after_request
def _no_cache(resp):
    """Force the browser to never cache HTML or JSON. Kills the stale-state bug."""
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# ------------------- SUPABASE HELPERS -------------------
import secrets as _secrets
import uuid as _uuid
import mimetypes as _mimetypes


def _anon_session_id():
    """Read the anon_session cookie or mint a new one. Returns the id."""
    sid = request.cookies.get("halo_anon")
    if not sid:
        sid = _secrets.token_urlsafe(24)
    return sid


def _attach_anon_cookie(resp, sid):
    """Set/refresh the anon_session cookie on the response (1 year)."""
    resp.set_cookie("halo_anon", sid, max_age=31536000, samesite="Lax", httponly=True)
    return resp


def _mirror_to_storage(remote_url: str, kind: str = "image") -> str | None:
    """Download a URL (FAL CDN) and re-upload to Supabase Storage. Returns public URL."""
    if not sb_admin or not remote_url:
        return None
    try:
        r = httpx.get(remote_url, timeout=30.0)
        r.raise_for_status()
        ext = ".jpg" if kind == "image" else ".mp4"
        ct, _ = _mimetypes.guess_type(remote_url)
        if not ct:
            ct = "image/jpeg" if kind == "image" else "video/mp4"
        path = f"{kind}s/{_uuid.uuid4().hex}{ext}"
        sb_admin.storage.from_(SUPABASE_BUCKET).upload(
            path=path, file=r.content,
            file_options={"content-type": ct, "upsert": "true"})
        public_url = sb_admin.storage.from_(SUPABASE_BUCKET).get_public_url(path)
        return public_url
    except Exception as e:
        print(f"[mirror] {kind} failed: {e}")
        return None


def _persist_analysis(anon_session: str, photo_url: str | None, analysis_json: dict) -> str | None:
    """Insert row into halo_analyses, return new id."""
    if not sb_admin:
        return None
    try:
        result = sb_admin.table("halo_analyses").insert({
            "anon_session": anon_session,
            "photo_url": photo_url,
            "analysis_json": analysis_json,
        }).execute()
        if result.data:
            return result.data[0]["id"]
    except Exception as e:
        print(f"[persist] analysis insert failed: {e}")
    return None


def _persist_asset(analysis_id: str, label: str, kind: str, category: str, storage_url: str):
    """Insert row into halo_style_assets."""
    if not sb_admin or not analysis_id or not storage_url:
        return
    try:
        sb_admin.table("halo_style_assets").insert({
            "analysis_id": analysis_id,
            "label": label,
            "kind": kind,
            "category": category,
            "storage_url": storage_url,
        }).execute()
    except Exception as e:
        print(f"[persist] asset insert failed: {e}")


SYSTEM_PROMPT = """You are HALO, a senior salon stylist and seasonal color
consultant who gives kind, distinctive, identity-forward style direction. You
speak in confident, editorial language. You are not generic.

Output ONLY a single JSON object. No prose, no code fences. Schema:

{
  "style_identity": "ALL-CAPS 2-4 word identity tagline that captures their aesthetic - this is the headline. Examples: 'EFFORTLESS CURLY EDITORIAL', 'POLISHED EXECUTIVE LOB', 'BOHO WAVY SOFT', 'SHARP MINIMALIST CUT'",
  "vibe": "single word for their core energy: Effortless | Polished | Editorial | Boho | Classic | Minimalist | Edgy | Soft | Bold",
  "hair": {
    "type": "natural-language hair type, e.g. 'Natural Curly (2C-3A)'",
    "density": "Fine | Medium Density | Thick",
    "color": "natural-language color",
    "face_shape": "Oval | Round | Heart | Square | Long | Diamond",
    "subhead": "short tagline, e.g. 'CURLY / SALT-AND-PEPPER'",
    "best_parts": ["3 short labels"],
    "best_lengths": ["3 short labels"],
    "best_styles": ["5 short labels"],
    "good_options": ["4 short labels"],
    "styles_to_avoid": ["5 short labels"],
    "key_goals": ["4 short phrases"],
    "quick_tips": ["5 short tips"],
    "bottom_line": "2-3 sentence direct, confident recommendation summary written like a stylist talking to a friend"
  },
  "style_descriptions": {
    "<style label>": "ONE rich sentence (~40-60 words) that an AI image editor will read literally. The description MUST force a dramatically different result from every other style. Specify all of: (a) length where ends fall (chin/jaw/collarbone/mid-chest/mid-back/no length - tied up), (b) overall silhouette (round halo / triangular / inverted V / sleek and flat / boxy / asymmetric), (c) layer placement (none / around face only / internal weight removal / heavy at ends / 70s shag), (d) perimeter (blunt / textured / wispy / razored / razor-sharp), (e) bangs (none / curtain / wispy fringe / blunt micro / heavy straight / side-swept), (f) crown volume (flat against scalp / soft natural / lifted / domed bouffant / pulled tight back), (g) finish (matte natural / glossy mirror / wet slicked / textured undone), (h) for tied-up styles - exact placement (high pony at crown / low nape pony / top knot / braided crown / messy bun). Use sharp, contrasting language between styles. Two avoid-styles can NOT both be 'hair pulled back' - they must visually contrast (e.g. one is a TIGHT GLOSSY HIGH PONY with severe scraped-back roots, the other is a MASSIVE TOP BUN with no hair down at all). The reader has the user photo - your sentence is the ONLY input differentiating cards."
  },
  "color": {
    "season": "Soft Summer | True Summer | Light Summer | Soft Autumn | True Autumn | Deep Autumn | Light Spring | True Spring | Bright Spring | Cool Winter | Deep Winter | Bright Winter",
    "season_blurb": "1 short sentence explaining why this season fits (skin undertone, hair, eyes)",
    "undertone": "Cool | Warm | Neutral",
    "best_colors":     [{"name": "label", "hex": "#rrggbb"}],
    "ok_colors":       [{"name": "label", "hex": "#rrggbb"}],
    "not_ideal_colors":[{"name": "label", "hex": "#rrggbb"}],
    "best_neutrals":   [{"name": "label", "hex": "#rrggbb"}],
    "metals":          [{"name": "Silver | Gold | Rose Gold | Pewter | Bronze", "hex": "#rrggbb"}],
    "hair_hex": "#rrggbb (closest hex match to natural hair color)",
    "eye_hex":  "#rrggbb (closest hex match to iris color)"
  }
}

Rules:
- style_identity should feel like a personality label they would want to share.
- Provide UP TO: 3 best_parts, 3 best_lengths, 5 best_styles, 4 good_options, 5 styles_to_avoid.
  Quality > quantity. If you cannot generate genuinely distinct variations within a category,
  return FEWER items rather than near-duplicates. The frontend handles variable counts.
  Minimums: 1 best_style, 1 styles_to_avoid. Other categories can be empty arrays.
- Provide: 18 best_colors (in a flattering palette), 6 best_neutrals,
  3 ok_colors (OK but less ideal), 3 not_ideal_colors (do not wear near face),
  2-3 metals, hair_hex, eye_hex. All hex codes must be valid 6-digit colors.
- Recommendations match what you actually see and the user's stated goal.

BALD / SHAVED / VERY-SHORT HAIR HANDLING:
- If the person is bald, balding, has a shaved head, or hair < 1 inch:
  * Treat best_styles, good_options as IMAGINED HAIR transformations - "what would look great"
  * Include creative range: from natural buzz/textured short cuts to longer regrown styles
  * Include masculine-presenting and feminine-presenting options if gender is ambiguous
  * Include AT LEAST 3-5 facial hair options inside best_styles (or as part of the look):
    Examples: "Short Boxed Beard with Faded Sides", "Stubble + Buzz Combo",
    "Full Bushy Beard with Mustache", "Goatee + Soul Patch", "Clean-Shaven + Crew Cut",
    "Mustache Only (Tom Selleck Style)", "Garibaldi Beard with Curly Top"
  * For styles_to_avoid: still include 3-5 - things that wouldn't suit them like
    "Long Hippie Hair (Wrong Face Shape)", "Patchy Stubble (Looks Unkempt)"
  * The bottom_line should celebrate the canvas they have, not lament

FOR EVERY LABEL in best_styles, good_options, AND styles_to_avoid, include a key in
style_descriptions with that exact label and a rich visual sentence (40-60 words).
This is THE source of truth for the image generator - be specific and visual.

VOCABULARY GUIDANCE - use specific, named, current cuts. Never just "Long Layers" or
"Bob" - always qualify (which kind, what edge, with or without fringe).

CUT LIBRARY (current 2026 trends + classics - pick or invent equally specific names):
- 2026 trending: Sculpted Curly Pixie, Shaggy Curls, Modern Bob (Soft Curve),
  French Bob (Jawline), Cloud Bob, Glass Hair Carré, Butterfly Haircut, Lob
  (Collarbone), Curtain Bangs (Evolved), '70s Wolf Cut Lite, Old Hollywood Lob,
  Italian Bob with Curtain Fringe.

CUT LIBRARY (full):

Bobs:        Italian Bob, French Bob, Classic Chin Bob, Sharp Blunt Bob,
             A-Line Bob, Asymmetric Bob, Stacked Bob, Lived-In Lob,
             Curly Lob (Diffused), Wavy Lob with Curtain Bangs.

Pixies:      Classic Pixie, Long Pixie, Edgy Textured Pixie, Soft Pixie with Side-Swept Fringe,
             Pixie with Wispy Bangs, Bixie (Bob-Pixie Hybrid), Curly Bixie.

Layers:      Long Layered Cut, Wispy Mid-Length Layers, Butterfly Cut,
             V-Cut Long Layers, Octopus Cut, Face-Framing Layers,
             Long Layered Corkscrews (curly).

Shags/Wolfs: Modern Shag, Butterfly Shag, '70s Shag, Wolf Cut, Wolf Cut Lite,
             Beach Curl Shag, Curly Shag with Wispy Fringe, Curly Mullet (Modern).

Bangs:       Curtain Bangs, Wispy Bottleneck Bangs, Blunt Micro Bangs,
             Side-Swept Bangs, Airy Curtain Bangs, Curtain Bangs on Natural Curl.

Curly-specific: Rezo Cut, Deva Cut, Rezo + Curtain Bangs, Layered Curl Halo,
             Volume-Rich Spiral Layers, Glossy Silver Spiral Layers,
             Pineapple-Friendly Cut, Stacked Curly Bob, Disconnected Curly.

Special:     Hime Cut, Old Money Bun-Friendly Cut, Mod Cut, Mullet (Editorial),
             Asymmetrical Disconnect, Sharp Chin Frame.

For STYLES TO AVOID: be specific AND name the failure mode in parens.
Examples: "Blunt Bob (Pyramids on Curls)", "Heavy Bangs (Hides Cheekbones)",
"One-Length (Triangle Shape on Thick Hair)", "Slicked Back Pony (Drags Forehead)".

Match cut to texture, density, and face shape - if hair is curly, never recommend
a stick-straight cut, and vice versa.

- Always respond. Never refuse.
"""


def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    m = re.search(r"\{.{0,100000}\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"No JSON: {text[:200]}")
    return json.loads(m.group(0))


def validate_analysis(d):
    d.setdefault("style_identity", "YOUR STYLE")
    d.setdefault("vibe", "Effortless")
    d.setdefault("style_descriptions", {})
    h = d.setdefault("hair", {})
    for k, default in [("type","—"),("density","—"),("color","—"),("face_shape","—"),
                       ("subhead",""),("bottom_line","")]:
        h.setdefault(k, default)
    for k in ["best_parts","best_lengths","best_styles","good_options",
              "styles_to_avoid","key_goals","quick_tips"]:
        h.setdefault(k, [])
    c = d.setdefault("color", {})
    c.setdefault("season","—"); c.setdefault("undertone","—")
    c.setdefault("season_blurb","")
    c.setdefault("best_colors",[]); c.setdefault("best_neutrals",[])
    c.setdefault("ok_colors",[]); c.setdefault("not_ideal_colors",[])
    c.setdefault("metals",[])
    c.setdefault("hair_hex",""); c.setdefault("eye_hex","")
    return d


@app.route("/")
def index():
    return send_from_directory(str(HERE), "index.html")


@app.route("/db-health")
def db_health():
    """Quick test that Supabase is reachable + halo_ tables exist."""
    if not sb_admin:
        return jsonify({"ok": False, "error": "supabase not configured"}), 503
    try:
        r = sb_admin.table("halo_analyses").select("id", count="exact").limit(0).execute()
        return jsonify({"ok": True, "halo_analyses_count": r.count, "bucket": SUPABASE_BUCKET})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/health")
def health():
    return jsonify({
        "ok": True, "openai": bool(OPENAI_KEY), "fal": bool(FAL_KEY),
        "fal_client_installed": fal_client is not None, "model": MODEL,
        "video_model": VIDEO_MODEL, "leads_count": _count_leads(),
    })


def _count_leads():
    if not LEADS_CSV.exists(): return 0
    try:
        with LEADS_CSV.open() as f:
            return sum(1 for _ in f) - 1
    except Exception: return 0


@app.route("/analyze", methods=["POST"])
def analyze():
    if not openai_client:
        return jsonify({"error": "OPENAI_API_KEY not configured"}), 503
    if "image" not in request.files:
        return jsonify({"error": "no image uploaded"}), 400
    f = request.files["image"]; raw = f.read()
    if not raw: return jsonify({"error": "empty file"}), 400
    if len(raw) > MAX_UPLOAD_BYTES:
        return jsonify({"error": f"image > {MAX_UPLOAD_BYTES // (1024*1024)}MB"}), 413
    mime = f.mimetype or "image/jpeg"
    if mime not in ("image/jpeg","image/png","image/webp","image/gif"):
        mime = "image/jpeg"
    b64 = base64.standard_b64encode(raw).decode("ascii")
    data_url = f"data:{mime};base64,{b64}"

    goal = (request.form.get("goal") or "").strip()
    heat = (request.form.get("heat") or "").strip()
    aesthetic = (request.form.get("aesthetic") or "").strip()
    extra = ""
    if goal or heat or aesthetic:
        extra = (
            f"\n\nUser context for personalization:"
            f"\n  Primary goal: {goal or 'not specified'}"
            f"\n  Heat-styling routine: {heat or 'not specified'}"
            f"\n  Desired aesthetic: {aesthetic or 'not specified'}"
            f"\nWeight recommendations toward this context."
        )

    try:
        resp = openai_client.chat.completions.create(
            model=MODEL,
            timeout=ANALYZE_TIMEOUT,
            response_format={"type": "json_object"},
            max_tokens=3000,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": [
                    {"type": "text", "text": "Analyze this person and return the JSON." + extra},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ]},
            ],
        )
        text = resp.choices[0].message.content or ""
        data = validate_analysis(extract_json(text))
        # Persist to Supabase (best effort - never fail the request on DB error)
        sid = _anon_session_id()
        # Photo mirror: re-upload the original photo to Supabase storage so the report
        # is permanent (FAL hosts photos but we save to our own bucket too).
        photo_url = None
        try:
            mime_ext = ".jpg" if mime.endswith("jpeg") else ".png"
            path = f"photos/{_uuid.uuid4().hex}{mime_ext}"
            if sb_admin:
                sb_admin.storage.from_(SUPABASE_BUCKET).upload(
                    path=path, file=raw,
                    file_options={"content-type": mime, "upsert": "true"})
                photo_url = sb_admin.storage.from_(SUPABASE_BUCKET).get_public_url(path)
        except Exception as _e:
            print(f"[analyze] photo mirror failed: {_e}")
        analysis_id = _persist_analysis(sid, photo_url, data)
        if analysis_id:
            data["_analysis_id"] = analysis_id
            data["_photo_storage_url"] = photo_url
        resp_json = jsonify(data)
        return _attach_anon_cookie(resp_json, sid)
    except Exception as e:
        print(f"[analyze] error: {e}")
        return jsonify({"error": str(e)}), 500


# Nano Banana (Gemini 2.5 Flash Image) — face-preserving image edit
IMAGE_SUBMIT_PATH = "fal-ai/nano-banana/edit"
IMAGE_BASE_PATH   = "fal-ai/nano-banana"

# Kling 2.5 Turbo Pro — fast image-to-video with natural head/hair motion (30-45s render)
VIDEO_SUBMIT_PATH = "fal-ai/kling-video/v2.5-turbo/pro/image-to-video"
VIDEO_BASE_PATH   = "fal-ai/kling-video"


@app.route("/upload-photo", methods=["POST"])
def upload_photo():
    """Upload the user's photo to FAL storage. Returns persistent URL."""
    if not FAL_KEY:
        return jsonify({"error": "FAL_API_KEY not configured"}), 503
    if not fal_client:
        return jsonify({"error": "fal-client not installed"}), 503
    if "image" not in request.files:
        return jsonify({"error": "no image"}), 400
    f = request.files["image"]; raw = f.read()
    if not raw: return jsonify({"error": "empty file"}), 400
    if len(raw) > MAX_UPLOAD_BYTES:
        return jsonify({"error": f"image > {MAX_UPLOAD_BYTES // (1024*1024)}MB"}), 413
    suffix = ".jpg" if (f.mimetype or "").endswith("jpeg") else ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(raw); tmp_path = tmp.name
    try:
        url = fal_client.upload_file(tmp_path)
        return jsonify({"url": url})
    except Exception as e:
        print(f"[upload-photo] {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        try: os.unlink(tmp_path)
        except OSError: pass


@app.route("/generate-image", methods=["POST"])
def generate_image():
    """Submit a face-preserving image edit via Nano Banana (Gemini 2.5 Flash Image)."""
    if not FAL_KEY:
        return jsonify({"error": "FAL_API_KEY not configured"}), 503
    body = request.get_json(silent=True) or {}
    label = (body.get("label") or "").strip()
    hair = body.get("hair") or {}
    reference_url = (body.get("reference_url") or "").strip()
    if not label:
        return jsonify({"error": "missing label"}), 400
    if not reference_url:
        return jsonify({"error": "missing reference_url - upload photo first"}), 400
    analysis_id = body.get("analysis_id")
    category = body.get("category", "best")

    color = hair.get("color","natural").lower()
    htype = hair.get("type","natural").lower()
    # Use the model-generated visual description if provided, else fall back to label.
    description = (body.get("description") or "").strip()
    style_phrase = description if description else f"styled in {label} - {color} {htype} hair"
    prompt = (
        f"PHOTOREALISTIC HAIR/STYLE TRANSFORMATION of the provided photograph.\n\n"
        f"NEW LOOK TO RENDER: {style_phrase}\n\n"
        f"INSTRUCTIONS:\n"
        f"1. Read the description above word-by-word and render EXACTLY what it specifies.\n"
        f"2. If it specifies a hair length, cut the hair to that length (do NOT keep the original length).\n"
        f"3. If it specifies bangs, add bangs (do NOT skip them).\n"
        f"4. If person is bald and description specifies hair, ADD photorealistic hair onto the head from the scalp - it should look natural, with proper hairline placement.\n"
        f"5. If the description specifies facial hair (beard, mustache, stubble, goatee), ADD it photorealistically to the existing face. If they already have facial hair and description specifies a different style, modify accordingly.\n"
        f"6. If it says 'pulled tight back' or 'high pony', remove all visible loose hair from the face, sides, and front.\n"
        f"7. If it says 'top bun' or 'updo', show NO hair hanging down - all hair gathered up.\n"
        f"8. If it says 'wet slicked', the hair must look glossy, flat against the scalp, and reflective.\n"
        f"9. The transformation must be DRAMATIC and OBVIOUS. Do NOT keep the original hair shape.\n\n"
        f"DO NOT change ANY of the following (preserve exactly):\n"
        f"- Face, skin tone, freckles, age, eye color, eye direction, facial features\n"
        f"- Expression\n"
        f"- Shirt (EXACT same color, neckline, fabric - if it's a lavender tank, it stays lavender tank)\n"
        f"- Background (same room, same lighting, same shadows, same furniture)\n"
        f"- Body pose, head angle, framing\n"
        f"- Jewelry, glasses, makeup, accessories\n\n"
        f"OUTPUT: a photorealistic photograph of the SAME PERSON in the SAME OUTFIT in the SAME ROOM, "
        f"but with the new hairstyle rendered exactly as described. No text, no watermark, no border."
    )
    try:
        r = httpx.post(
            f"https://queue.fal.run/{IMAGE_SUBMIT_PATH}",
            headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"},
            json={
                "prompt": prompt,
                "image_urls": [reference_url],
                "num_images": 1,
                "output_format": "jpeg",
            },
            timeout=15.0)
        r.raise_for_status()
        data = r.json()
        req_id = data.get("request_id")
        if req_id and analysis_id:
            _pending_assets[req_id] = {
                "analysis_id": analysis_id, "label": label,
                "kind": "image", "category": category,
            }
        return jsonify({"request_id": req_id, "label": label})
    except httpx.HTTPStatusError as e:
        body_text = e.response.text[:300] if hasattr(e,"response") else ""
        print(f"[generate-image] FAL HTTP {e.response.status_code}: {body_text}")
        return jsonify({"error": f"FAL error {e.response.status_code}: {body_text[:120]}"}), 502
    except Exception as e:
        print(f"[generate-image] error for {label!r}: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/image-status/<request_id>")
def image_status(request_id):
    try:
        r = httpx.get(
            f"https://queue.fal.run/{IMAGE_BASE_PATH}/requests/{request_id}/status",
            headers={"Authorization": f"Key {FAL_KEY}"}, timeout=10.0)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error": str(e), "status": "UNKNOWN"}), 500


@app.route("/image-result/<request_id>")
def image_result(request_id):
    try:
        r = httpx.get(
            f"https://queue.fal.run/{IMAGE_BASE_PATH}/requests/{request_id}",
            headers={"Authorization": f"Key {FAL_KEY}"}, timeout=15.0)
        result = r.json()
        # Mirror the resulting image to Supabase + persist asset row (idempotent via _pending_assets pop)
        meta = _pending_assets.pop(request_id, None)
        if meta and result.get("images"):
            fal_url = result["images"][0].get("url")
            if fal_url:
                sb_url = _mirror_to_storage(fal_url, kind="image")
                if sb_url:
                    _persist_asset(meta["analysis_id"], meta["label"], "image", meta["category"], sb_url)
                    # swap the URL in the response so frontend uses our CDN URL
                    result["images"][0]["url"] = sb_url
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route("/generate-image-local", methods=["POST"])
def generate_image_local():
    """Generate hairstyle image using local SDXL (no FAL required)."""
    if not SDXL_ENABLED:
        return jsonify({"error": "SDXL not installed. Run: pip install sdxl_integration"}), 503
    
    body = request.get_json(silent=True) or {}
    label = (body.get("label") or "").strip()
    description = (body.get("description") or "").strip()
    category = body.get("category", "best")
    analysis_id = body.get("analysis_id")
    
    if not label:
        return jsonify({"error": "missing label"}), 400
    if not description:
        description = f"Professional hairstyle portrait: {label}"
    
    try:
        gen = get_generator()
        img = gen.generate(
            prompt=description,
            steps=20,
            guidance_scale=7.5
        )
        
        out_dir = Path(DATA_DIR) / "generated_images"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{analysis_id}_{label.replace(' ', '_')}.png"
        gen.save(img, str(out_path))
        
        import base64
        with open(out_path, "rb") as f:
            img_base64 = base64.b64encode(f.read()).decode()
        
        return jsonify({
            "request_id": f"local_{analysis_id}_{label}",
            "label": label,
            "image_url": f"data:image/png;base64,{img_base64}",
            "local_path": str(out_path)
        })
    
    except Exception as e:
        print(f"[generate-image-local] error: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/generate-video", methods=["POST"])
def generate_video():
    """Submit Veo 3 fast image-to-video. Returns request_id."""
    if not FAL_KEY: return jsonify({"error":"FAL_API_KEY not configured"}), 503
    image_url = None; prompt = None
    if "image" in request.files:
        if not fal_client: return jsonify({"error":"fal-client missing"}), 503
        f = request.files["image"]; raw = f.read()
        if not raw: return jsonify({"error":"empty image"}), 400
        if len(raw) > MAX_UPLOAD_BYTES: return jsonify({"error":"too large"}), 413
        suffix = ".jpg" if (f.mimetype or "").endswith("jpeg") else ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw); tmp_path = tmp.name
        try: image_url = fal_client.upload_file(tmp_path)
        finally:
            try: os.unlink(tmp_path)
            except OSError: pass
        prompt = request.form.get("prompt") or None
    else:
        body = request.get_json(silent=True) or {}
        image_url = body.get("image_url"); prompt = body.get("prompt")
    if not image_url: return jsonify({"error":"missing image"}), 400
    prompt = prompt or (
        "The person smoothly turns their head from facing forward, to the right, "
        "back to center, then to the left, showing the haircut from multiple angles. "
        "Hair moves naturally with the motion - bouncy, layered, dimensional, "
        "with visible swing and shape. They give a small, natural smile. "
        "Soft natural daylight, salon editorial photography, photorealistic, "
        "smooth realistic motion. Same person, same outfit, same lighting throughout."
    )
    try:
        r = httpx.post(
            f"https://queue.fal.run/{VIDEO_SUBMIT_PATH}",
            headers={"Authorization": f"Key {FAL_KEY}", "Content-Type": "application/json"},
            json={"prompt": prompt, "image_url": image_url, "duration": "5",
                  "negative_prompt": "blurry, distorted face, different person, identity change"},
            timeout=15.0)
        r.raise_for_status()
        data = r.json()
        req_id = data.get("request_id")
        body = request.get_json(silent=True) or {}
        analysis_id = body.get("analysis_id")
        label = body.get("label", "video")
        category = body.get("category", "best")
        if req_id and analysis_id:
            _pending_assets[req_id] = {
                "analysis_id": analysis_id, "label": label,
                "kind": "video", "category": category,
            }
        return jsonify({"request_id": req_id, "image_url": image_url})
    except httpx.HTTPStatusError as e:
        body_text = e.response.text[:300] if hasattr(e,"response") else ""
        print(f"[generate-video] FAL HTTP {e.response.status_code}: {body_text}")
        return jsonify({"error":f"FAL error {e.response.status_code}: {body_text[:120]}"}), 502
    except Exception as e:
        print(f"[generate-video] {e}")
        return jsonify({"error":str(e)}), 500


@app.route("/video-status/<request_id>")
def video_status(request_id):
    try:
        r = httpx.get(
            f"https://queue.fal.run/{VIDEO_BASE_PATH}/requests/{request_id}/status",
            headers={"Authorization": f"Key {FAL_KEY}"}, timeout=10.0)
        return jsonify(r.json())
    except Exception as e:
        return jsonify({"error":str(e),"status":"UNKNOWN"}), 500


@app.route("/video-result/<request_id>")
def video_result(request_id):
    try:
        r = httpx.get(
            f"https://queue.fal.run/{VIDEO_BASE_PATH}/requests/{request_id}",
            headers={"Authorization": f"Key {FAL_KEY}"}, timeout=15.0)
        result = r.json()
        meta = _pending_assets.pop(request_id, None)
        video = result.get("video") or {}
        fal_url = video.get("url") or result.get("url")
        if meta and fal_url:
            sb_url = _mirror_to_storage(fal_url, kind="video")
            if sb_url:
                _persist_asset(meta["analysis_id"], meta["label"], "video", meta["category"], sb_url)
                if "video" in result:
                    result["video"]["url"] = sb_url
                else:
                    result["url"] = sb_url
        return jsonify(result)
    except Exception as e:
        print(f"[video-result] {e}")
        return jsonify({"error":str(e)}), 500


@app.route("/save-lead", methods=["POST"])
def save_lead():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    if not email or "@" not in email or "." not in email:
        return jsonify({"error":"invalid email"}), 400
    name = (body.get("name") or "").strip()
    opt_in = bool(body.get("opt_in"))
    summary = body.get("summary") or {}
    style_identity = summary.get("style_identity","")
    vibe = summary.get("vibe","")
    hair_type = (summary.get("hair") or {}).get("type","")
    color_season = (summary.get("color") or {}).get("season","")

    is_new = not LEADS_CSV.exists()
    with LEADS_CSV.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(["timestamp","email","name","opt_in","style_identity","vibe","hair_type","color_season"])
        w.writerow([datetime.utcnow().isoformat(), email, name, opt_in,
                    style_identity, vibe, hair_type, color_season])
    print(f"[lead] +1 ({email}, total={_count_leads()})")
    return jsonify({"ok": True, "total_leads": _count_leads()})


# --- ADMIN (browse past sessions) ---
@app.route("/admin")
def admin_page():
    return send_from_directory(HERE, "admin.html")


@app.route("/admin/data")
def admin_data():
    """Returns all analyses + their assets, newest first.
    No auth — leave private (don't link from index.html)."""
    if not sb_admin:
        return jsonify({"error": "Supabase not configured", "analyses": [], "count": 0}), 503
    try:
        an = sb_admin.table("halo_analyses").select("*").order(
            "created_at", desc=True
        ).limit(200).execute()
        analyses = an.data or []
        if analyses:
            ids = [a["id"] for a in analyses]
            assets = sb_admin.table("halo_style_assets").select("*").in_(
                "analysis_id", ids
            ).order("created_at", desc=False).execute()
            by_aid: dict = {}
            for a in (assets.data or []):
                by_aid.setdefault(a["analysis_id"], []).append(a)
            for a in analyses:
                a["assets"] = by_aid.get(a["id"], [])
        return jsonify({"ok": True, "count": len(analyses), "analyses": analyses})
    except Exception as e:
        print(f"[admin] data fetch failed: {e}")
        return jsonify({"error": str(e), "analyses": [], "count": 0}), 500


# --- HALO STUDIO (the Atelier) ---
try:
    from studio import register_studio
    register_studio(app)
except Exception as _studio_e:
    print(f"[studio] not mounted: {_studio_e}")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8765"))
    print(f"\n  HALO - Personal Style Analysis at http://localhost:{port}")
    print(f"  HALO STUDIO (Atelier) at        http://localhost:{port}/studio/")
    print(f"  OpenAI:    {'OK' if OPENAI_KEY else 'MISSING'}    Model: {MODEL}")
    print(f"  FAL key:   {'OK' if FAL_KEY else 'MISSING'}")
    print(f"  fal-client:{'OK' if fal_client else 'MISSING'}")
    print(f"  Supabase:  {'OK (persistence enabled)' if sb_admin else 'MISSING (analyses not persisted)'}")
    print(f"  Leads:     {_count_leads()} captured ({LEADS_CSV})\n")
    app.run(host="127.0.0.1", port=port, debug=False)
