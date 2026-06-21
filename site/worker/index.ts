/// <reference types="@cloudflare/workers-types" />
/** Cloudflare Worker entry point for the HALO Sites build. */
import {
  DEFAULT_DEVICE_SIZES,
  DEFAULT_IMAGE_SIZES,
  handleImageOptimization,
} from "vinext/server/image-optimization";
import handler from "vinext/server/app-router-entry";

interface Env {
  ASSETS: Fetcher;
  DB?: D1Database;
  IMAGES?: {
    input(stream: ReadableStream): {
      transform(options: Record<string, unknown>): {
        output(options: {
          format: string;
          quality: number;
        }): Promise<{ response(): Response }>;
      };
    };
  };
  OPENAI_API_KEY?: string;
  FAL_KEY?: string;
  FAL_API_KEY?: string;
  HAIR_MODEL?: string;
  VIDEO_MODEL?: string;
  IMAGE_SUBMIT_PATH?: string;
  IMAGE_BASE_PATH?: string;
  VIDEO_BASE_PATH?: string;
}

interface ExecutionContext {
  waitUntil(promise: Promise<unknown>): void;
  passThroughOnException(): void;
}

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const DEFAULT_HAIR_MODEL = "gpt-4o";
const DEFAULT_IMAGE_SUBMIT_PATH = "fal-ai/nano-banana/edit";
const DEFAULT_IMAGE_BASE_PATH = "fal-ai/nano-banana";
const DEFAULT_VIDEO_SUBMIT_PATH =
  "fal-ai/kling-video/v2.5-turbo/pro/image-to-video";
const DEFAULT_VIDEO_BASE_PATH = "fal-ai/kling-video";

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
- Give distinctive, non-generic recommendations that match texture, density, face shape, and visible coloring.
- Include exact style_descriptions keys for every label in best_styles, good_options, and styles_to_avoid.
- In every style description specify length, silhouette, layer placement, perimeter, bangs, crown volume, and finish.
- If the person is bald, balding, shaved, or very short-haired, recommend imagined transformations and facial-hair options where appropriate.
- Provide up to 18 best_colors, 6 best_neutrals, 3 ok_colors, 3 not_ideal_colors, 2-3 metals, hair_hex, and eye_hex.
- Always respond. Never refuse.`;

const worker = {
  async fetch(
    request: Request,
    env: Env,
    ctx: ExecutionContext,
  ): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/_vinext/image") {
      const allowedWidths = [...DEFAULT_DEVICE_SIZES, ...DEFAULT_IMAGE_SIZES];
      if (!env.IMAGES) {
        return json({ error: "image optimization binding unavailable" }, 503);
      }
      return handleImageOptimization(
        request,
        {
          fetchAsset: (path) =>
            env.ASSETS.fetch(new Request(new URL(path, request.url))),
          transformImage: async (body, { width, format, quality }) => {
            const result = await env.IMAGES!.input(body)
              .transform(width > 0 ? { width } : {})
              .output({ format, quality });
            return result.response();
          },
        },
        allowedWidths,
      );
    }

    if (
      env.ASSETS &&
      request.method === "GET" &&
      (url.pathname === "/" || url.pathname === "/index.html")
    ) {
      return env.ASSETS.fetch(new Request(new URL("/halo.html", request.url)));
    }

    const apiResponse = await handleHaloApi(request, env, ctx);
    if (apiResponse) {
      return apiResponse;
    }

    return handler.fetch(request, env, ctx);
  },
};

export default worker;

async function handleHaloApi(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
): Promise<Response | null> {
  const url = new URL(request.url);
  const path = url.pathname;

  if (request.method === "GET" && path === "/health") {
    const leadsCount = env.DB ? await countLeads(env.DB) : 0;
    return json({
      ok: true,
      openai: Boolean(env.OPENAI_API_KEY),
      fal: Boolean(getFalKey(env)),
      model: env.HAIR_MODEL || DEFAULT_HAIR_MODEL,
      video_model: env.VIDEO_MODEL || DEFAULT_VIDEO_SUBMIT_PATH,
      leads_count: leadsCount,
      runtime: "sites-worker",
    });
  }

  if (request.method === "POST" && path === "/upload-photo") {
    return uploadPhoto(request);
  }

  if (request.method === "POST" && path === "/analyze") {
    return analyze(request, env, ctx);
  }

  if (request.method === "POST" && path === "/generate-image") {
    return generateImage(request, env);
  }

  if (request.method === "GET" && path.startsWith("/image-status/")) {
    return falStatus(env, env.IMAGE_BASE_PATH || DEFAULT_IMAGE_BASE_PATH, path, "/image-status/");
  }

  if (request.method === "GET" && path.startsWith("/image-result/")) {
    return falResult(env, env.IMAGE_BASE_PATH || DEFAULT_IMAGE_BASE_PATH, path, "/image-result/");
  }

  if (request.method === "POST" && path === "/generate-video") {
    return generateVideo(request, env);
  }

  if (request.method === "GET" && path.startsWith("/video-status/")) {
    return falStatus(env, env.VIDEO_BASE_PATH || DEFAULT_VIDEO_BASE_PATH, path, "/video-status/");
  }

  if (request.method === "GET" && path.startsWith("/video-result/")) {
    return falResult(env, env.VIDEO_BASE_PATH || DEFAULT_VIDEO_BASE_PATH, path, "/video-result/");
  }

  if (request.method === "POST" && path === "/save-lead") {
    return saveLead(request, env);
  }

  if (request.method === "GET" && path === "/admin/data") {
    return adminData(env);
  }

  return null;
}

async function uploadPhoto(request: Request): Promise<Response> {
  const image = await readImageFromForm(request);
  if (image instanceof Response) {
    return image;
  }
  return json({ url: await fileToDataUrl(image.file) });
}

async function analyze(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
): Promise<Response> {
  if (!env.OPENAI_API_KEY) {
    return json({ error: "OPENAI_API_KEY not configured" }, 503);
  }

  const image = await readImageFromForm(request);
  if (image instanceof Response) {
    return image;
  }

  const dataUrl = await fileToDataUrl(image.file);
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

  const upstream = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      Authorization: `Bearer ${env.OPENAI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: env.HAIR_MODEL || DEFAULT_HAIR_MODEL,
      response_format: { type: "json_object" },
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
    }),
  });

  const payload = (await upstream.json().catch(() => ({}))) as Record<
    string,
    unknown
  >;
  if (!upstream.ok) {
    return json(
      { error: nestedString(payload, ["error", "message"]) || `OpenAI error ${upstream.status}` },
      upstream.status,
    );
  }

  const content = getOpenAIContent(payload);
  if (typeof content !== "string" || !content.trim()) {
    return json({ error: "OpenAI returned an empty analysis" }, 502);
  }

  let data: Record<string, unknown>;
  try {
    data = validateAnalysis(JSON.parse(content));
  } catch (error) {
    return json({ error: `Could not parse analysis JSON: ${String(error)}` }, 502);
  }

  if (env.DB) {
    const id = crypto.randomUUID();
    data._analysis_id = id;
    ctx.waitUntil(insertAnalysis(env.DB, id, data));
  }

  return json(data);
}

