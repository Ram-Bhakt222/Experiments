export const runtime = "nodejs";

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024;
const DEFAULT_HAIR_MODEL = "gpt-4o";
const IMAGE_SUBMIT_PATH = "fal-ai/nano-banana/edit";
const IMAGE_BASE_PATH = "fal-ai/nano-banana";
const VIDEO_SUBMIT_PATH = "fal-ai/kling-video/v2.5-turbo/pro/image-to-video";
const VIDEO_BASE_PATH = "fal-ai/kling-video";

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
      Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: process.env.HAIR_MODEL || DEFAULT_HAIR_MODEL,
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
  if (!content.trim()) {
    return json({ error: "OpenAI returned an empty analysis" }, 502);
  }

  try {
    const data = validateAnalysis(JSON.parse(content));
    data._analysis_id = crypto.randomUUID();
    return json(data);
  } catch (error) {
    return json({ error: `Could not parse analysis JSON: ${String(error)}` }, 502);
  }
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

async function saveLead(request: Request): Promise<Response> {
  const body = (await request.json().catch(() => ({}))) as Record<
    string,
    unknown
  >;
  const email = stringField(body, "email").trim().toLowerCase();
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return json({ error: "invalid email" }, 400);
  }
  console.log("HALO lead", {
    email,
    name: stringField(body, "name").trim(),
    opt_in: Boolean(body.opt_in),
  });
  return json({ ok: true, total_leads: 1 });
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
