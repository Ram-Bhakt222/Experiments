# HALO Public Site

This is the hosted HALO web app. It keeps the original single-file HALO UI in
`public/halo.html` and serves it through a small Next app.

Live production URL:

```text
https://site-mu-nine-30.vercel.app
```

## Commands

```bash
npm install
npx next build
npm run build
```

- `npx next build` validates the public Vercel deployment path.
- `npm run build` validates the Sites/Vinext Worker build path.

## Runtime Variables

Set these in the production host, not in Git:

```text
OPENAI_API_KEY
FAL_KEY
```

Optional:

```text
HAIR_MODEL
VIDEO_MODEL
```

## Structure

- `app/page.tsx` loads the HALO UI full-screen.
- `app/api/halo/[...path]/route.ts` provides Vercel API endpoints for the
  existing frontend routes like `/analyze`, `/generate-image`, and `/health`.
- `worker/index.ts` keeps the Cloudflare/Sites Worker implementation.
- `vercel.json` rewrites the legacy root API paths into the Next API route.