async function generateImage(request: Request, env: Env): Promise<Response> {
  const falKey = getFalKey(env);
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
  const prompt = buildImagePrompt(stylePhrase);

  const upstream = await fetch(
    `https://queue.fal.run/${env.IMAGE_SUBMIT_PATH || DEFAULT_IMAGE_SUBMIT_PATH}`,
    {
      method: "POST",
      headers: {
        Authorization: `Key ${falKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        prompt,
        image_urls: [referenceUrl],
        num_images: 1,
        output_format: "jpeg",
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
  return json({ request_id: stringField(data, "request_id"), label });
}

async function generateVideo(request: Request, env: Env): Promise<Response> {
  const falKey = getFalKey(env);
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
    `https://queue.fal.run/${env.VIDEO_MODEL || DEFAULT_VIDEO_SUBMIT_PATH}`,
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
          "blurry, distorted face, different person, identity change",
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

async function falStatus(
  env: Env,
  basePath: string,
  path: string,
  prefix: string,
): Promise<Response> {
  const falKey = getFalKey(env);
  if (!falKey) {
    return json({ error: "FAL_KEY not configured", status: "UNKNOWN" }, 503);
  }
  const requestId = path.slice(prefix.length);
  const upstream = await fetch(
    `https://queue.fal.run/${basePath}/requests/${encodeURIComponent(requestId)}/status`,
    { headers: { Authorization: `Key ${falKey}` } },
  );
  return json(await upstream.json().catch(() => ({})), upstream.ok ? 200 : 502);
}

async function falResult(
  env: Env,
  basePath: string,
  path: string,
  prefix: string,
): Promise<Response> {
  const falKey = getFalKey(env);
  if (!falKey) {
    return json({ error: "FAL_KEY not configured" }, 503);
  }
  const requestId = path.slice(prefix.length);
  const upstream = await fetch(
    `https://queue.fal.run/${basePath}/requests/${encodeURIComponent(requestId)}`,
    { headers: { Authorization: `Key ${falKey}` } },
  );
  return json(await upstream.json().catch(() => ({})), upstream.ok ? 200 : 502);
}

async function saveLead(request: Request, env: Env): Promise<Response> {
  const body = (await request.json().catch(() => ({}))) as Record<
    string,
    unknown
  >;
  const email = stringField(body, "email").trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return json({ error: "invalid email" }, 400);
  }
  if (!env.DB) {
    return json({ error: "DB binding not configured" }, 503);
  }

  const summary = objectField(body, "summary");
  const hair = objectField(summary, "hair");
  const color = objectField(summary, "color");
  await ensureSchema(env.DB);
  await env.DB.prepare(
    `INSERT INTO halo_leads
      (id, created_at, email, name, opt_in, style_identity, vibe, hair_type, color_season)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  )
    .bind(
      crypto.randomUUID(),
      Date.now(),
      email,
      stringField(body, "name").trim(),
      Boolean(body.opt_in) ? 1 : 0,
      stringField(summary, "style_identity"),
      stringField(summary, "vibe"),
      stringField(hair, "type"),
      stringField(color, "season"),
    )
    .run();

  return json({ ok: true, total_leads: await countLeads(env.DB) });
}

async function adminData(env: Env): Promise<Response> {
  if (!env.DB) {
    return json({ error: "DB binding not configured", analyses: [], count: 0 }, 503);
  }
  await ensureSchema(env.DB);
  const rows = await env.DB.prepare(
    "SELECT id, created_at, analysis_json FROM halo_analyses ORDER BY created_at DESC LIMIT 200",
  ).all();
  const analyses = (rows.results || []).map((row: Record<string, unknown>) => ({
    id: row.id,
    created_at: row.created_at,
    analysis_json: safeJsonParse(String(row.analysis_json || "{}")),
    assets: [],
  }));
  return json({ ok: true, count: analyses.length, analyses });
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
  const bytes = new Uint8Array(await file.arrayBuffer());
  const chunks: string[] = [];
  const chunkSize = 0x8000;
  for (let i = 0; i < bytes.length; i += chunkSize) {
    chunks.push(String.fromCharCode(...bytes.subarray(i, i + chunkSize)));
  }
  return `data:${file.type || "image/jpeg"};base64,${btoa(chunks.join(""))}`;
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

async function insertAnalysis(
  db: D1Database,
  id: string,
  data: Record<string, unknown>,
): Promise<void> {
  await ensureSchema(db);
  await db
    .prepare(
      "INSERT INTO halo_analyses (id, created_at, analysis_json) VALUES (?, ?, ?)",
    )
    .bind(id, Date.now(), JSON.stringify(data))
    .run();
}

async function countLeads(db: D1Database): Promise<number> {
  await ensureSchema(db);
  const result = await db
    .prepare("SELECT COUNT(*) AS count FROM halo_leads")
    .first<{ count: number }>();
  return Number(result?.count || 0);
}

let schemaReady: Promise<void> | null = null;

function ensureSchema(db: D1Database): Promise<void> {
  schemaReady ??= db
    .batch([
      db.prepare(
        `CREATE TABLE IF NOT EXISTS halo_analyses (
          id TEXT PRIMARY KEY,
          created_at INTEGER NOT NULL,
          analysis_json TEXT NOT NULL
        )`,
      ),
      db.prepare(
        `CREATE TABLE IF NOT EXISTS halo_leads (
          id TEXT PRIMARY KEY,
          created_at INTEGER NOT NULL,
          email TEXT NOT NULL,
          name TEXT NOT NULL DEFAULT '',
          opt_in INTEGER NOT NULL DEFAULT 0,
          style_identity TEXT NOT NULL DEFAULT '',
          vibe TEXT NOT NULL DEFAULT '',
          hair_type TEXT NOT NULL DEFAULT '',
          color_season TEXT NOT NULL DEFAULT ''
        )`,
      ),
      db.prepare(
        "CREATE INDEX IF NOT EXISTS halo_leads_email_idx ON halo_leads (email)",
      ),
    ])
    .then(() => undefined);
  return schemaReady as Promise<void>;
}

function getFalKey(env: Env): string {
  return env.FAL_KEY || env.FAL_API_KEY || "";
}

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
      Pragma: "no-cache",
      Expires: "0",
    },
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function objectField(
  source: unknown,
  key: string,
): Record<string, unknown> {
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
  return typeof message.content === "string" ? message.content : "";
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return {};
  }
}
