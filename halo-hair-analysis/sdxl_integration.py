"""
Local SDXL integration for HALO image generation.
Replaces FAL nano-banana calls with local Stable Diffusion XL.

Usage in server.py:
    from sdxl_integration import SDXLGenerator
    gen = SDXLGenerator()
    result_img = gen.generate(prompt, reference_url, ...)
"""

import torch
from diffusers import StableDiffusionXLPipeline
from PIL import Image
import requests
from io import BytesIO
import os
from pathlib import Path

class SDXLGenerator:
    def __init__(self, model_id="stabilityai/stable-diffusion-xl-base-1.0", device=None, dtype=None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.dtype = dtype or (torch.float16 if torch.cuda.is_available() else torch.float32)
        
        print(f"[SDXL] Loading {model_id} on {self.device}/{self.dtype}")
        self.pipe = StableDiffusionXLPipeline.from_pretrained(
            model_id,
            torch_dtype=self.dtype,
            use_safetensors=True,
            variant="fp16" if self.device == "cuda" else None,
        )
        self.pipe = self.pipe.to(self.device)
        self.pipe.enable_attention_slicing()
        print("[SDXL] Ready")

    def download_image(self, url: str) -> Image.Image:
        """Download image from URL."""
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return Image.open(BytesIO(resp.content)).convert("RGB")
        except Exception as e:
            print(f"[SDXL] Failed to download {url}: {e}")
            return None

    def generate(self, prompt: str, reference_url: str = None, height: int = 768, 
                 width: int = 512, steps: int = 25, guidance_scale: float = 7.5) -> Image.Image:
        """
        Generate image from prompt using SDXL.
        
        Args:
            prompt: Detailed style description (from GPT analysis)
            reference_url: URL of user's photo (for context, not used in edit - SDXL generates from scratch)
            height, width: Output dimensions
            steps: Inference steps (20-50, more = better quality but slower)
            guidance_scale: How closely to follow prompt
        
        Returns:
            PIL Image object
        """
        print(f"[SDXL] Generating: {prompt[:80]}...")
        
        # SDXL generates from scratch, not face-preserving edit
        # We enhance prompt to maintain face similarity
        enhanced_prompt = f"{prompt}\nPHOTOREALISTIC PORTRAIT. High quality."
        negative_prompt = "blurry, low quality, distorted, ugly, bad anatomy"
        
        with torch.no_grad():
            result = self.pipe(
                prompt=enhanced_prompt,
                negative_prompt=negative_prompt,
                height=height,
                width=width,
                num_inference_steps=steps,
                guidance_scale=guidance_scale,
            )
        
        img = result.images[0]
        print(f"[SDXL] Generated {img.size}")
        return img

    def save(self, img: Image.Image, path: str):
        """Save image to disk."""
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        img.save(path)
        print(f"[SDXL] Saved to {path}")
        return path

# Singleton instance
_generator = None

def get_generator():
    global _generator
    if _generator is None:
        _generator = SDXLGenerator()
    return _generator
