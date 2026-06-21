#!/usr/bin/env python3
"""
Test Stable Diffusion XL locally as nano-banana replacement.
Generates portrait edits with custom prompts.
"""

import sys
from pathlib import Path
import torch
from diffusers import StableDiffusionXLPipeline
from PIL import Image

# Use GPU if available, else CPU
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
DTYPE = torch.float16 if torch.cuda.is_available() else torch.float32

print(f"[device] {DEVICE} / {DTYPE}")

# Load SDXL (base model)
print("[loading] Stable Diffusion XL (base)...")
pipe = StableDiffusionXLPipeline.from_pretrained(
    "stabilityai/stable-diffusion-xl-base-1.0",
    torch_dtype=DTYPE,
    use_safetensors=True,
    variant="fp16" if DEVICE == "cuda" else None,
)
pipe = pipe.to(DEVICE)
pipe.enable_attention_slicing()

print("[ready] SDXL loaded")

# Example prompts for hair styles
PROMPTS = {
    "bob": "portrait of woman with modern blunt bob haircut, side-swept bangs, professional salon photo",
    "waves": "portrait of woman with long wavy hair, beachy waves, soft lighting, professional headshot",
    "pixie": "portrait of woman with chic short pixie cut, elegant, professional photo",
    "curly": "portrait of woman with natural curly hair, defined curls, beauty photography",
}

def generate(prompt: str, negative_prompt: str = "", height: int = 768, width: int = 512, steps: int = 30):
    """Generate image from prompt."""
    print(f"[gen] {prompt[:60]}...")
    with torch.no_grad():
        result = pipe(
            prompt=prompt,
            negative_prompt=negative_prompt or "blurry, low quality, distorted",
            height=height,
            width=width,
            num_inference_steps=steps,
            guidance_scale=7.5,
        )
    return result.images[0]

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--style", choices=list(PROMPTS.keys()), default="bob", help="Hair style to generate")
    parser.add_argument("--output", default="test_output.png", help="Output image path")
    parser.add_argument("--steps", type=int, default=30, help="Inference steps (20-50)")
    args = parser.parse_args()

    prompt = PROMPTS[args.style]
    img = generate(prompt, steps=args.steps)
    img.save(args.output)
    print(f"[saved] {args.output}")
