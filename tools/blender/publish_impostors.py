"""Convert baked impostor atlases (PNG) to WebP for the web app and write the manifest.
usage: python publish_impostors.py <bake_out_dir> <public_dir> <manifest.json> name [name...]"""
import json
import os
import sys

from PIL import Image

src, pub, manifest, *names = sys.argv[1:]
os.makedirs(pub, exist_ok=True)
specs = []
for n in names:
    c = Image.open(os.path.join(src, f"{n}_color.png")).convert("RGBA")
    c.save(os.path.join(pub, f"{n}_color.webp"), "WEBP", quality=88, method=4, exact=True)
    nm = Image.open(os.path.join(src, f"{n}_normal.png")).convert("RGB")
    nm.save(os.path.join(pub, f"{n}_normal.webp"), "WEBP", quality=90, method=4)
    spec = json.load(open(os.path.join(src, f"{n}.json")))
    specs.append({k: spec[k] for k in ("name", "frames", "px", "height", "radius", "centre")})
    print(n, os.path.getsize(os.path.join(pub, f"{n}_color.webp")) // 1024, "KB +",
          os.path.getsize(os.path.join(pub, f"{n}_normal.webp")) // 1024, "KB")
json.dump(specs, open(manifest, "w"), indent=1)
