export const runtime = "nodejs";

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const DEFAULT_HAIR_MODEL = "gpt-4o";
const IMAGE_SUBMIT_PATH = "fal-ai/nano-banana/edit";
const IMAGE_BASE_PATH = "fal-ai/nano-banana";
const VIDEO_SUBMIT_PATH = "fal-ai/kling-video/v2.5-turbo/pro/image-to-video";
const VIDEO_BASE_PATH = "fal-ai/kling-video";

// SUPABASE (system of record) - REST + Storage via fetch (no extra deps)
const SUPABASE_URL = process.env.SUPABASE_URL || "";
const SUPABASE_SERVICE_KEY =
  process.env.SUPABASE_SERVICE_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY || "";
const SUPABASE_BUCKET = process.env.SUPABASE_BUCKET || "halo-assets";

function sbReady(): boolean {
  return Boolean(SUPABASE_URL && SUPABASE_SERVICE_KEY);
}

function sbHeaders(extra: Record<string, string> = {}): Record<string, string> {
  return {
    apikey: SUPABASE_SERVICE_KEY,
    Authorization: `Bearer ${SUPABASE_SERVICE_KEY}`,
    ...extra,
  };
}

async function sbInsert(table: string, row: Record<string, unknown>): Promise<void> {
  if (!sbReady()) return;
  try {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/${table}`, {
      method: "POST",
      headers: sbHeaders({ "Content-Type": "application/json", Prefer: "return=minimal" }),
      body: JSON.stringify(row),
    });
    if (!res.ok) {
      console.warn(`[supabase] insert ${table} failed`, res.status, await res.text().catch(() => ""));
    }
  } catch (e) {
    console.warn(`[supabase] insert ${table} error`, e);
  }
}

async function sbUploadBytes(
  path: string,
  bytes: ArrayBuffer | Uint8Array | Buffer,
  contentType: string,
): Promise<string | null> {
  if (!sbReady()) return null;
  try {
    const res = await fetch(`${SUPABASE_URL}/storage/v1/object/${SUPABASE_BUCKET}/${path}`, {
      method: "POST",
      headers: sbHeaders({ "Content-Type": contentType, "x-upsert": "true" }),
      body: bytes as BodyInit,
    });
    if (!res.ok) {
      console.warn("[supabase] storage upload failed", res.status, await res.text().catch(() => ""));
      return null;
    }
    return `${SUPABASE_URL}/storage/v1/object/public/${SUPABASE_BUCKET}/${path}`;
  } catch (e) {
    console.warn("[supabase] storage upload error", e);
    return null;
  }
}

async function sbMirrorFromUrl(
  srcUrl: string,
  path: string,
  fallbackType: string,
): Promise<string | null> {
  if (!sbReady()) return null;
  try {
    const r = await fetch(srcUrl);
    if (!r.ok) return null;
    const ct = r.headers.get("content-type") || fallbackType;
    const buf = Buffer.from(await r.arrayBuffer());
    return sbUploadBytes(path, buf, ct);
  } catch (e) {
    console.warn("[supabase] mirror error", e);
    return null;
  }
}

function clientIp(request: Request): string {
  const xff = request.headers.get("x-forwarded-for") || "";
  if (xff) return xff.split(",")[0].trim();
  return request.headers.get("x-real-ip") || "";
}

function randomHex(n: number): string {
  const bytes = new Uint8Array(n);
  crypto.getRandomValues(bytes);
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

const SYSTEM_PROMPT = `You are HALO, a senior salon stylist and seasonal color consultant.
Return only one JSON object. No markdown.

Schema:
{
  "style_identity": "ALL-CAPS 2-4 word identity tagline",
  "vibe": "Effortless | Polished | Editorial | Boho | Classic | Minimalist | Edgy | Soft | Bold",
  "hair": {
    "type": "natural-language hair type",
    "density": "Fine | Medium Density | Thick",
    "color": "natural-language color",
    "face_shape": "Oval | Round | Heart | Square | Long | Diamond",
    "subhead": "short tagline",
    "best_parts": ["3 short labels"],
    "best_lengths": ["3 short labels"],
    "best_styles": ["5 specific, named styles"],
    "good_options": ["4 specific, named styles"],
    "styles_to_avoid": ["5 specific labels with failure mode in parentheses"],
    "key_goals": ["4 short phrases"],
    "quick_tips": ["5 short tips"],
    "bottom_line": "2-3 sentence confident stylist recommendation"
  },
  "style_descriptions": {
    "<style label>": "40-60 word literal visual instruction for image editing"
  },
  "color": {
    "season": "Soft Summer | True Summer | Light Summer | Soft Autumn | True Autumn | Deep Autumn | Light Spring | True Spring | Bright Spring | Cool Winter | Deep Winter | Bright Winter",
    "season_blurb": "1 short sentence",
    "undertone": "Cool | Warm | Neutral",
    "best_colors": [{"name": "label", "hex": "#rrggbb"}],
    "ok_colors": [{"name": "label", "hex": "#rrggbb"}],
    "not_ideal_colors": [{"name": "label", "hex": "#rrggbb"}],
    "best_neutrals": [{"name": "label", "hex": "#rrggbb"}],
    "metals": [{"name": "Silver | Gold | Rose Gold | Pewter | Bronze", "hex": "#rrggbb"}],
    "hair_hex": "#rrggbb",
    "eye_hex": "#rrggbb"
  }
}

Rules:
- FIRST check the image for a visible human face. If you cannot clearly see a human face (e.g. the image is of an object, animal, landscape, fabric, or the face is too obscured), return ONLY this JSON and nothing else: {"error":"no_face","message":"No human face detected in this photo. Please upload a clear front-facing photo of yourself."}
- Give distinctive, non-generic recommendations that match texture, density, face shape, and visible coloring.
- Include exact style_descriptions keys for every label in best_styles, good_options, and styles_to_avoid.
- In every style description specify length, silhouette, layer placement, perimeter, bangs, crown volume, and finish.
- If the person is bald, balding, shaved, or very short-haired, recommend imagined transformations and facial-hair options where appropriate.
- Provide up to 18 best_colors, 6 best_neutrals, 3 ok_colors, 3 not_ideal_colors, 2-3 metals, hair_hex, and eye_hex.`;

type RouteContext = {
  params: Promise<{ path?: string[] }>;
};

export async function GET(request: Request, context: RouteContext) {
  return handleRequest(request, await getPath(context));
}

export async function POST(request: Request, context: RouteContext) {
  return handleRequest(request, await getPath(context));
}

async function getPath(context: RouteContext): Promise<string[]> {
  const params = await context.params;
  return params.path || [];
}

async function handleRequest(request: Request, path: string[]): Promise<Response> {
  const [endpoint, id] = path;

  if (request.method === "GET" && endpoint === "health") {
    return json({
      ok: true,
      openai: Boolean(process.env.OPENAI_API_KEY),
      fal: Boolean(getFalKey()),
      model: process.env.HAIR_MODEL || DEFAULT_HAIR_MODEL,
      video_model: process.env.VIDEO_MODEL || VIDEO_SUBMIT_PATH,
      runtime: "vercel-next",
    });
  }

  if (request.method === "POST" && endpoint === "upload-photo") {
    return uploadPhoto(request);
  }

  if (request.method === "POST" && endpoint === "analyze") {
    return analyze(request);
  }

  if (request.method === "POST" && endpoint === "generate-image") {
    return generateImage(request);
  }

  if (request.method === "GET" && endpoint === "image-status" && id) {
    return falStatus(IMAGE_BASE_PATH, id);
  }

  if (request.method === "GET" && endpoint === "image-result" && id) {
    return falResult(IMAGE_BASE_PATH, id);
  }

  if (request.method === "POST" && endpoint === "generate-video") {
    return generateVideo(request);
  }

  if (request.method === "GET" && endpoint === "video-status" && id) {
    return falStatus(VIDEO_BASE_PATH, id);
  }

  if (request.method === "GET" && endpoint === "video-result" && id) {
    return falResult(VIDEO_BASE_PATH, id);
  }

  if (request.method === "POST" && endpoint === "save-lead") {
    return saveLead(request);
  }

  if (request.method === "POST" && endpoint === "save-favorites") {
    return saveFavorites(request);
  }

  if (request.method === "POST" && endpoint === "save-asset") {
    return saveAsset(request);
  }

  return json({ error: "not found" }, 404);
}

async function uploadPhoto(request: Request): Promise<Response> {
  const image = await readImageFromForm(request);
  if (image instanceof Response) {
    return image;
  }
  return json({ url: await fileToDataUrl(image.file) });
}

async function analyze(request: Request): Promise<Response> {
  if (!process.env.OPENAI_API_KEY) {
    return json({ error: "OPENAI_API_KEY not configured" }, 503);
  }

  const image = await readImageFromForm(request);
  if (image instanceof Response) {
    return image;
  }

  const photoMime = image.file.type || "image/jpeg";
  const photoBuffer = Buffer.from(await image.file.arrayBuffer());
  const dataUrl = `data:${photoMime};base64,${photoBuffer.toString("base64")}`;
  const form = image.form;
  const userContext = [
    ["Primary goal", form.get("goal")],
    ["Heat-styling routine", form.get("heat")],
    ["Desired aesthetic", form.get("aesthetic")],
  ]
    .filter(([, value]) => typeof value === "string" && value.trim())
    .map(([label, value]) => `${label}: ${String(value).trim()}`)
    .join("\n");

  const prompt = userContext
    ? `Analyze this person and return the JSON.\n\nUser context:\n${userContext}`
    : "Analyze this person and return the JSON.";

  const firstAttempt = await requestOpenAIAnalysis(prompt, dataUrl, true);
  if (!firstAttempt.ok) {
    return json({ error: firstAttempt.error }, firstAttempt.status);
  }

  let content = firstAttempt.content;
  if (!content.trim()) {
    console.warn("HALO empty OpenAI analysis; retrying without JSON mode", {
      finish_reason: firstAttempt.finishReason,
      refusal: firstAttempt.refusal,
      usage: firstAttempt.usage,
    });
    const retry = await requestOpenAIAnalysis(
      `${prompt}\n\nReturn one valid JSON object only. Do not include markdown.`,
      dataUrl,
      false,
    );
    if (!retry.ok) {
      return json({ error: retry.error }, retry.status);
    }
    content = retry.content;
    if (!content.trim()) {
      return json(
        {
          error:
            retry.refusal ||
            retry.finishReason ||
            "OpenAI returned an empty analysis after retry",
        },
        502,
      );
    }
  }

  try {
    const parsed = parseJsonObject(content);
    // Face detection guard — model returns {error:"no_face"} when no face visible
    if (isRecord(parsed) && parsed.error === "no_face") {
      return json({
        error: typeof parsed.message === "string"
          ? parsed.message
          : "No human face detected. Please upload a clear front-facing photo of yourself.",
      }, 400);
    }
    const data = validateAnalysis(parsed);
    data._analysis_id = crypto.randomUUID();
    const analysisId = String(data._analysis_id);
    const color = isRecord(data.color) ? data.color : {};

    // Persist to Supabase (system of record) - best effort, never fails request
    try {
      const sessForm = form.get("session");
      const anonSession =
        typeof sessForm === "string" && sessForm.trim() ? sessForm.trim() : crypto.randomUUID();
      const ext = photoMime === "image/png" ? "png" : photoMime === "image/webp" ? "webp" : "jpg";
      const photoUrl = await sbUploadBytes(`photos/${randomHex(16)}.${ext}`, photoBuffer, photoMime);
      await sbInsert("halo_analyses", {
        id: analysisId,
        anon_session: anonSession,
        photo_url: photoUrl,
        analysis_json: data,
        ip_address: clientIp(request) || null,
        user_agent: request.headers.get("user-agent") || null,
      });
    } catch (e) {
      console.warn("[halo] analysis persist failed", e);
    }

    // Log to Notion (non-blocking) - color season lives under data.color.season
    logToNotion(
      analysisId,
      isRecord(data.hair) ? data.hair : {},
      stringField(data, "vibe"),
      stringField(color, "season"),
    );
    notifySlack(
      analysisId,
      isRecord(data.hair) ? data.hair : {},
      stringField(color, "season"),
    );
    return json(data);
  } catch (error) {
    return json({ error: `Could not parse analysis JSON: ${String(error)}` }, 502);
  }
}

async function requestOpenAIAnalysis(
  prompt: string,
  dataUrl: string,
  jsonMode: boolean,
): Promise<
  | {
      ok: true;
      content: string;
      finishReason: string;
      refusal: string;
      usage: unknown;
    }
  | { ok: false; error: string; status: number }
> {
  const body: Record<string, unknown> = {
    model: process.env.HAIR_MODEL || DEFAULT_HAIR_MODEL,
    max_tokens: 3000,
    messages: [
      { role: "system", content: SYSTEM_PROMPT },
      {
        role: "user",
        content: [
          { type: "text", text: prompt },
          { type: "image_url", image_url: { url: dataUrl } },
        ],
      },
    ],
  };
  if (jsonMode) {
    body.response_format = { type: "json_object" };
  }

  const upstream = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  const payload = (await upstream.json().catch(() => ({}))) as Record<
    string,
    unknown
  >;
  if (!upstream.ok) {
    return {
      ok: false,
      error:
        nestedString(payload, ["error", "message"]) ||
        `OpenAI error ${upstream.status}`,
      status: upstream.status,
    };
  }

  return {
    ok: true,
    content: getOpenAIContent(payload),
    finishReason: getOpenAIFinishReason(payload),
    refusal: getOpenAIRefusal(payload),
    usage: payload.usage,
  };
}

async function generateImage(request: Request): Promise<Response> {
  const falKey = getFalKey();
  if (!falKey) {
    return json({ error: "FAL_KEY not configured" }, 503);
  }

  const body = (await request.json().catch(() => ({}))) as Record<
    string,
    unknown
  >;
  const label = stringField(body, "label");
  const referenceUrl = stringField(body, "reference_url");
  if (!label) {
    return json({ error: "missing label" }, 400);
  }
  if (!referenceUrl) {
    return json({ error: "missing reference_url - upload photo first" }, 400);
  }

  const hair = objectField(body, "hair");
  const description = stringField(body, "description");
  const color = stringField(hair, "color") || "natural";
  const htype = stringField(hair, "type") || "natural";
  const stylePhrase =
    description || `styled in ${label} - ${color.toLowerCase()} ${htype.toLowerCase()} hair`;

  const upstream = await fetch(`https://queue.fal.run/${IMAGE_SUBMIT_PATH}`, {
    method: "POST",
    headers: {
      Authorization: `Key ${falKey}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      prompt: buildImagePrompt(stylePhrase),
      image_urls: [referenceUrl],
      num_images: 1,
      output_format: "jpeg",
    }),
  });

  const data = (await upstream.json().catch(() => ({}))) as Record<
    string,
    unknown
  >;
  if (!upstream.ok) {
    return json(
      { error: stringField(data, "error") || `FAL error ${upstream.status}` },
      upstream.status === 401 ? 502 : upstream.status,
    );
  }
  return json({ request_id: stringField(data, "request_id"), label });
}

async function generateVideo(request: Request): Promise<Response> {
  const falKey = getFalKey();
  if (!falKey) {
    return json({ error: "FAL_KEY not configured" }, 503);
  }

  const body = (await request.json().catch(() => ({}))) as Record<
    string,
    unknown
  >;
  const imageUrl = stringField(body, "image_url");
  if (!imageUrl) {
    return json({ error: "missing image" }, 400);
  }

  const prompt =
    stringField(body, "prompt") ||
    "The person smoothly turns their head from facing forward, to the right, back to center, then to the left, showing the haircut from multiple angles. Hair moves naturally with the motion - bouncy, layered, dimensional, with visible swing and shape. They give a small, natural smile. Soft natural daylight, salon editorial photography, photorealistic, smooth realistic motion. Same person, same outfit, same lighting throughout.";

  const upstream = await fetch(
    `https://queue.fal.run/${process.env.VIDEO_MODEL || VIDEO_SUBMIT_PATH}`,
    {
      method: "POST",
      headers: {
        Authorization: `Key ${falKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        prompt,
        image_url: imageUrl,
        duration: "5",
        negative_prompt:
          "blurry, distorted face, different person, identity change, color shift, color change, color grading, hue shift, oversaturated, color cast, tint change, lighting change, skin tone change",
      }),
    },
  );

  const data = (await upstream.json().catch(() => ({}))) as Record<
    string,
    unknown
  >;
  if (!upstream.ok) {
    return json(
      { error: stringField(data, "error") || `FAL error ${upstream.status}` },
      upstream.status === 401 ? 502 : upstream.status,
    );
  }
  return json({ request_id: stringField(data, "request_id"), image_url: imageUrl });
}

async function falStatus(basePath: string, requestId: string): Promise<Response> {
  const falKey = getFalKey();
  if (!falKey) {
    return json({ error: "FAL_KEY not configured", status: "UNKNOWN" }, 503);
  }
  const upstream = await fetch(
    `https://queue.fal.run/${basePath}/requests/${encodeURIComponent(requestId)}/status`,
    { headers: { Authorization: `Key ${falKey}` } },
  );
  return json(await upstream.json().catch(() => ({})), upstream.ok ? 200 : 502);
}

async function falResult(basePath: string, requestId: string): Promise<Response> {
  const falKey = getFalKey();
  if (!falKey) {
    return json({ error: "FAL_KEY not configured" }, 503);
  }
  const upstream = await fetch(
    `https://queue.fal.run/${basePath}/requests/${encodeURIComponent(requestId)}`,
    { headers: { Authorization: `Key ${falKey}` } },
  );
  return json(await upstream.json().catch(() => ({})), upstream.ok ? 200 : 502);
}

// ── SLACK NOTIFICATION ────────────────────────────────────────────────────────
function notifySlack(analysisId: string, hair: Record<string, unknown>, colorSeason: string) {
  const token = process.env.SLACK_BOT_TOKEN;
  const userId = process.env.SLACK_NOTIFY_USER || "U08KSRMG82G"; // Ram's Slack ID
  if (!token) return;
  const hairType    = stringField(hair, "type") || "Unknown";
  const hairColor   = stringField(hair, "color") || "Unknown";
  const hairDensity = stringField(hair, "density") || "Unknown";
  const faceShape   = stringField(hair, "face_shape") || "Unknown";
  const text = `🪞 *New HALO analysis!*\n• Hair: ${hairType} · ${hairColor} · ${hairDensity}\n• Face: ${faceShape}\n• Color season: ${colorSeason || "—"}\n• ID: \`${analysisId}\``;
  fetch("https://slack.com/api/chat.postMessage", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: JSON.stringify({ channel: userId, text }),
  }).catch(e => console.warn("Slack notify failed:", e));
}

async function saveFavorites(request: Request): Promise<Response> {
  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const analysisId = stringField(body, "analysis_id").trim();
  const likedStyles = Array.isArray(body.liked_styles) ? (body.liked_styles as unknown[]).map(String).join(", ") : "";
  const email = stringField(body, "email").trim().toLowerCase();
  const hairType = stringField(body, "hair_type").trim();
  const colorSeason = stringField(body, "color_season").trim();
  if (!likedStyles) return json({ error: "no styles selected" }, 400);

  const apiKey = process.env.NOTION_API_KEY;
  const dbId = process.env.NOTION_FAVORITES_DB_ID || "529034cd8f95455fb9d1ca2f011ea3aa";
  if (apiKey) {
    fetch("https://api.notion.com/v1/pages", {
      method: "POST",
      headers: {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
      },
      body: JSON.stringify({
        parent: { database_id: dbId },
        properties: {
          "Analysis ID":  { title: [{ text: { content: analysisId || "unknown" } }] },
          "Liked Styles": { rich_text: [{ text: { content: likedStyles } }] },
          "Hair Type":    { rich_text: [{ text: { content: hairType } }] },
          "Color Season": { rich_text: [{ text: { content: colorSeason } }] },
          ...(email ? { "Email": { email } } : {}),
        },
      }),
    }).catch(e => console.warn("Notion favorites log failed:", e));
  }
  console.log("HALO favorites", { analysisId, likedStyles, email });
  return json({ ok: true });
}

async function saveLead(request: Request): Promise<Response> {
  const body = (await request.json().catch(() => ({}))) as Record<
    string,
    unknown
  >;
  const email = stringField(body, "email").trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return json({ error: "invalid email" }, 400);
  }
  const leadName = stringField(body, "name").trim();
  const optIn = Boolean(body.opt_in);
  const leadAnalysisId = stringField(body, "analysis_id").trim();
  console.log("HALO lead", { email, name: leadName, opt_in: optIn });
  logLeadToNotion(leadAnalysisId, email, leadName, optIn);
  return json({ ok: true, total_leads: 1 });
}

async function saveAsset(request: Request): Promise<Response> {
  const body = (await request.json().catch(() => ({}))) as Record<string, unknown>;
  const analysisId = stringField(body, "analysis_id").trim();
  const label = stringField(body, "label").trim() || "Style";
  const kind = stringField(body, "kind").trim() === "video" ? "video" : "image";
  const catRaw = stringField(body, "category").trim().toLowerCase();
  const category = ["best", "good", "avoid"].includes(catRaw) ? catRaw : "best";
  const url = stringField(body, "url").trim();
  if (!analysisId || !url) return json({ error: "missing analysis_id or url" }, 400);
  if (!sbReady()) return json({ ok: false, error: "supabase not configured" });

  const folder = kind === "video" ? "videos" : "images";
  const ext = kind === "video" ? "mp4" : "jpg";
  const ctype = kind === "video" ? "video/mp4" : "image/jpeg";
  const storageUrl = await sbMirrorFromUrl(url, `${folder}/${randomHex(16)}.${ext}`, ctype);
  await sbInsert("halo_style_assets", {
    analysis_id: analysisId,
    label,
    kind,
    category,
    storage_url: storageUrl || url,
    position: 0,
  });
  return json({ ok: true, storage_url: storageUrl || url });
}

async function readImageFromForm(
  request: Request,
): Promise<{ form: FormData; file: File } | Response> {
  const form = await request.formData().catch(() => null);
  if (!form) {
    return json({ error: "invalid form data" }, 400);
  }
  const file = form.get("image");
  if (!(file instanceof File)) {
    return json({ error: "no image uploaded" }, 400);
  }
  if (!file.size) {
    return json({ error: "empty file" }, 400);
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return json({ error: "image > 10MB" }, 413);
  }
  const mime = file.type || "image/jpeg";
  if (!["image/jpeg", "image/png", "image/webp", "image/gif"].includes(mime)) {
    return json({ error: "unsupported image type" }, 400);
  }
  return { form, file };
}

async function fileToDataUrl(file: File): Promise<string> {
  const buffer = Buffer.from(await file.arrayBuffer());
  return `data:${file.type || "image/jpeg"};base64,${buffer.toString("base64")}`;
}

function buildImagePrompt(stylePhrase: string): string {
  return `PHOTOREALISTIC HAIR/STYLE TRANSFORMATION of the provided photograph.

NEW LOOK TO RENDER: ${stylePhrase}

INSTRUCTIONS:
1. Render exactly the haircut, shape, bangs, length, finish, and facial-hair details named above.
2. If a length is specified, cut the hair to that length.
3. If bangs, pulled-back hair, top bun, wet slicking, or facial hair are specified, make that change obvious.
4. The transformation must be dramatic and visible.

DO NOT change the face, skin tone, age, expression, outfit, background, body pose, head angle, lighting, jewelry, glasses, makeup, or accessories.

OUTPUT: a photorealistic photograph of the same person in the same outfit and same room, but with the new hairstyle rendered exactly as described. No text, watermark, or border.`;
}

function validateAnalysis(input: unknown): Record<string, unknown> {
  const data = isRecord(input) ? input : {};
  const hair = isRecord(data.hair) ? data.hair : {};
  const color = isRecord(data.color) ? data.color : {};

  data.style_identity = stringField(data, "style_identity") || "YOUR STYLE";
  data.vibe = stringField(data, "vibe") || "Effortless";
  data.style_descriptions = isRecord(data.style_descriptions)
    ? data.style_descriptions
    : {};

  data.hair = {
    type: stringField(hair, "type") || "-",
    density: stringField(hair, "density") || "-",
    color: stringField(hair, "color") || "-",
    face_shape: stringField(hair, "face_shape") || "-",
    subhead: stringField(hair, "subhead"),
    best_parts: arrayField(hair, "best_parts"),
    best_lengths: arrayField(hair, "best_lengths"),
    best_styles: arrayField(hair, "best_styles"),
    good_options: arrayField(hair, "good_options"),
    styles_to_avoid: arrayField(hair, "styles_to_avoid"),
    key_goals: arrayField(hair, "key_goals"),
    quick_tips: arrayField(hair, "quick_tips"),
    bottom_line: stringField(hair, "bottom_line"),
  };

  data.color = {
    season: stringField(color, "season") || "-",
    season_blurb: stringField(color, "season_blurb"),
    undertone: stringField(color, "undertone") || "-",
    best_colors: arrayField(color, "best_colors"),
    ok_colors: arrayField(color, "ok_colors"),
    not_ideal_colors: arrayField(color, "not_ideal_colors"),
    best_neutrals: arrayField(color, "best_neutrals"),
    metals: arrayField(color, "metals"),
    hair_hex: stringField(color, "hair_hex"),
    eye_hex: stringField(color, "eye_hex"),
  };

  return data;
}


// ── NOTION USAGE LOGGING ──────────────────────────────────────────────────────
// Fire-and-forget: never blocks the analysis response
function logToNotion(analysisId: string, hair: Record<string, unknown>, vibe: string, colorSeason = ""): void {
  const apiKey = process.env.NOTION_API_KEY;
  const dbId   = process.env.NOTION_DB_ID || "9d3cc5f89d984977b59d6e3d3795daa6";
  if (!apiKey) return;
  fetch("https://api.notion.com/v1/pages", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
      "Notion-Version": "2022-06-28",
    },
    body: JSON.stringify({
      parent: { database_id: dbId },
      properties: {
        "Analysis ID": { title: [{ text: { content: analysisId } }] },
        "Hair Type":   { rich_text: [{ text: { content: String(hair.type   || "") } }] },
        "Face Shape":  { rich_text: [{ text: { content: String(hair.face_shape || "") } }] },
        "Color Season":{ rich_text: [{ text: { content: colorSeason || "" } }] },
        "Density":     { rich_text: [{ text: { content: String(hair.density || "") } }] },
        "Vibe":        { rich_text: [{ text: { content: vibe } }] },
      },
    }),
  }).catch(e => console.warn("Notion log failed:", e));
}

