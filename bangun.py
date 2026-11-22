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

from film import shot, waktu  # noqa: E402

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
    scene.render.image_settings.file_format = "PNG"

    dunia = bpy.data.worlds.new("Malam")
    latar = dunia.node_tree.nodes["Background"]
    latar.inputs["Color"].default_value = (0.02, 0.03, 0.06, 1.0)
    latar.inputs["Strength"].default_value = 1.0
    scene.world = dunia


def lampu_sementara():
    data = bpy.data.lights.new("Sementara_Matahari", type="SUN")
    data.energy = 3.0
    obj = bpy.data.objects.new("Sementara_Matahari", data)
    obj.rotation_euler = (0.8, 0.2, 0.6)
    bpy.context.scene.collection.objects.link(obj)


def main():
    vertikal = "--vertikal" in argumen()
    random.seed(SEED)
    kosongkan()
    atur_scene(vertikal)
    lampu_sementara()
    shot.bangun_shot()
    bpy.ops.wm.save_as_mainfile(filepath=BERKAS)
    print(f"[bangun] {BERKAS} tersimpan, {len(waktu.SHOTS)} shot, "
          f"frame {waktu.FRAME_AWAL}-{waktu.FRAME_AKHIR}, "
          f"{'1080x1920' if vertikal else '1920x1080'}")


main()
