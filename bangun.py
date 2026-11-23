"""Membangun film.blend dari nol.

Jalankan:
    blender --background --python bangun.py               # 1920x1080
    blender --background --python bangun.py -- --vertikal # 1080x1920
    blender --background --python bangun.py -- --tegak    # versi tegak (YouTube Short): film_tegak.blend
"""

import os
import random
import sys

import bpy

AKAR = os.path.dirname(os.path.abspath(__file__))
if AKAR not in sys.path:
    sys.path.insert(0, AKAR)

from film import adegan, cipratan, dunia_kota, hp, kamera, kucing, kurir, motor, shot, waktu  # noqa: E402
from mathutils import Vector  # noqa: E402

SEED = 75
BERKAS = os.path.join(AKAR, "film.blend")


def argumen():
    return sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []


def kosongkan():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def atur_scene(vertikal):
    scene = bpy.context.scene
    scene.name = "Film"
    scene.render.fps = waktu.FPS
    scene.render.fps_base = 1.0
    scene.frame_start = waktu.FRAME_AWAL
    scene.frame_end = waktu.FRAME_AKHIR

    lebar, tinggi = (1080, 1920) if vertikal else (1920, 1080)
    scene.render.resolution_x = lebar
    scene.render.resolution_y = tinggi
    scene.render.resolution_percentage = 100

    scene.render.engine = "CYCLES"
    scene.cycles.samples = 128
    scene.cycles.use_denoising = True
    scene.cycles.use_light_tree = True
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    scene.view_settings.exposure = 0.4
    scene.render.use_motion_blur = True  # motion blur ringan
    scene.render.motion_blur_shutter = 0.25


LAJU_SHOT1 = 7.0  # m/s (25 km/jam), kecepatan tetap


def shot1_motor(m, s1, kol):
    """Shot 1: motor melaju lurus di lajur kiri Jl. Kenanga menjauhi kamera.

    Motor sudah melaju sejak awal pra-gulir kain, supaya di frame pertama
    shot ponco sudah berkibar wajar (tidak tersentak oleh start mendadak).
    Di frame pertama shot motor berada di TITIK["motor_kenanga"].
    """
    # Motor mulai 14 m lebih ke belakang supaya lewat di samping kamera (kamera naik saat motor lewat)
    awal = dunia_kota.TITIK["motor_kenanga"] + Vector((0, -14.0, 0))
    f0 = s1.frame_mulai - kurir.MULAI_KAIN
    f1 = s1.frame_selesai

    def titik(f):
        return (awal.x, awal.y + LAJU_SHOT1 * (f - s1.frame_mulai) / waktu.FPS, 0.0)

    jalur = motor.animasi_jalan(m, [(f0, titik(f0), 0.0), (f1, titik(f1), 0.0)], halus=False,
                                permukaan=dunia_kota.tinggi_permukaan)
    kejadian = cipratan.cari_kejadian(jalur, dunia_kota.GENANGAN, s1.frame_mulai, s1.frame_selesai)
    cipratan.buat(kol, m, kejadian)
    for roda, a, b, g in kejadian:
        print(f"[bangun] cipratan roda {roda} frame {a}-{b} di genangan {dunia_kota.GENANGAN[g]['pusat']}")


def kode_hash():
    """Sidik isi kode pembangun: simulasi hanya perlu dipanggang ulang bila kode berubah."""
    import hashlib
    h = hashlib.sha1()
    for nama in sorted(os.listdir(os.path.join(AKAR, "film"))) + ["bangun.py"]:
        jalur = os.path.join(AKAR, "film", nama) if nama != "bangun.py" else os.path.join(AKAR, nama)
        if nama.endswith(".py"):
            with open(jalur, "rb") as f:
                h.update(f.read())
    return h.hexdigest()[:10]


def atur_cache():
    """Cache simulasi (kain, partikel) disimpan di disk: blendcache_film/."""
    kode = kode_hash()
    for o in bpy.context.scene.objects:
        caches = [m.point_cache for m in o.modifiers if m.type == "CLOTH"]
        caches += [ps.point_cache for ps in o.particle_systems]
        for i, pc in enumerate(caches):
            pc.use_disk_cache = True
            pc.name = f"{o.name}_{i}_{kode}"


def main():
    global BERKAS
    tegak = "--tegak" in argumen()
    vertikal = "--vertikal" in argumen() or tegak
    if tegak:
        BERKAS = os.path.join(AKAR, "film_tegak.blend")
    random.seed(SEED)
    kosongkan()
    atur_scene(vertikal)
    dunia_kota.bangun()
    kol_motor = bpy.data.collections.new("Motor")
    bpy.context.scene.collection.children.link(kol_motor)
    m = motor.buat_motor(kol_motor)
    # Mas Adit duduk di motor; simulasi ponco untuk shot 1 saja
    kol_kurir = bpy.data.collections.new("Kurir")
    bpy.context.scene.collection.children.link(kol_kurir)
    s1 = waktu.SHOTS[0]
    arm = kurir.buat_kurir(kol_kurir)
    kurir.duduk_di(arm, m, s1.frame_mulai, s1.frame_selesai)
    shot1_motor(m, s1, kol_motor)
    # Shot 3: kucing oren, lampu merah ke hijau, jeda 1 detik
    kol_kucing = bpy.data.collections.new("Kucing")
    bpy.context.scene.collection.children.link(kol_kucing)
    kc = kucing.buat_kucing(kol_kucing)
    adegan.shot2(m, arm)
    adegan.shot3(m, arm, kc, kol_kurir)
    adegan.shot45(m, arm, kol_kurir)
    adegan.shot5(m, arm)
    # Shot 6-7: teras rumah tujuan, pintu terbuka, siluet anak dengan kue
    kol_anak = bpy.data.collections.new("Anak")
    bpy.context.scene.collection.children.link(kol_anak)
    adegan.shot67(m, arm, kol_kurir, kol_anak)
    adegan.shot8(arm)
    # HP di setang: navigasi di shot 2, paket terakhir di shot 4-5
    S = waktu.SHOTS
    hp.buat_hp(kol_motor, m, [(S[1].frame_mulai, S[1].frame_selesai)],
               [(S[3].frame_mulai, S[4].frame_selesai)])
    print(f"[bangun] kucing: {kc['jumlah_helai_bulu']} helai bulu")
    kurir.hitung_laju(arm, m, waktu.FRAME_AWAL - kurir.MULAI_KAIN, waktu.FRAME_AKHIR)  # goyang tepi ponco
    shot.bangun_shot()
    kamera.atur()  # gerakan kamera, lensa, fokus kabur (lihat film/kamera.py)
    if tegak:
        kamera.atur_tegak()  # kamera kedua per shot untuk bingkai 9:16
    bpy.ops.wm.save_as_mainfile(filepath=BERKAS)
    atur_cache()  # cache disk hanya bisa diaktifkan setelah berkas tersimpan
    bpy.ops.wm.save_as_mainfile(filepath=BERKAS)
    print(f"[bangun] {BERKAS} tersimpan, {len(waktu.SHOTS)} shot, "
          f"frame {waktu.FRAME_AWAL}-{waktu.FRAME_AKHIR}, "
          f"{'1080x1920' if vertikal else '1920x1080'}")


main()
