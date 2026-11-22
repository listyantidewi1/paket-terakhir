"""Membangun film.blend dari nol.

Jalankan:
    blender --background --python bangun.py               # 1920x1080
    blender --background --python bangun.py -- --vertikal # 1080x1920
"""

import os
import random
import sys

import bpy

AKAR = os.path.dirname(os.path.abspath(__file__))
if AKAR not in sys.path:
    sys.path.insert(0, AKAR)

from film import dunia_kota, kurir, motor, shot, waktu  # noqa: E402

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


def main():
    vertikal = "--vertikal" in argumen()
    random.seed(SEED)
    kosongkan()
    atur_scene(vertikal)
    dunia_kota.bangun()
    kol_motor = bpy.data.collections.new("Motor")
    bpy.context.scene.collection.children.link(kol_motor)
    # Untuk sekarang motor diam di Jl. Kenanga (shot 1), menghadap +Y
    m = motor.buat_motor(kol_motor)
    motor.taruh(m, dunia_kota.TITIK["motor_kenanga"])
    # Mas Adit duduk di motor (shot 1); simulasi ponco untuk shot 1 saja
    kol_kurir = bpy.data.collections.new("Kurir")
    bpy.context.scene.collection.children.link(kol_kurir)
    s1 = waktu.SHOTS[0]
    kurir.duduk_di(kurir.buat_kurir(kol_kurir), m, s1.frame_mulai, s1.frame_selesai)
    shot.bangun_shot()
    bpy.ops.wm.save_as_mainfile(filepath=BERKAS)
    print(f"[bangun] {BERKAS} tersimpan, {len(waktu.SHOTS)} shot, "
          f"frame {waktu.FRAME_AWAL}-{waktu.FRAME_AKHIR}, "
          f"{'1080x1920' if vertikal else '1920x1080'}")


main()