function logLeadToNotion(analysisId: string, email: string, name: string, optIn: boolean): void {
  const apiKey = process.env.NOTION_API_KEY;
  const dbId   = process.env.NOTION_DB_ID || "9d3cc5f89d984977b59d6e3d3795daa6";
  if (!apiKey) return;
  // Find the existing row by analysis ID and update it, or create a new one
  fetch("https://api.notion.com/v1/pages", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${apiKey}`,
      "Content-Type": "application/json",
      "Notion-Version": "2022-06-28",
    },
    body: JSON.stringify({
      parent: { database_id: dbId },
      properties: {
        "Analysis ID": { title: [{ text: { content: analysisId || "lead-only" } }] },
        "Email":       { email },
        "Opt In":      { checkbox: optIn },
      },
    }),
  }).catch(e => console.warn("Notion lead log failed:", e));
}

function getFalKey(): string {
  return process.env.FAL_KEY || process.env.FAL_API_KEY || "";
}

function json(data: unknown, status = 200): Response {
  return Response.json(data, {
    status,
    headers: {
      "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    },
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function objectField(source: unknown, key: string): Record<string, unknown> {
  return isRecord(source) && isRecord(source[key]) ? source[key] : {};
}

function stringField(source: unknown, key: string): string {
  const value = isRecord(source) ? source[key] : undefined;
  return typeof value === "string" ? value : "";
}

function arrayField(source: unknown, key: string): unknown[] {
  const value = isRecord(source) ? source[key] : undefined;
  return Array.isArray(value) ? value : [];
}

function nestedString(source: unknown, path: string[]): string {
  let cursor = source;
  for (const key of path) {
    if (!isRecord(cursor)) {
      return "";
    }
    cursor = cursor[key];
  }
  return typeof cursor === "string" ? cursor : "";
}

function parseJsonObject(text: string): unknown {
  const trimmed = text.trim().replace(/^```(?:json)?\s*/i, "").replace(/\s*```$/, "");
  try {
    return JSON.parse(trimmed);
  } catch {
    const match = trimmed.match(/\{[\s\S]*\}/);
    if (!match) {
      throw new Error("No JSON object found in model output");
    }
    return JSON.parse(match[0]);
  }
}

function getOpenAIContent(payload: Record<string, unknown>): string {
  const choices = payload.choices;
  if (!Array.isArray(choices)) {
    return "";
  }
  const first = choices[0];
  if (!isRecord(first)) {
    return "";
  }
  const message = first.message;
  if (!isRecord(message)) {
    return "";
  }
  if (typeof message.content === "string") {
    return message.content;
  }
  if (Array.isArray(message.content)) {
    return message.content
      .map((part) => {
        if (typeof part === "string") {
          return part;
        }
        if (!isRecord(part)) {
          return "";
        }
        return stringField(part, "text") || stringField(part, "content");
      })
      .join("");
  }
  return "";
}

function getOpenAIFinishReason(payload: Record<string, unknown>): string {
  const choices = payload.choices;
  if (!Array.isArray(choices) || !isRecord(choices[0])) {
    return "";
  }
  return stringField(choices[0], "finish_reason");
}

function getOpenAIRefusal(payload: Record<string, unknown>): string {
  const choices = payload.choices;
  if (!Array.isArray(choices) || !isRecord(choices[0])) {
    return "";
  }
  const message = choices[0].message;
  if (!isRecord(message)) {
    return "";
  }
  return stringField(message, "refusal");
}
