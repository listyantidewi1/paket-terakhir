"""HP di dudukan setang motor, layar menyala, aplikasi kurir generik.

Tidak ada logo atau merek: tampilan dibuat dari objek teks dan bentuk
sederhana. Isi layar berganti per shot (visibilitas render diberi keyframe):
    shot 2   : panah besar ke kanan, "Belok kanan", "20 m"
    shot 4-5 : "1 paket tersisa", "Gang Melati, pagar hijau", jam 21.47

Susunan objek (semua ikut Motor_Kemudi, jadi ikut berbelok):
    HP_Dudukan   penjepit dan tangkai ke setang
    HP           badan HP
    HP_Layar     empty di tengah layar: X kanan, Y atas layar, Z keluar layar.
                 Semua isi layar dan tetes air adalah anak objek ini.
"""

import math
import random

import bpy
from mathutils import Euler, Vector

from . import bahan
from .geo import Gabung
from .motor import KEPALA

SEED = 4021
LEBAR, TINGGI, TEBAL = 0.074, 0.158, 0.009  # ukuran HP (meter)
LAYAR_L, LAYAR_T = 0.068, 0.148
# Posisi dan kemiringan HP dalam koordinat motor: di setang sebelah kanan
# tengah, layar condong ke belakang menghadap pengendara.
POSISI = Vector((0.1, 0.44, 1.075))
MIRING = 35  # derajat dari tegak, layar menghadap ke atas-belakang
JAM_S2 = "21.44"
JAM_S45 = "21.47"


def _bahan():
    if "hp_badan" in bpy.data.materials:
        return
    bahan.polos("hp_badan", (0.02, 0.02, 0.022), kasar=0.35, logam=0.4)
    bahan.polos("hp_dudukan", (0.015, 0.015, 0.015), kasar=0.55)
    b = bahan.polos("hp_kaca", (0.0, 0.0, 0.0), kasar=0.03)
    b.node_tree.nodes["Principled BSDF"].inputs["Coat Weight"].default_value = 1.0
    bahan.polos("hp_latar", (0.0, 0.0, 0.0), emisi=(0.03, 0.045, 0.07), kuat=1.0)  # latar gelap aplikasi
    bahan.polos("hp_panel", (0.0, 0.0, 0.0), emisi=(0.07, 0.1, 0.16), kuat=1.0)
    bahan.polos("hp_teks", (0.0, 0.0, 0.0), emisi=(0.92, 0.95, 1.0), kuat=2.2)
    bahan.polos("hp_teks_redup", (0.0, 0.0, 0.0), emisi=(0.55, 0.62, 0.72), kuat=1.6)
    bahan.polos("hp_aksen", (0.0, 0.0, 0.0), emisi=(0.15, 0.95, 0.5), kuat=2.5)  # hijau navigasi
    bahan.polos("hp_oren", (0.0, 0.0, 0.0), emisi=(1.0, 0.5, 0.08), kuat=2.2)
    if "air_tetes" not in bpy.data.materials:
        a = bahan.polos("air_tetes", (0.9, 0.92, 0.95), kasar=0.05)
        bsdf = a.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Transmission Weight"].default_value = 1.0
        bsdf.inputs["IOR"].default_value = 1.33


def _mesh(nama, g, bahan_nama, induk, kol, tumpul=0.0):
    mesh = bpy.data.meshes.new(nama)
    mesh.from_pydata([tuple(v) for v in g.v], [], g.f)
    mesh.validate()
    mesh.materials.append(bpy.data.materials[bahan_nama])
    obj = bpy.data.objects.new(nama, mesh)
    kol.objects.link(obj)
    obj.parent = induk
    if tumpul:
        mod = obj.modifiers.new("Tumpul", "BEVEL")
        mod.width = tumpul
        mod.segments = 3
        mod.limit_method = "ANGLE"
    return obj


def _teks(nama, isi, induk, kol, x, y, ukuran, bahan_nama, rata="LEFT", tebal=False):
    kurva = bpy.data.curves.new(nama, type="FONT")
    kurva.body = isi
    kurva.align_x = rata
    kurva.align_y = "CENTER"
    kurva.size = ukuran
    if tebal:
        kurva.offset = ukuran * 0.025  # sedikit menebal
    kurva.materials.append(bpy.data.materials[bahan_nama])
    obj = bpy.data.objects.new(nama, kurva)
    kol.objects.link(obj)
    obj.parent = induk
    obj.location = (x, y, 0.0006)
    return obj


