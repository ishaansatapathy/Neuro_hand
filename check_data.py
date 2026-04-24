from pathlib import Path
from collections import Counter

raw = Path("data/raw")
dirs = sorted([d.name for d in raw.iterdir() if d.is_dir()])
print("Directories in data/raw:")
for d in dirs:
    exts = [".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"]
    imgs = [p for p in (raw / d).rglob("*") if p.suffix.lower() in exts]
    print(f"  {d}: {len(imgs)} images")
    # Show subdirs if any
    subdirs = [s.name for s in (raw / d).iterdir() if s.is_dir()]
    if subdirs:
        for sd in subdirs[:10]:
            sub_imgs = [p for p in (raw / d / sd).rglob("*") if p.suffix.lower() in exts]
            print(f"    /{sd}: {len(sub_imgs)} images")

# Check CUDA
try:
    import torch
    print(f"\nPyTorch device: {'CUDA ' + torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only'}")
except:
    print("\nPyTorch not available or no CUDA")
