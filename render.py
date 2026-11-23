"""Render akhir film ke PNG per frame, untuk laptop dengan kartu grafis 4 GB.

Jalankan (setelah bangun.py; untuk versi tegak: bangun.py -- --tegak):
    blender --background --python render.py                         # seluruh film, versi lebar
    blender --background --python render.py -- --versi tegak         # 1080x1920
    blender --background --python render.py -- --shot 3              # satu shot
    blender --background --python render.py -- --frame 100 --sampel 16

Hasil: render/<versi>/shotN/frame_XXXX.png (nomor frame film, 1-1800).
Frame yang sudah ada dilewati, jadi render yang terhenti bisa dilanjutkan
dengan perintah yang sama. Setelah semua frame ada: python3 gabung.py.

Berbeda dengan cek.py: ukuran penuh, motion blur dan depth of field menyala,
tanpa cap tulisan, sampel bawaan 128.
"""

import argparse
import os
import sys
import time

import bpy

AKAR = os.path.dirname(os.path.abspath(__file__))
if AKAR not in sys.path:
    sys.path.insert(0, AKAR)

from film import waktu  # noqa: E402

BERKAS = {"lebar": "film.blend", "tegak": "film_tegak.blend"}
UKURAN = {"lebar": (1920, 1080), "tegak": (1080, 1920)}
# Hemat memori untuk kartu grafis 4 GB (aturan proyek: tekstur paling besar 2k)
BATAS_TEKSTUR = "2048"
UBIN = 1024  # render per ubin 1024 px: buffer render dan pass denoiser lebih kecil


def argumen():
    p = argparse.ArgumentParser(prog="render.py")
    p.add_argument("--versi", choices=("lebar", "tegak"), default="lebar")
    p.add_argument("--sampel", type=int, default=128)
    p.add_argument("--shot", type=int, choices=[s.nomor for s in waktu.SHOTS])
    p.add_argument("--frame", type=int)
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])


def shot_untuk(frame):
    for s in waktu.SHOTS:
        if s.frame_mulai <= frame <= s.frame_selesai:
            return s
    sys.exit(f"[render] frame {frame} di luar film ({waktu.FRAME_AWAL}-{waktu.FRAME_AKHIR})")


def jam(detik):
    detik = int(round(detik))
    return f"{detik // 3600}j{detik // 60 % 60:02d}m{detik % 60:02d}d"


# --------------------------------------------------------------------------
# Perangkat

def pilih_perangkat(scene):
    """Kartu grafis OptiX, lalu CUDA; kalau tidak ada, CPU dengan peringatan."""
    pref = bpy.context.preferences.addons["cycles"].preferences
    for jenis in ("OPTIX", "CUDA"):
        try:
            pref.compute_device_type = jenis
        except TypeError:  # jenis ini tidak didukung build Blender ini
            continue
        pref.refresh_devices()
        gpu = [d for d in pref.devices if d.type == jenis]
        if not gpu:
            continue
        for d in pref.devices:
            d.use = d.type == jenis  # CPU tidak ikut: hemat memori, tidak memperlambat ubin
        scene.cycles.device = "GPU"
        # OptiX punya denoiser sendiri di kartu grafis; CUDA memakai OIDN di kartu grafis
        scene.cycles.denoiser = "OPTIX" if jenis == "OPTIX" else "OPENIMAGEDENOISE"
        scene.cycles.denoising_use_gpu = True
        print(f"[render] perangkat: {jenis} - " + ", ".join(d.name for d in gpu), flush=True)
        return jenis
    pref.compute_device_type = "NONE"
    scene.cycles.device = "CPU"
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.denoising_use_gpu = False
    print("[render] PERINGATAN: tidak ada kartu grafis OptiX/CUDA, render memakai CPU "
          f"({os.cpu_count()} inti). Ini jauh lebih lambat.", flush=True)
    return "CPU"


# --------------------------------------------------------------------------
# Pengaturan render

def atur_render(scene, versi, sampel):
    r, c = scene.render, scene.cycles
    lebar, tinggi = UKURAN[versi]
    if (r.resolution_x, r.resolution_y) != (lebar, tinggi):
        sys.exit(f"[render] {BERKAS[versi]} berukuran {r.resolution_x}x{r.resolution_y}, "
                 f"bukan {lebar}x{tinggi}; bangun ulang berkasnya")
    r.resolution_percentage = 100
    r.engine = "CYCLES"
    c.samples = sampel
    c.use_denoising = True
    c.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    # Motion blur dan depth of field menyala (cek.py mematikannya)
    r.use_motion_blur = True
    dof = [cam.name for cam in bpy.data.cameras if cam.dof.use_dof]
    # Hemat memori
    c.texture_limit_render = BATAS_TEKSTUR
    c.debug_use_texture_cache_eviction = True
    c.debug_use_compact_bvh = True
    c.use_auto_tile = True
    c.tile_size = UBIN
    r.use_persistent_data = False  # data scene dibuang setiap frame, tidak menumpuk
    # Berkas: PNG RGB 8-bit tanpa cap tulisan
    r.use_stamp = False
    s = r.image_settings
    s.file_format = "PNG"
    s.color_mode = "RGB"
    s.color_depth = "8"
    s.compression = 15
    r.use_file_extension = True
    print(f"[render] {lebar}x{tinggi}, {sampel} sampel, denoiser {c.denoiser}, motion blur "
          f"{r.motion_blur_shutter}, depth of field di {len(dof)} kamera, tekstur maks {BATAS_TEKSTUR} px, "
          f"ubin {UBIN} px, BVH ringkas", flush=True)


