"""Render beberapa frame kecil (480p, sedikit sampel) lalu buat lembar kontak.

Jalankan (setelah bangun.py):
    blender --background --python cek.py                    # frame tengah tiap shot
    blender --background --python cek.py -- 1 200 700       # frame pilihan
    blender --background --python cek.py -- --shot 1 2 3 4  # frame tengah shot pilihan
    blender --background --python cek.py -- --shot 1 --motor --kurir  # ditambah close-up

--motor : motor dari depan-kanan ke cek/motor.png
--kurir : kurir dari samping (kanan) ke cek/kurir.png
--hp    : layar HP dari dekat ke cek/hp.png
--langkah-anak : anak dari samping, tiga frame per langkah (angkat, tengah, tapak),
          di set sementara (lantai bergaris 10 cm, kaki kiri merah, kanan biru),
          ke cek/langkah_anak.png. Tidak menyimpan apa pun ke film.blend.
Simulasi kain (ponco) dihitung berurutan dari awal cache-nya sebelum render.

Hasil: cek/frame_XXXX.png dan cek/lembar.png.
Setiap gambar diberi cap nomor shot dan frame (fitur stamp Blender),
lalu disusun menjadi satu lembar dengan numpy, tanpa pustaka tambahan.
"""

import math
import os
import sys
import time

import bpy
import numpy as np

AKAR = os.path.dirname(os.path.abspath(__file__))
if AKAR not in sys.path:
    sys.path.insert(0, AKAR)

from film import waktu  # noqa: E402

TEGAK = "--tegak" in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else [])
BERKAS = os.path.join(AKAR, "film_tegak.blend" if TEGAK else "film.blend")
FOLDER = os.path.join(AKAR, "cek", "tegak") if TEGAK else os.path.join(AKAR, "cek")
SISI_PENDEK = 480
SAMPEL = 8
KOLOM = 4
CELAH = 8  # piksel antar gambar di lembar


WAKTU = []  # (frame, detik) tiap render


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
    # Denoiser OIDN di CPU: dengan 8 sampel gambar malam terlalu berbintik untuk dinilai.
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.device = "CPU"
    # Motion blur dan fokus kabur hanya untuk render akhir; cek harus cepat
    r.use_motion_blur = False
    for cam in bpy.data.cameras:
        cam.dof.use_dof = False
    r.image_settings.file_format = "PNG"
    r.image_settings.color_mode = "RGBA"

    r.use_stamp = True
    for nama in ("date", "time", "render_time", "frame", "frame_range", "memory",
                 "hostname", "camera", "lens", "scene", "marker", "filename",
                 "sequencer_strip"):
        setattr(r, f"use_stamp_{nama}", False)
    r.use_stamp_note = True
    r.stamp_font_size = 20


def _cache_semua(scene):
    """Semua point cache simulasi (kain ponco dan partikel cipratan)."""
    for o in scene.objects:
        for m in o.modifiers:
            if m.type == "CLOTH":
                yield o.name, m.point_cache
        for ps in o.particle_systems:
            yield o.name, ps.point_cache


FOLDER_CACHE = os.path.join(AKAR, "blendcache_film_tegak" if TEGAK else "blendcache_film")


def _ada_di_disk(pc):
    """Cache sudah tersimpan di disk (semua frame rentangnya)?"""
    if not os.path.isdir(FOLDER_CACHE):
        return False
    awalan = pc.name + "_"
    n = sum(1 for nm in os.listdir(FOLDER_CACHE) if nm.startswith(awalan))
    return n >= (pc.frame_end - pc.frame_start + 1)


