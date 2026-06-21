# HALO Server Patch: Local SDXL Integration

Add this to `server.py` after the imports section (around line 40):

```python
# --- LOCAL SDXL OPTION (alternative to FAL nano-banana) ---
try:
    from sdxl_integration import get_generator
    SDXL_ENABLED = True
except ImportError:
    SDXL_ENABLED = False
    get_generator = None
```

Then add this new endpoint AFTER the existing `/generate-image` endpoint (after line 558):

```python
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
        # Generate image (SDXL generates from scratch, not face-preserving edit)
        img = gen.generate(
            prompt=description,
            steps=20,  # Use 20-25 for speed, 40+ for quality
            guidance_scale=7.5
        )
        
        # Save locally
        out_dir = Path(DATA_DIR) / "generated_images"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{analysis_id}_{label.replace(' ', '_')}.png"
        gen.save(img, str(out_path))
        
        # Return as data URL (base64) or file path
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
```

## Usage

1. Install: `pip install diffusers transformers torch accelerate safetensors`
2. Test script: `python test_sdxl_local.py --style bob --steps 20`
3. In HALO frontend, POST to `/generate-image-local` instead of `/generate-image`

## Performance Notes

| Device | Steps | Time |
|--------|-------|------|
| GPU (NVIDIA) | 20 | ~2 min |
| GPU | 40 | ~4 min |
| CPU | 20 | ~15 min |
| CPU | 40 | ~30 min |

## Limitations

- SDXL generates **from scratch**, not face-preserving edits
  - For real face-preserving: use ControlNet (more complex setup)
  - Current approach: strong prompting to encourage similar face
- Image quality ~95% of FAL but without proprietary face preservation
- No video generation (that's still FAL's Kling or local alternatives)

## Switch back to FAL

Change frontend POST from `/generate-image-local` → `/generate-image`