def _persegi(g, x0, y0, x1, y1, z=0.0003):
    g.poly([(x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)], [(0, 1, 2, 3)])


def _panah_kanan(g, cx, cy, panjang, tebal, kepala, z=0.0005):
    """Panah datar ke kanan (+X layar), titik tengah (cx, cy)."""
    x0, x1 = cx - panjang / 2, cx + panjang / 2
    xk = x1 - kepala
    g.poly([(x0, cy - tebal / 2, z), (xk, cy - tebal / 2, z), (xk, cy - kepala * 0.75, z), (x1, cy, z),
            (xk, cy + kepala * 0.75, z), (xk, cy + tebal / 2, z), (x0, cy + tebal / 2, z)],
           [(0, 1, 5, 6), (2, 3, 4)])


def _tetes_air(layar, kol, rng, n=55):
    """Tetes hujan yang menempel di kaca: setengah bola pipih, beberapa memanjang ke bawah."""
    g = Gabung()
    for _ in range(n):
        r = rng.uniform(0.0012, 0.0042)
        x = rng.uniform(-LAYAR_L / 2 + r, LAYAR_L / 2 - r)
        y = rng.uniform(-LAYAR_T / 2 + r, LAYAR_T / 2 - r)
        panjang = r * (1.0 + (rng.random() < 0.25) * rng.uniform(0.8, 2.5))  # sebagian mengalir turun
        tinggi = r * rng.uniform(0.35, 0.55)
        cincin, sisi = 4, 12
        o = len(g.v)
        for j in range(cincin + 1):
            t = (math.pi / 2) * j / cincin
            for i in range(sisi):
                s = 2 * math.pi * i / sisi
                sx, sy = math.cos(s) * math.cos(t), math.sin(s) * math.cos(t)
                g.v.append((x + r * sx, y + sy * (panjang if sy < 0 else r), 0.0015 + tinggi * math.sin(t)))
                g.tepi.append(0.0)
        for j in range(cincin):
            for i in range(sisi):
                a, b = o + j * sisi + i, o + j * sisi + (i + 1) % sisi
                g.f.append((a, b, b + sisi, a + sisi))
        g.f.append(tuple(range(o + cincin * sisi, o + (cincin + 1) * sisi)))
    obj = _mesh("HP_Tetes", g, "air_tetes", layar, kol)
    obj.data.shade_smooth()
    return obj


def _tampil(obj, rentang):
    """Objek hanya tampil di render pada rentang frame yang diberikan."""
    awal = min(a for a, _ in rentang)
    obj.hide_render = True
    obj.keyframe_insert("hide_render", frame=awal - 1)
    for a, b in rentang:
        obj.hide_render = False
        obj.keyframe_insert("hide_render", frame=a)
        obj.hide_render = True
        obj.keyframe_insert("hide_render", frame=b + 1)