def pastikan_panggang(scene):
    """Hitung simulasi (kain, cipratan) sekali, tersimpan di disk; cek berikutnya langsung memakainya.

    Simulasi dijalankan frame demi frame hanya pada rentang tiap cache, dan
    cache disk (blendcache_film/, nama dari sidik kode di bangun.py) menyimpan
    hasilnya. Selama kode tidak berubah, film.blend yang dibangun ulang tetap
    memakai cache yang sama.
    """
    rentang = []
    for nama, pc in _cache_semua(scene):
        if not pc.use_disk_cache:
            print(f"[cek] PERINGATAN: cache {nama} tidak di disk; jalankan ulang bangun.py")
        if not pc.is_baked:
            rentang.append((pc.frame_start, pc.frame_end))
    if not rentang:
        print("[cek] simulasi sudah dipanggang, langsung render")
        return
    rentang.sort()  # gabungkan rentang yang tumpang tindih, lalu jalankan berurutan
    gabung = [list(rentang[0])]
    for a, b in rentang[1:]:
        if a <= gabung[-1][1] + 1:
            gabung[-1][1] = max(gabung[-1][1], b)
        else:
            gabung.append([a, b])
    mulai = time.time()
    total = sum(b - a + 1 for a, b in gabung)
    print(f"[cek] menghitung simulasi sekali: {total} frame dalam rentang {gabung}", flush=True)
    for a, b in gabung:
        for f in range(a, b + 1):
            scene.frame_set(f)
    # Jadikan frame yang sudah dihitung sebagai cache terpanggang (tanpa menghitung ulang),
    # supaya tetap terpakai setelah berkas dibuka lagi.
    for nama, pc in _cache_semua(scene):
        if not pc.is_baked:
            with bpy.context.temp_override(point_cache=pc):
                bpy.ops.ptcache.bake_from_cache()
    bpy.ops.wm.save_mainfile()
    print(f"[cek] simulasi dihitung sekali dan dipanggang dalam {time.time() - mulai:.0f} detik", flush=True)


def render_frame(scene, frame):
    s = shot_untuk(frame)
    mulai = time.time()
    scene.frame_set(frame)
    scene.render.stamp_note_text = f"{s.nama}  frame {frame}  ({s.judul})"
    jalur = os.path.join(FOLDER, f"frame_{frame:04d}.png")
    scene.render.filepath = jalur
    bpy.ops.render.render(write_still=True)
    WAKTU.append((frame, time.time() - mulai))
    print(f"[cek] {jalur} ({WAKTU[-1][1]:.1f} detik)")
    return jalur


