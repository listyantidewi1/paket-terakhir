"""Satu kamera per shot, berganti otomatis lewat marker di timeline.

Shot yang sudah punya lokasi di kota memakai kamera dari tabel KAMERA.
Shot lain masih memakai set sementara (lantai, kubus, nomor shot) yang
diletakkan jauh dari kota supaya tidak terlihat.
"""

import bpy
from mathutils import Vector

from . import dunia_kota as kota
from .waktu import SHOTS

T = kota.TITIK

# nomor shot: (lokasi kamera, titik sasaran, lensa mm). Kamera statis dulu;
# gerakan kamera dari storyboard dibuat nanti bersama isi adegan.
KAMERA = {
    # Wide rendah dekat genangan, menatap Jl. Kenanga ke arah motor pergi
    1: (T["motor_kenanga"] + Vector((0.6, -7.5, 0.35)), T["motor_kenanga"] + Vector((0.4, 40, 3.0)), 24),
    # Dari belakang-atas bahu kanan pengendara (posisi kepala saat duduk):
    # layar GPS di latar depan bawah, jalan kecil, simpang tiga, kali di kanan
    2: (T["motor_kali"] + Vector((0.22, -0.32, 1.62)), T["motor_kali"] + Vector((0.35, 5.0, 0.35)), 22),
    # Belakang-samping motor di lampu merah: lampu lalu lintas, warung, bangku
    3: (T["motor_lampu_merah"] + Vector((2.6, -5.5, 1.45)), T["bangku_warung"] + Vector((0.6, 3.0, 1.1)), 28),
    # Dari belakang motor di mulut Gang Melati, menyusuri gang
    4: (T["mulut_gang"] + Vector((0.0, -6.5, 1.65)), T["mulut_gang"] + Vector((0.0, 30.0, 1.8)), 24),
}

def _kamera_rumah():
    """Kamera shot 6 dan 7 di rumah tujuan (titiknya baru ada setelah kota dibangun)."""
    if "teras_tujuan" not in T:
        return {}
    P, luar, pintu = T["teras_tujuan"], T["pintu_keluar"], T["pintu_tujuan"]
    kanan = (-luar).cross(Vector((0, 0, 1))).normalized()  # kanan kurir yang menghadap pintu
    # Posisi dari pencarian otomatis (proyeksi ke layar + uji penghalang dengan sinar):
    # shot 6 memuat seluruh badan kurir; shot 7 menaruh kepala dan bahu kurir di
    # sepertiga kiri, kue dan kepala anak di tengah tanpa terhalang.
    P7 = P - kanan * 0.2  # di shot 7 kurir bergeser 20 cm ke kirinya (adegan.shot67)
    tengah7 = T["lantai_dalam"] + luar * 0.11 + Vector((0, 0, 0.86))  # antara kue dan kepala anak
    return {
        # Statis dari belakang kurir, rendah; seluruh badan masuk frame
        6: (P + luar * 1.8 + kanan * 0.6 + Vector((0, 0, 0.8)), P + Vector((0, 0, 0.95)) - luar * 0.2, 20),
        # Over-the-shoulder dari belakang bahu kanan kurir
        7: (P7 + luar * 0.8 + kanan * 0.95 + Vector((0, 0, 1.85)), tengah7, 35),
        # Shot 5 dan 8: posisi awal saja; gerakannya diatur di kamera.py
        5: (P + luar * 2 + Vector((0, 0, 1.5)), P, 85),
        8: (P + luar * 3 + Vector((0, 6, 1.7)), P, 24),
    }


SET_SEMENTARA_Y = -2000.0  # jauh dari semua lokasi kota
JARAK_SET = 40.0


def _bahan(nama, warna):
    bahan = bpy.data.materials.get(nama) or bpy.data.materials.new(nama)
    if bahan.node_tree is None:
        bahan.use_nodes = True
    bsdf = bahan.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*warna, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.5
    return bahan


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


def _kamera(nama, kol, lokasi, sasaran, lensa=35):
    data = bpy.data.cameras.new(nama)
    data.lens = lensa
    data.sensor_fit = "AUTO"  # bekerja untuk 16:9 maupun 9:16
    data.clip_start = 0.05
    data.clip_end = 500
    cam = _objek(nama, data, kol, lokasi)
    arah = Vector(sasaran) - Vector(lokasi)
    cam.rotation_euler = arah.to_track_quat("-Z", "Y").to_euler()
    return cam


def _set_sementara(shot, kol):
    lantai = _bahan("Sementara_Lantai", (0.15, 0.15, 0.17))
    kubus = _bahan("Sementara_Kubus", (0.9, 0.45, 0.05))  # oranye boks paket
    huruf = _bahan("Sementara_Tulisan", (0.95, 0.95, 0.95))
    x = (shot.nomor - 1) * JARAK_SET
    y = SET_SEMENTARA_Y
    _lantai(f"{shot.nama}_Lantai", kol, (x, y, 0), lantai)
    _kubus(f"{shot.nama}_Kubus", kol, (x - 1.5, y, 0), kubus)
    _tulisan(f"{shot.nama}_Nomor", f"SHOT {shot.nomor}", kol, (x + 1.2, y, 0.6), huruf)
    data = bpy.data.lights.new(f"{shot.nama}_Lampu", type="POINT")  # bukan SUN: matahari menerangi kota
    data.energy = 4000.0
    _objek(f"{shot.nama}_Lampu", data, kol, (x + 4, y - 6, 8))
    return (x, y - 9, 3.5), (x, y, 0.8), 35


def bangun_shot():
    """Buat kamera (dan set sementara bila perlu) serta marker untuk semua shot."""
    scene = bpy.context.scene
    induk = bpy.data.collections.new("Shot")
    scene.collection.children.link(induk)

    kamera = {**KAMERA, **_kamera_rumah()}
    scene.timeline_markers.clear()
    for shot in SHOTS:
        kol = bpy.data.collections.new(shot.nama)
        induk.children.link(kol)
        if shot.nomor in kamera:
            lokasi, sasaran, lensa = kamera[shot.nomor]
        else:
            lokasi, sasaran, lensa = _set_sementara(shot, kol)
        cam = _kamera(f"{shot.nama}_Kamera", kol, lokasi, sasaran, lensa)
        marker = scene.timeline_markers.new(shot.nama, frame=shot.frame_mulai)
        marker.camera = cam

    scene.camera = bpy.data.objects[f"{SHOTS[0].nama}_Kamera"]