# --------------------------------------------------------------------------
# Simulasi cipratan: sama seperti cek.py, dihitung sekali lalu dipanggang ke disk

def _cache_semua(scene):
    for o in scene.objects:
        for m in o.modifiers:
            if m.type == "CLOTH":
                yield o.name, m.point_cache
        for ps in o.particle_systems:
            yield o.name, ps.point_cache


def pastikan_panggang(scene):
    belum = [(n, pc) for n, pc in _cache_semua(scene) if not pc.is_baked]
    if not belum:
        return
    rentang = sorted({(pc.frame_start, pc.frame_end) for _, pc in belum})
    print(f"[render] menghitung simulasi cipratan sekali: {len(belum)} cache", flush=True)
    mulai = time.time()
    selesai = set()
    for a, b in rentang:
        for f in range(a, b + 1):
            if f not in selesai:
                scene.frame_set(f)
                selesai.add(f)
    for _, pc in belum:
        with bpy.context.temp_override(point_cache=pc):
            bpy.ops.ptcache.bake_from_cache()
    bpy.ops.wm.save_mainfile()
    print(f"[render] simulasi dipanggang dalam {time.time() - mulai:.0f} detik", flush=True)


# --------------------------------------------------------------------------

def jalur_frame(versi, frame):
    s = shot_untuk(frame)
    return os.path.join(AKAR, "render", versi, f"shot{s.nomor}", f"frame_{frame:04d}.png")


def main():
    arg = argumen()
    berkas = os.path.join(AKAR, BERKAS[arg.versi])
    if not os.path.exists(berkas):
        perintah = "bangun.py -- --tegak" if arg.versi == "tegak" else "bangun.py"
        sys.exit(f"[render] {BERKAS[arg.versi]} belum ada. Jalankan dulu: blender --background --python {perintah}")
    if arg.sampel < 1:
        sys.exit("[render] --sampel harus 1 atau lebih")

    if arg.frame is not None:
        frames = [arg.frame]
        shot_untuk(arg.frame)
    elif arg.shot is not None:
        s = next(s for s in waktu.SHOTS if s.nomor == arg.shot)
        frames = list(range(s.frame_mulai, s.frame_selesai + 1))
    else:
        frames = list(range(waktu.FRAME_AWAL, waktu.FRAME_AKHIR + 1))

    # Frame yang sudah selesai dilewati. Berkas sementara (render terputus) dibuang.
    for f in frames:
        sementara = jalur_frame(arg.versi, f)[:-4] + "_sementara.png"
        if os.path.exists(sementara):
            os.remove(sementara)
    sisa = [f for f in frames if not (os.path.exists(jalur_frame(arg.versi, f))
                                      and os.path.getsize(jalur_frame(arg.versi, f)) > 0)]
    print(f"[render] versi {arg.versi}: {len(frames)} frame diminta, {len(frames) - len(sisa)} sudah ada, "
          f"{len(sisa)} akan dirender", flush=True)
    if not sisa:
        return

    bpy.ops.wm.open_mainfile(filepath=berkas)
    scene = bpy.context.scene
    pilih_perangkat(scene)
    atur_render(scene, arg.versi, arg.sampel)
    pastikan_panggang(scene)

    mulai_semua = time.time()
    lama = []
    for i, f in enumerate(sisa, 1):
        s = shot_untuk(f)
        tujuan = jalur_frame(arg.versi, f)
        os.makedirs(os.path.dirname(tujuan), exist_ok=True)
        sementara = tujuan[:-4] + "_sementara"  # Blender menambah .png
        t0 = time.time()
        scene.frame_set(f)
        scene.render.filepath = sementara
        bpy.ops.render.render(write_still=True)
        os.replace(sementara + ".png", tujuan)  # baru dianggap selesai setelah tertulis utuh
        lama.append(time.time() - t0)
        rata = sum(lama[-24:]) / len(lama[-24:])  # rata-rata 24 frame terakhir
        print(f"[render] shot {s.nomor} frame {f:4d} ({i}/{len(sisa)}): {lama[-1]:6.1f} dtk, "
              f"perkiraan sisa {jam(rata * (len(sisa) - i))}", flush=True)
    print(f"[render] selesai: {len(sisa)} frame dalam {jam(time.time() - mulai_semua)}, "
          f"hasil di render/{arg.versi}/", flush=True)


main()
