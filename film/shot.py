"""Satu set sementara dan satu kamera per shot.

Setiap shot punya koleksi sendiri ("S01", "S02", ...) yang diletakkan
berjajar di sumbu X supaya tidak saling terlihat. Kamera berganti otomatis
lewat marker timeline yang diikat ke kamera shot itu.
"""

import bpy
from mathutils import Vector

from .waktu import SHOTS

JARAK_SET = 40.0  # meter antar set shot di sumbu X


def _bahan(nama, warna):
    bahan = bpy.data.materials.get(nama) or bpy.data.materials.new(nama)
    bahan.use_nodes = True
    bsdf = bahan.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*warna, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.5
    return bahan


def _koleksi(nama):
    kol = bpy.data.collections.new(nama)
    bpy.context.scene.collection.children.link(kol)
    return kol


def _objek(nama, data, kol, lokasi):
    obj = bpy.data.objects.new(nama, data)
    obj.location = lokasi
    kol.objects.link(obj)
    return obj


def _lantai(nama, kol, pusat, bahan):
    mesh = bpy.data.meshes.new(nama)
    s = 10.0
    mesh.from_pydata([(-s, -s, 0), (s, -s, 0), (s, s, 0), (-s, s, 0)], [], [(0, 1, 2, 3)])
    mesh.materials.append(bahan)
    return _objek(nama, mesh, kol, pusat)


def _kubus(nama, kol, pusat, bahan):
    mesh = bpy.data.meshes.new(nama)
    h = 0.5
    v = [(x, y, z) for x in (-h, h) for y in (-h, h) for z in (0, 2 * h)]
    f = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    mesh.from_pydata(v, [], f)
    mesh.materials.append(bahan)
    return _objek(nama, mesh, kol, pusat)


def _tulisan(nama, teks, kol, lokasi, bahan):
    kurva = bpy.data.curves.new(nama, type="FONT")
    kurva.body = teks
    kurva.align_x = "CENTER"
    kurva.size = 0.8
    kurva.extrude = 0.05
    kurva.materials.append(bahan)
    obj = _objek(nama, kurva, kol, lokasi)
    obj.rotation_euler = (1.5708, 0, 0)  # berdiri menghadap kamera (-Y)
    return obj


def _kamera(nama, kol, lokasi, sasaran):
    data = bpy.data.cameras.new(nama)
    data.lens = 35
    data.sensor_fit = "AUTO"  # bekerja untuk 16:9 maupun 9:16
    cam = _objek(nama, data, kol, lokasi)
    arah = Vector(sasaran) - Vector(lokasi)
    cam.rotation_euler = arah.to_track_quat("-Z", "Y").to_euler()
    return cam


def bangun_shot():
    """Buat set sementara, kamera, dan marker untuk semua shot."""
    scene = bpy.context.scene
    lantai = _bahan("Sementara_Lantai", (0.15, 0.15, 0.17))
    kubus = _bahan("Sementara_Kubus", (0.9, 0.45, 0.05))  # oranye boks paket
    huruf = _bahan("Sementara_Tulisan", (0.95, 0.95, 0.95))

    scene.timeline_markers.clear()
    for shot in SHOTS:
        kol = _koleksi(shot.nama)
        x = (shot.nomor - 1) * JARAK_SET
        _lantai(f"{shot.nama}_Lantai", kol, (x, 0, 0), lantai)
        _kubus(f"{shot.nama}_Kubus", kol, (x - 1.5, 0, 0), kubus)
        _tulisan(f"{shot.nama}_Nomor", f"SHOT {shot.nomor}", kol, (x + 1.2, 0, 0.6), huruf)
        cam = _kamera(f"{shot.nama}_Kamera", kol, (x, -9, 3.5), (x, 0, 0.8))

        marker = scene.timeline_markers.new(shot.nama, frame=shot.frame_mulai)
        marker.camera = cam

    scene.camera = bpy.data.objects[f"{SHOTS[0].nama}_Kamera"]
