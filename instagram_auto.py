import time
import sys
import os
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WATCH_DIR   = Path(os.path.expanduser("~")) / "Documents" / "python"
OUT_INSTA   = WATCH_DIR / "インスタ"
OUT_STORY_B = WATCH_DIR / "ストーリー前"
OUT_STORY_A = WATCH_DIR / "ストーリー後"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tiff", ".bmp"}

IG_W, IG_H = 1080, 1350
IG_PAD_T = 293 / 1350
IG_PAD_B = 294 / 1350
IG_PAD_L = 154 / 1080
IG_PAD_R = 155 / 1080

ST_W, ST_H = 1125, 1990
ST_PAD_T  = 0.301
ST_PAD_L  = 0.144
ST_PAD_R  = 0.145
ST_AREA_H = 0.397

def crop_product(src_path):
    img = Image.open(src_path).convert("RGBA")
    arr = np.array(img.convert("RGB"))
    mask = ~((arr[:,:,0]>240)&(arr[:,:,1]>240)&(arr[:,:,2]>240))
    rows = np.where(mask.any(axis=1))[0]
    cols = np.where(mask.any(axis=0))[0]
    if len(rows) == 0 or len(cols) == 0:
        return None
    return img.crop((cols.min(), rows.min(), cols.max()+1, rows.max()+1))

def make_instagram(img_cropped, out_path):
    W, H = IG_W, IG_H
    area_w = int(W * (1 - IG_PAD_L - IG_PAD_R))
    area_h = int(H * (1 - IG_PAD_T - IG_PAD_B))
    ox = int(W * IG_PAD_L)
    oy = int(H * IG_PAD_T)
    scale = min(area_w / img_cropped.width, area_h / img_cropped.height)
    nw, nh = int(img_cropped.width*scale), int(img_cropped.height*scale)
    img_r = img_cropped.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    canvas.paste(img_r, (ox+(area_w-nw)//2, oy+(area_h-nh)//2), img_r)
    canvas.save(out_path, "JPEG", quality=95)

def make_story(img_cropped, out_before, out_after):
    W, H = ST_W, ST_H
    pad_top   = int(H * ST_PAD_T)
    pad_left  = int(W * ST_PAD_L)
    pad_right = int(W * ST_PAD_R)
    area_w = W - pad_left - pad_right
    area_h = int(H * ST_AREA_H)
    scale = min(area_w / img_cropped.width, area_h / img_cropped.height)
    nw, nh = int(img_cropped.width*scale), int(img_cropped.height*scale)
    img_r = img_cropped.resize((nw, nh), Image.LANCZOS)
    x = pad_left + (area_w - nw) // 2
    y = pad_top  + (area_h - nh) // 2
    canvas = Image.new("RGB", (W, H), (255, 255, 255))
    canvas.paste(img_r, (x, y), img_r)
    canvas.save(out_before, "JPEG", quality=95)
    canvas_after = canvas.copy()
    draw = ImageDraw.Draw(canvas_after)
    fx1 = W//2 - 174
    fx2 = W//2 + 174
    fy  = H - 214
    draw.rounded_rectangle([fx1, fy, fx2, fy+40], radius=18, outline=(200,200,200), width=2)
    canvas_after.save(out_after, "JPEG", quality=95)

def process_image(src_path):
    img = crop_product(src_path)
    if img is None:
        print("  [SKIP]", src_path.name)
        return False
    stem = src_path.stem
    make_instagram(img, OUT_INSTA   / (stem + "_insta.jpg"))
    make_story(img,
               OUT_STORY_B / (stem + "_story_before.jpg"),
               OUT_STORY_A / (stem + "_story_after.jpg"))
    print("  [OK]", src_path.name)
    return True

def batch_process():
    for d in [OUT_INSTA, OUT_STORY_B, OUT_STORY_A]:
        d.mkdir(parents=True, exist_ok=True)
    targets = [
        p for p in WATCH_DIR.iterdir()
        if p.is_file()
        and p.suffix.lower() in IMAGE_EXTS
        and not any(p.is_relative_to(d) for d in [OUT_INSTA, OUT_STORY_B, OUT_STORY_A])
    ]
    if not targets:
        print("No images found.")
        return
    print("Processing", len(targets), "images...")
    ok = ng = 0
    for i, path in enumerate(targets, 1):
        print("[{}/{}]".format(i, len(targets)), path.name)
        if process_image(path): ok += 1
        else: ng += 1
    print("Done! OK:", ok, "/ Skipped:", ng)

class ImageHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        path = Path(event.src_path)
        out_dirs = [OUT_INSTA, OUT_STORY_B, OUT_STORY_A]
        if any(path.is_relative_to(d) for d in out_dirs):
            return
        if path.suffix.lower() not in IMAGE_EXTS:
            return
        time.sleep(0.5)
        print("[Detected]", path.name)
        process_image(path)

def watch_mode():
    for d in [OUT_INSTA, OUT_STORY_B, OUT_STORY_A]:
        d.mkdir(parents=True, exist_ok=True)
    print("Watch :", WATCH_DIR)
    print("Ctrl+C to stop.")
    observer = Observer()
    observer.schedule(ImageHandler(), str(WATCH_DIR), recursive=False)
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("Stopped.")
    observer.join()

if __name__ == "__main__":
    if "--batch" in sys.argv:
        batch_process()
    else:
        watch_mode()