def buat_hp(kol, motor, rentang_s2, rentang_s45):
    """Pasang HP di kemudi motor. rentang_*: daftar (frame_awal, frame_akhir)."""
    _bahan()
    rng = random.Random(SEED)
    kemudi = bpy.data.objects["Motor_Kemudi"]
    # Rx(90 - MIRING): +Z lokal (muka layar) menghadap ke belakang-atas (ke pengendara),
    # +Y lokal (atas layar) condong ke depan-atas
    rot = Euler((math.radians(90 - MIRING), 0, 0)).to_matrix()

    # Dudukan: penjepit setang, tangkai, dan cakar penjepit HP
    g = Gabung()
    g.tabung(Vector((POSISI.x - 0.02, 0.4, 0.99)), Vector((POSISI.x + 0.02, 0.4, 0.99)), 0.02, n=14)
    g.tabung(Vector((POSISI.x, 0.41, 1.0)), POSISI + rot @ Vector((0, 0, -0.012)), 0.007, n=10)
    for sx in (-1, 1):
        for sy in (-0.045, 0.045):
            a = POSISI + rot @ Vector((sx * (LEBAR / 2 + 0.003), sy, -TEBAL / 2 - 0.002))
            b = POSISI + rot @ Vector((sx * (LEBAR / 2 + 0.003), sy, TEBAL / 2 + 0.002))
            g.kotak(a - Vector((0.004, 0.004, 0.004)), b + Vector((0.004, 0.004, 0.0)))
    g.v = [v - KEPALA for v in map(Vector, g.v)]
    _mesh("HP_Dudukan", g, "hp_dudukan", kemudi, kol, tumpul=0.002)

    # Badan HP: kotak bertepi bulat; sumbu lokal objek = sumbu layar
    hp = bpy.data.objects.new("HP", None)
    kol.objects.link(hp)
    hp.parent = kemudi
    hp.location = POSISI - KEPALA
    hp.rotation_euler = rot.to_euler()
    g = Gabung()
    g.kotak((-LEBAR / 2, -TINGGI / 2, -TEBAL / 2), (LEBAR / 2, TINGGI / 2, TEBAL / 2 - 0.0005))
    _mesh("HP_Badan", g, "hp_badan", hp, kol, tumpul=0.004)
    g = Gabung()
    _persegi(g, -LEBAR / 2 + 0.0012, -TINGGI / 2 + 0.0012, LEBAR / 2 - 0.0012, TINGGI / 2 - 0.0012, z=TEBAL / 2)
    _mesh("HP_Kaca", g, "hp_kaca", hp, kol)

    layar = bpy.data.objects.new("HP_Layar", None)
    layar.empty_display_size = 0.03
    kol.objects.link(layar)
    layar.parent = hp
    layar.location = (0, 0, TEBAL / 2 + 0.0002)
    g = Gabung()
    _persegi(g, -LAYAR_L / 2, -LAYAR_T / 2, LAYAR_L / 2, LAYAR_T / 2, z=0.0)
    _mesh("HP_Layar_Latar", g, "hp_latar", layar, kol)

    # --- Isi shot 2: navigasi belok kanan
    s2 = []
    s2.append(_teks("HP_S2_Jam", JAM_S2, layar, kol, -0.03, 0.068, 0.0042, "hp_teks_redup"))
    g = Gabung()
    _persegi(g, -0.032, 0.006, 0.032, 0.06)
    s2.append(_mesh("HP_S2_Panel", g, "hp_panel", layar, kol))
    g = Gabung()
    _panah_kanan(g, 0.0, 0.034, 0.05, 0.011, 0.02)
    s2.append(_mesh("HP_S2_Panah", g, "hp_aksen", layar, kol))
    s2.append(_teks("HP_S2_Jarak", "20 m", layar, kol, 0.0, -0.01, 0.014, "hp_teks", rata="CENTER", tebal=True))
    s2.append(_teks("HP_S2_Belok", "Belok kanan", layar, kol, 0.0, -0.03, 0.0088, "hp_teks", rata="CENTER"))
    g = Gabung()  # garis rute sederhana di bawah
    _persegi(g, -0.003, -0.068, 0.003, -0.045)
    _persegi(g, -0.003, -0.048, 0.022, -0.042)
    s2.append(_mesh("HP_S2_Rute", g, "hp_aksen", layar, kol))
    for o in s2:
        _tampil(o, rentang_s2)

    # --- Isi shot 4-5: paket terakhir
    s45 = []
    s45.append(_teks("HP_S45_Jam", JAM_S45, layar, kol, -0.03, 0.068, 0.0042, "hp_teks_redup"))
    g = Gabung()  # ikon paket: kotak oren dengan pita
    _persegi(g, -0.012, 0.022, 0.012, 0.046)
    s45.append(_mesh("HP_S45_Ikon", g, "hp_oren", layar, kol))
    g = Gabung()
    _persegi(g, -0.0015, 0.022, 0.0015, 0.046, z=0.0005)
    _persegi(g, -0.012, 0.0325, 0.012, 0.0355, z=0.0005)
    s45.append(_mesh("HP_S45_Pita", g, "hp_latar", layar, kol))
    s45.append(_teks("HP_S45_Sisa", "1 paket tersisa", layar, kol, 0.0, 0.006, 0.0068, "hp_teks", rata="CENTER",
                     tebal=True))
    g = Gabung()
    _persegi(g, -0.032, -0.034, 0.032, -0.008)
    s45.append(_mesh("HP_S45_Panel", g, "hp_panel", layar, kol))
    s45.append(_teks("HP_S45_Alamat1", "Gang Melati,", layar, kol, 0.0, -0.015, 0.0068, "hp_teks", rata="CENTER"))
    s45.append(_teks("HP_S45_Alamat2", "pagar hijau", layar, kol, 0.0, -0.027, 0.0068, "hp_teks", rata="CENTER"))
    for o in s45:
        _tampil(o, rentang_s45)

    _tetes_air(layar, kol, rng)
    return hp