def baca_piksel(jalur):
    img = bpy.data.images.load(jalur, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(h, w, 4)  # baris 0 = bawah gambar


def susun_lembar(jalur_semua, nama="lembar.png", kolom_maks=KOLOM):
    gambar = [baca_piksel(j) for j in jalur_semua]
    h, w = gambar[0].shape[:2]
    kolom = min(kolom_maks if len(gambar) > 4 else 2, len(gambar))
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
    img.filepath_raw = os.path.join(FOLDER, nama)
    img.file_format = "PNG"
    img.save()
    print(f"[cek] lembar kontak: {img.filepath_raw} ({W}x{H}, {len(gambar)} frame)")


# Close-up: nama objek acuan, posisi kamera dan sasaran dalam koordinat motor, lensa
DEKAT = {
    "motor": ("Motor", (2.3, 2.6, 1.3), (0.0, -0.15, 0.65), 35, "Motor dari dekat"),
    "kurir": ("Motor", (3.4, -0.1, 1.2), (0.0, -0.1, 1.0), 32, "Kurir dari samping"),
    # Layar HP dari depan layar (koordinat HP_Layar: Z keluar layar)
    "hp": ("HP_Layar", (0.0, -0.01, 0.48), (0.0, 0.0, 0.0), 50, "Layar HP"),
}


def render_dekat(scene, frame, jenis):
    """Close-up dengan kamera sementara (tidak disimpan ke film.blend).

    Ditambah satu lampu bantu netral yang lembut supaya bentuk bisa dinilai;
    lampu ini hanya ada saat cek, tidak ada di film.
    """
    from mathutils import Vector
    nama, dari, ke, lensa, catatan = DEKAT[jenis]
    acuan = bpy.data.objects.get(nama)
    if acuan is None:
        print(f"[cek] tidak ada objek {nama}")
        return
    scene.frame_set(frame)
    mw = acuan.matrix_world
    data = bpy.data.cameras.new(f"Cek_{jenis}")
    data.lens = lensa
    cam = bpy.data.objects.new(f"Cek_{jenis}", data)
    scene.collection.objects.link(cam)
    cam.location = mw @ Vector(dari)
    cam.rotation_euler = (mw @ Vector(ke) - cam.location).to_track_quat("-Z", "Y").to_euler()
    bantu = bpy.data.lights.new(f"Cek_Lampu_{jenis}", type="AREA")
    bantu.energy = 60.0
    bantu.size = 2.0
    bantu.color = (0.85, 0.9, 1.0)
    lampu = bpy.data.objects.new(f"Cek_Lampu_{jenis}", bantu)
    scene.collection.objects.link(lampu)
    lampu.location = mw @ (Vector(dari) * 0.8 + Vector((0, -1.2, 1.0)))
    lampu.rotation_euler = (mw @ Vector(ke) - lampu.location).to_track_quat("-Z", "Y").to_euler()
    lampu.visible_camera = False
    scene.timeline_markers.clear()  # supaya marker tidak mengganti kamera
    scene.camera = cam
    scene.render.stamp_note_text = f"{catatan}  frame {frame}"
    scene.render.filepath = os.path.join(FOLDER, f"{jenis}.png")
    bpy.ops.render.render(write_still=True)
    scene.collection.objects.unlink(lampu)
    print(f"[cek] {scene.render.filepath}")


def cek_langkah_anak(scene):
    """Anak dari samping kanannya, tiga frame per langkah, di set sementara."""
    import json
    from mathutils import Vector
    rangka = bpy.data.objects["Anak_Rangka"]
    akar = bpy.data.objects["Anak"]
    jadwal = json.loads(rangka["langkah"])
    # Hanya koleksi Anak yang dirender (kurir, pintu, rumah dikecualikan dari view layer)
    for lc in bpy.context.view_layer.layer_collection.children:
        lc.exclude = lc.name != "Anak"
    for o in scene.collection.objects:
        o.hide_render = True
    # Bahan cek: badan abu-abu, kaki kiri merah, kaki kanan biru (bahan siluet asli hampir hitam)
    def bahan(nama, warna):
        b = bpy.data.materials.new(nama)
        b.use_nodes = True
        b.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*warna, 1)
        return b
    sil = bpy.data.objects["Anak_Siluet_siluet"]
    me = sil.data
    me.materials.clear()
    for b in (bahan("cek_badan", (0.45, 0.45, 0.45)), bahan("cek_kiri", (0.7, 0.12, 0.1)),
              bahan("cek_kanan", (0.1, 0.25, 0.75))):
        me.materials.append(b)
    grup = {g.index: g.name for g in sil.vertex_groups}
    sisi_titik = []
    for v in me.vertices:
        nama = max(v.groups, key=lambda g: g.weight, default=None)
        nm = grup.get(nama.group, "badan") if nama else "badan"
        sisi_titik.append(1 if nm.endswith(".L") else 2 if nm.endswith(".R") else 0)
    for p in me.polygons:
        p.material_index = max(sisi_titik[i] for i in p.vertices)
    # Lantai bergaris setiap 10 cm (koordinat anak: +y ke depan)
    M = akar.matrix_world
    mesh = bpy.data.meshes.new("cek_lantai")
    v, f = [], []
    for i in range(-14, 6):
        y0, y1 = i * 0.1, i * 0.1 + (0.1 if i % 2 == 0 else 0.1)
        n = len(v)
        v += [M @ Vector((x, y, -0.002)) for x, y in ((-0.6, y0), (0.6, y0), (0.6, y1), (-0.6, y1))]
        f.append((n, n + 1, n + 2, n + 3))
    mesh.from_pydata([tuple(p) for p in v], [], f)
    gelap, terang = bahan("cek_lantai_a", (0.75, 0.72, 0.65)), bahan("cek_lantai_b", (0.35, 0.33, 0.3))
    mesh.materials.append(gelap)
    mesh.materials.append(terang)
    for i, p in enumerate(mesh.polygons):
        p.material_index = i % 2
    lantai = bpy.data.objects.new("cek_lantai", mesh)
    scene.collection.objects.link(lantai)
    # Cahaya matahari dan latar abu-abu
    matahari = bpy.data.objects.new("cek_matahari", bpy.data.lights.new("cek_matahari", "SUN"))
    matahari.data.energy = 3.0
    scene.collection.objects.link(matahari)
    matahari.rotation_euler = (M.to_3x3() @ Vector((0.6, -0.3, 1.0))).to_track_quat("Z", "Y").to_euler()
    dunia = bpy.data.worlds.new("cek_dunia")
    dunia.use_nodes = True
    dunia.node_tree.nodes["Background"].inputs["Color"].default_value = (0.25, 0.27, 0.3, 1)
    dunia.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    scene.world = dunia
    # Kamera ortografis dari samping kanan anak (+x lokal), memuat seluruh jalur
    data = bpy.data.cameras.new("cek_samping")
    data.type = "ORTHO"
    data.ortho_scale = 2.3  # lebar 2,3 m, tinggi 1,3 m: anak utuh dan lantai terlihat
    cam = bpy.data.objects.new("cek_samping", data)
    scene.collection.objects.link(cam)
    # sedikit dari atas (sekitar 17 derajat) supaya garis lantai di bawah sandal terlihat
    cam.location = M @ Vector((3.0, -0.35, 1.5))
    cam.rotation_euler = ((M @ Vector((0, -0.35, 0.58))) - cam.location).to_track_quat("-Z", "Y").to_euler()
    scene.timeline_markers.clear()
    scene.camera = cam
    for o in bpy.data.cameras:
        o.dof.use_dof = False
    scene.render.use_motion_blur = False

    jalur, sudah = [], set()
    for k, (arah, sisi, a, b) in enumerate(jadwal):
        nomor = k % 4 + 1
        for f, tahap in ((math.floor(a) + 1, "angkat"), (round((a + b) / 2), "tengah"), (math.ceil(b), "tapak")):
            if f in sudah:
                continue
            sudah.add(f)
            scene.frame_set(f)
            scene.render.stamp_note_text = (f"frame {f}  {arah} langkah {nomor}  kaki "
                                            f"{'kiri (merah)' if sisi == 'L' else 'kanan (biru)'}: {tahap}")
            scene.render.filepath = os.path.join(FOLDER, "langkah_anak", f"frame_{f:04d}.png")
            bpy.ops.render.render(write_still=True)
            jalur.append(scene.render.filepath)
            print(f"[cek] {scene.render.filepath}")
    susun_lembar(jalur, "langkah_anak.png", kolom_maks=6)


