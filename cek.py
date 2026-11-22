"""Render beberapa frame kecil (480p, sedikit sampel) lalu buat lembar kontak.

Jalankan (setelah bangun.py):
    blender --background --python cek.py                    # frame tengah tiap shot
    blender --background --python cek.py -- 1 200 700       # frame pilihan

Hasil: cek/frame_XXXX.png dan cek/lembar.png.
Setiap gambar diberi cap nomor shot dan frame (fitur stamp Blender),
lalu disusun menjadi satu lembar dengan numpy, tanpa pustaka tambahan.
"""

import os
import sys

import bpy
import numpy as np

AKAR = os.path.dirname(os.path.abspath(__file__))
if AKAR not in sys.path:
    sys.path.insert(0, AKAR)

from film import waktu  # noqa: E402

BERKAS = os.path.join(AKAR, "film.blend")
FOLDER = os.path.join(AKAR, "cek")
SISI_PENDEK = 480
SAMPEL = 8
KOLOM = 4
CELAH = 8  # piksel antar gambar di lembar


def argumen():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def shot_untuk(frame):
    for s in waktu.SHOTS:
        if s.frame_mulai <= frame <= s.frame_selesai:
            return s
    raise ValueError(f"frame {frame} di luar film ({waktu.FRAME_AWAL}-{waktu.FRAME_AKHIR})")


def atur_render_kecil(scene):
    r = scene.render
    skala = SISI_PENDEK / min(r.resolution_x, r.resolution_y)
    r.resolution_x = round(r.resolution_x * skala / 2) * 2
    r.resolution_y = round(r.resolution_y * skala / 2) * 2
    r.resolution_percentage = 100
    scene.cycles.samples = SAMPEL
    scene.cycles.use_denoising = False
    scene.cycles.device = "CPU"
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"

    r.use_stamp = True
    for nama in ("date", "time", "render_time", "frame", "frame_range", "memory",
                 "hostname", "camera", "lens", "scene", "marker", "filename",
                 "sequencer_strip"):
        setattr(r, f"use_stamp_{nama}", False)
    r.use_stamp_note = True
    r.stamp_font_size = 20


def render_frame(scene, frame):
    s = shot_untuk(frame)
    scene.frame_set(frame)
    scene.render.stamp_note_text = f"{s.nama}  frame {frame}  ({s.judul})"
    jalur = os.path.join(FOLDER, f"frame_{frame:04d}.png")
    scene.render.filepath = jalur
    bpy.ops.render.render(write_still=True)
    print(f"[cek] {jalur}")
    return jalur


def baca_piksel(jalur):
    img = bpy.data.images.load(jalur, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)  # baris 0 = bawah gambar


def susun_lembar(jalur_semua):
    gambar = [baca_piksel(j) for j in jalur_semua]
    h, w = gambar[0].shape[:2]
    kolom = min(KOLOM, len(gambar))
    baris = (len(gambar) + kolom - 1) // kolom
    W = kolom * w + (kolom + 1) * CELAH
    H = baris * h + (baris + 1) * CELAH
    lembar = np.zeros((H, W, 4), dtype=np.float32)
    lembar[..., 3] = 1.0
    for i, g in enumerate(gambar):
        b, k = divmod(i, kolom)
        x = CELAH + k * (w + CELAH)
        y = H - (b + 1) * (h + CELAH)  # baris pertama di atas
        lembar[y:y + h, x:x + w] = g

    img = bpy.data.images.new("lembar", W, H, alpha=True)
    img.pixels.foreach_set(lembar.ravel())
    img.filepath_raw = os.path.join(FOLDER, "lembar.png")
    img.file_format = "PNG"
    img.save()
    print(f"[cek] lembar kontak: {img.filepath_raw} ({W}x{H}, {len(gambar)} frame)")


def main():
    if not os.path.exists(BERKAS):
        sys.exit("[cek] film.blend belum ada. Jalankan dulu: "
                 "blender --background --python bangun.py")
    bpy.ops.wm.open_mainfile(filepath=BERKAS)
    os.makedirs(FOLDER, exist_ok=True)

    frames = [int(a) for a in argumen()] or [s.frame_tengah for s in waktu.SHOTS]
    scene = bpy.context.scene
    atur_render_kecil(scene)
    susun_lembar([render_frame(scene, f) for f in frames])


main()