def main():
    if not os.path.exists(BERKAS):
        sys.exit("[cek] film.blend belum ada. Jalankan dulu: "
                 "blender --background --python bangun.py")
    bpy.ops.wm.open_mainfile(filepath=BERKAS)
    os.makedirs(FOLDER, exist_ok=True)

    arg = argumen()
    if "--langkah-anak" in arg:
        scene = bpy.context.scene
        atur_render_kecil(scene)
        cek_langkah_anak(scene)  # berkas tidak disimpan
        return
    dekat = [j for j in DEKAT if f"--{j}" in arg]
    arg = [a for a in arg if a.lstrip("-") not in DEKAT and a != "--tegak"]
    if "--shot" in arg:
        pilih = {int(a) for a in arg[arg.index("--shot") + 1:]}
        frames = [s.frame_tengah for s in waktu.SHOTS if s.nomor in pilih]
    else:
        frames = [int(a) for a in arg] or [s.frame_tengah for s in waktu.SHOTS]
    scene = bpy.context.scene
    pastikan_panggang(scene)
    atur_render_kecil(scene)
    if TEGAK and frames:
        from film import kamera
        for f in frames:
            nama, utuh, rx, ry = kamera.periksa_tegak(f)
            print(f"[cek] tegak frame {f} {nama}: benda penting {'UTUH' if utuh else 'TERPOTONG'} "
                  f"(x {rx[0]:.2f}-{rx[1]:.2f}, y {ry[0]:.2f}-{ry[1]:.2f})")
    if frames and not (dekat and not arg):
        susun_lembar([render_frame(scene, f) for f in frames])
    for jenis in dekat:
        render_dekat(scene, frames[0] if frames else waktu.SHOTS[0].frame_tengah, jenis)
    if WAKTU:
        rata = sum(t for _, t in WAKTU) / len(WAKTU)
        print(f"[cek] waktu render per frame: rata-rata {rata:.1f} detik, "
              f"terlama {max(t for _, t in WAKTU):.1f} detik ({len(WAKTU)} frame)")


main()
