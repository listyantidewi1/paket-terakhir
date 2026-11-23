"""Mas Adit, kurir Kota Senja: tubuh berarmature, helm, sarung tangan, bot, ponco kain.

Aturan sama dengan motor (dipakai juga di game Kurir Senja):
    satuan meter, titik pusat armature "Kurir" di tanah di antara kedua kaki,
    menghadap +Y, kanan +X. Kiri (.L) ada di -X karena kurir menghadap +Y.

Tulang:
    akar > pinggul > punggung > dada > leher > kepala
    dada > bahu.L/R > lengan_atas > lengan_bawah > tangan
    pinggul > paha.L/R > betis > kaki
Kendali (tidak mengubah bentuk tubuh):
    ik_tangan.L/R, ik_kaki.L/R   sasaran IK (pergelangan tangan / kaki)
    siku.L/R, lutut.L/R          arah tekuk siku dan lutut
    helm                         mengikuti soket_kepala atau soket_tangan.L (tergantung
                                 dari tali di pergelangan kiri; properti "helm_di_tangan"
                                 0..1, bisa diberi keyframe)

Pose ditulis di POSE dalam koordinat armature (meter, derajat). Saat duduk,
armature menjadi anak motor dengan titik pusat yang sama, sehingga koordinat
pose = koordinat motor (pegangan setang, pijakan kaki, jok).

Ponco: mesh yang mengikuti tulang (tanpa simulasi kain). Tepi bawahnya
bergoyang lewat Displace yang kekuatannya mengikuti properti "laju" (m/s,
dihitung oleh hitung_laju). Dulu: simulasi dimulai MULAI_KAIN frame sebelum
shot supaya kain sudah jatuh tenang di frame pertama shot.
"""

import math

import bmesh
import bpy
from mathutils import Euler, Matrix, Vector

from . import bahan

MULAI_KAIN = 72  # frame pra-gulir simulasi ponco (3 detik)


def _tulang():
    t = [
        ("akar", (0, 0, 0), (0, 0, 0.25), None, False),
        ("pinggul", (0, 0, 0.95), (0, 0, 1.05), "akar", True),
        ("punggung", (0, 0, 1.05), (0, 0, 1.27), "pinggul", True),
        ("dada", (0, 0, 1.27), (0, 0, 1.45), "punggung", True),
        ("leher", (0, 0, 1.45), (0, 0.01, 1.56), "dada", True),
        ("kepala", (0, 0.01, 1.56), (0, 0.01, 1.8), "leher", True),
        ("helm", (0, 0.01, 1.56), (0, 0.01, 1.8), "akar", True),
        ("soket_kepala", (0, 0.01, 1.56), (0, 0.01, 1.8), "kepala", False),
    ]
    for sisi, s in (("L", -1), ("R", 1)):
        t += [
            (f"bahu.{sisi}", (s * 0.03, 0, 1.42), (s * 0.18, 0, 1.42), "dada", True),
            (f"lengan_atas.{sisi}", (s * 0.18, 0, 1.42), (s * 0.2, 0, 1.13), f"bahu.{sisi}", True),
            (f"lengan_bawah.{sisi}", (s * 0.2, 0, 1.13), (s * 0.21, 0.03, 0.88), f"lengan_atas.{sisi}", True),
            (f"tangan.{sisi}", (s * 0.21, 0.03, 0.88), (s * 0.21, 0.05, 0.79), f"lengan_bawah.{sisi}", True),
            (f"paha.{sisi}", (s * 0.1, 0, 0.95), (s * 0.1, 0.02, 0.52), "pinggul", True),
            (f"betis.{sisi}", (s * 0.1, 0.02, 0.52), (s * 0.1, 0, 0.1), f"paha.{sisi}", True),
            (f"kaki.{sisi}", (s * 0.1, 0, 0.1), (s * 0.1, 0.16, 0.03), f"betis.{sisi}", True),
            (f"ik_tangan.{sisi}", (s * 0.21, 0.03, 0.88), (s * 0.21, 0.05, 0.79), "akar", False),
            (f"ik_kaki.{sisi}", (s * 0.1, 0, 0.1), (s * 0.1, 0.16, 0.03), "akar", False),
            (f"siku.{sisi}", (s * 0.45, -0.4, 1.13), (s * 0.45, -0.4, 1.23), "akar", False),
            (f"lutut.{sisi}", (s * 0.1, 0.6, 0.52), (s * 0.1, 0.6, 0.62), "akar", False),
        ]
    # Helm yang dipegang: tergantung di samping tangan kanan
    t.append(("soket_tangan.R", (0.27, 0.06, 0.66), (0.27, 0.06, 0.9), "tangan.R", False))
    # Helm tergantung dari talinya di pergelangan kiri (tangan kiri tetap bisa memegang paket)
    t.append(("soket_tangan.L", (-0.25, 0.06, 0.48), (-0.25, 0.06, 0.72), "tangan.L", False))
    return t


TIANG_IK = {"lengan": -90.0, "kaki": 90.0}  # pole angle; diperiksa di uji pose (lutut ke depan)


# Pose: pinggul = posisi kepala tulang pinggul; rot = derajat dunia armature.
# Tanda rotasi X: negatif = membungkuk ke depan, positif = mendongak ke belakang.
# fk = rotasi lokal tulang (derajat XYZ). ik = posisi sasaran; ik_rot = rotasi
# sasaran (derajat, dunia armature) relatif terhadap posisi istirahatnya.
_DUDUK = {
    "pinggul": (0, -0.15, 0.97), "pinggul_rot": (-14, 0, 0),
    "fk": {"punggung": (-8, 0, 0), "dada": (-4, 0, 0), "leher": (10, 0, 0), "kepala": (10, 0, 0)},
    "ik": {"ik_tangan.L": (-0.27, 0.33, 1.0), "ik_tangan.R": (0.27, 0.33, 1.0),
           "ik_kaki.L": (-0.21, 0.05, 0.37), "ik_kaki.R": (0.21, 0.05, 0.37),
           "siku.L": (-0.6, -0.1, 0.9), "siku.R": (0.6, -0.1, 0.9),
           "lutut.L": (-0.4, 0.9, 0.8), "lutut.R": (0.4, 0.9, 0.8)},
    "ik_rot": {"ik_tangan.L": (80, 0, 0), "ik_tangan.R": (80, 0, 0)},
}
POSE = {
    # Duduk dengan tangan tergantung di samping (di dalam ponco): awal pra-gulir
    # simulasi, supaya kain membungkus lengan saat tangan bergerak ke setang
    "duduk_tangan_turun": {**_DUDUK, "ik": {**_DUDUK["ik"], "ik_tangan.L": (-0.27, -0.06, 0.93),
                                            "ik_tangan.R": (0.27, -0.06, 0.93)},
                           "ik_rot": {}},
    "berdiri": {
        "pinggul": (0, 0, 0.94),
        "ik": {"ik_tangan.L": (-0.21, 0.03, 0.87), "ik_tangan.R": (0.21, 0.03, 0.87),
               "ik_kaki.L": (-0.1, 0, 0.1), "ik_kaki.R": (0.1, 0, 0.1)},
    },
    "duduk_motor": _DUDUK,
    # Menoleh ke belakang lewat bahu kanan (shot 3: melihat kucing di boks)
    "menoleh": {**_DUDUK, "fk": {**_DUDUK["fk"], "dada": (-4, -12, 0), "leher": (2, -48, 0),
                                 "kepala": (-4, -48, 0)}},
    # Turun dari motor: kaki kiri di tanah, kaki kanan diayun melewati jok
    "turun": {
        "pinggul": (-0.24, 0.02, 0.98), "pinggul_rot": (-10, 0, 10),
        "fk": {"punggung": (-6, 0, 0)},
        "ik": {"ik_tangan.L": (-0.27, 0.33, 1.0), "ik_tangan.R": (0.02, -0.18, 0.95),
               "ik_kaki.L": (-0.36, 0.06, 0.1), "ik_kaki.R": (0.0, -0.3, 0.98),
               "lutut.R": (0.4, -0.3, 1.5), "lutut.L": (-0.6, 0.6, 0.5)},
        "ik_rot": {"ik_tangan.L": (80, 0, 0), "ik_tangan.R": (180, 0, 0), "ik_kaki.R": (0, 0, 40)},
    },
    # Dua pose kontak langkah; berselang-seling untuk berjalan
    "jalan_kiri": {
        "pinggul": (0, 0, 0.9), "pinggul_rot": (0, 0, -5), "fk": {"dada": (0, 0, 8)},
        "ik": {"ik_kaki.L": (-0.1, 0.32, 0.1), "ik_kaki.R": (0.1, -0.3, 0.15),
               "ik_tangan.L": (-0.22, -0.16, 0.9), "ik_tangan.R": (0.22, 0.2, 0.9)},
        "ik_rot": {"ik_kaki.L": (15, 0, 0), "ik_kaki.R": (-30, 0, 0)},
    },
    "jalan_kanan": {
        "pinggul": (0, 0, 0.9), "pinggul_rot": (0, 0, 5), "fk": {"dada": (0, 0, -8)},
        "ik": {"ik_kaki.R": (0.1, 0.32, 0.1), "ik_kaki.L": (-0.1, -0.3, 0.15),
               "ik_tangan.R": (0.22, -0.16, 0.9), "ik_tangan.L": (-0.22, 0.2, 0.9)},
        "ik_rot": {"ik_kaki.R": (15, 0, 0), "ik_kaki.L": (-30, 0, 0)},
    },
    # Mengangkat paket dengan dua tangan di depan dada
    "angkat_dua_tangan": {
        "pinggul": (0, -0.02, 0.94), "fk": {"punggung": (4, 0, 0)},
        "ik": {"ik_tangan.L": (-0.16, 0.33, 1.08), "ik_tangan.R": (0.16, 0.33, 1.08),
               "ik_kaki.L": (-0.11, 0, 0.1), "ik_kaki.R": (0.11, 0, 0.1),
               "siku.L": (-0.6, -0.2, 0.9), "siku.R": (0.6, -0.2, 0.9)},
        "ik_rot": {"ik_tangan.L": (90, 0, -60), "ik_tangan.R": (90, 0, 60)},
    },
    # Melepas helm: tangan memegang sisi helm, lalu helm diangkat ke tangan
    "lepas_helm": {
        "pinggul": (0, 0, 0.94),
        "ik": {"ik_tangan.L": (-0.15, 0.03, 1.66), "ik_tangan.R": (0.15, 0.03, 1.66),
               "ik_kaki.L": (-0.1, 0, 0.1), "ik_kaki.R": (0.1, 0, 0.1),
               "siku.L": (-0.7, 0.1, 1.4), "siku.R": (0.7, 0.1, 1.4)},
        "ik_rot": {"ik_tangan.L": (180, 0, 0), "ik_tangan.R": (180, 0, 0)},
    },
    "helm_di_tangan": {
        "pinggul": (0, 0, 0.94), "helm": 1.0,
        "ik": {"ik_tangan.L": (-0.21, 0.03, 0.87), "ik_tangan.R": (0.2, 0.1, 0.9),
               "ik_kaki.L": (-0.1, 0, 0.1), "ik_kaki.R": (0.1, 0, 0.1)},
    },
    # Mengambil kucing dari atas boks (boks di depan kurir, setinggi dada)
    "ambil_kucing": {
        "pinggul": (0, 0, 0.94), "fk": {"punggung": (-8, 0, 0), "kepala": (-10, 0, 0)},
        "ik": {"ik_tangan.L": (-0.1, 0.42, 1.53), "ik_tangan.R": (0.1, 0.42, 1.53),
               "ik_kaki.L": (-0.11, 0, 0.1), "ik_kaki.R": (0.11, 0, 0.1),
               "siku.L": (-0.6, -0.1, 1.2), "siku.R": (0.6, -0.1, 1.2)},
        "ik_rot": {"ik_tangan.L": (90, 0, -80), "ik_tangan.R": (90, 0, 80)},
    },
    # Menggendong kucing di depan dada dengan dua tangan
    "bawa_kucing": {
        "pinggul": (0, 0, 0.94), "fk": {"punggung": (3, 0, 0)},
        "ik": {"ik_tangan.L": (-0.11, 0.3, 1.18), "ik_tangan.R": (0.11, 0.3, 1.18),
               "ik_kaki.L": (-0.11, 0, 0.1), "ik_kaki.R": (0.11, 0, 0.1),
               "siku.L": (-0.6, -0.2, 1.0), "siku.R": (0.6, -0.2, 1.0)},
        "ik_rot": {"ik_tangan.L": (90, 0, -80), "ik_tangan.R": (90, 0, 80)},
    },
    # Menaruh kucing di bangku: membungkuk, tangan rendah di depan
    "taruh_kucing": {
        "pinggul": (0, -0.08, 0.84), "pinggul_rot": (-28, 0, 0), "fk": {"punggung": (-10, 0, 0)},
        "ik": {"ik_tangan.L": (-0.11, 0.45, 0.83), "ik_tangan.R": (0.11, 0.45, 0.83),
               "ik_kaki.L": (-0.13, 0.05, 0.1), "ik_kaki.R": (0.13, 0.05, 0.1),
               "lutut.L": (-0.2, 0.9, 0.6), "lutut.R": (0.2, 0.9, 0.6),
               "siku.L": (-0.6, -0.1, 0.9), "siku.R": (0.6, -0.1, 0.9)},
        "ik_rot": {"ik_tangan.L": (90, 0, -80), "ik_tangan.R": (90, 0, 80)},
    },
    # Mengetuk pintu dengan tangan kanan; tangan kiri memegang paket di pinggang
    "ketuk_pintu": {
        "pinggul": (0, 0, 0.94),
        "ik": {"ik_tangan.R": (0.14, 0.42, 1.42), "ik_tangan.L": (-0.18, 0.22, 1.0),
               "ik_kaki.L": (-0.1, 0, 0.1), "ik_kaki.R": (0.1, 0, 0.1),
               "siku.R": (0.6, -0.1, 1.1)},
        "ik_rot": {"ik_tangan.R": (90, 0, 0), "ik_tangan.L": (70, 0, -40)},
    },
}


# --------------------------------------------------------------------------
# Bahan


def _bahan():
    if "kurir_baju" in bpy.data.materials:
        return
    bahan.polos("kurir_baju", (0.03, 0.035, 0.04), kasar=0.6)
    bahan.polos("kurir_celana", (0.025, 0.04, 0.075), kasar=0.7)
    bahan.polos("kurir_bot", (0.012, 0.012, 0.012), kasar=0.22)  # karet basah
    bahan.polos("kurir_sarung_tangan", (0.02, 0.02, 0.022), kasar=0.45)
    bahan.polos("kurir_kulit", (0.42, 0.26, 0.17), kasar=0.5)
    bahan.polos("kurir_rambut", (0.012, 0.01, 0.009), kasar=0.25)  # rambut basah
    b = bahan.polos("helm_putih", (0.85, 0.85, 0.83), kasar=0.2)
    b.node_tree.nodes["Principled BSDF"].inputs["Coat Weight"].default_value = 1.0
    # Kaca helm gelap: hampir hitam, sangat licin, memantulkan lampu kota
    bahan.polos("helm_kaca", (0.004, 0.004, 0.006), kasar=0.02, logam=0.5)
    bahan.polos("helm_karet", (0.015, 0.015, 0.015), kasar=0.5)
    _bahan_ponco()


def _bahan_ponco():
    """Plastik PVC kuning yang basah: lapisan coat licin, butir air, aliran air."""
    b = bahan.polos("ponco_kuning", (0.95, 0.6, 0.02), kasar=0.25)
    nt = b.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Coat Weight"].default_value = 1.0
    bsdf.inputs["Coat Roughness"].default_value = 0.03
    koor = nt.nodes.new("ShaderNodeTexCoord")
    butir = nt.nodes.new("ShaderNodeTexVoronoi")
    butir.feature = "SMOOTH_F1"
    butir.inputs["Scale"].default_value = 90.0
    nt.links.new(koor.outputs["Object"], butir.inputs["Vector"])
    rentang = nt.nodes.new("ShaderNodeMapRange")
    rentang.inputs["From Min"].default_value = 0.0
    rentang.inputs["From Max"].default_value = 0.35
    rentang.inputs["To Min"].default_value = 1.0
    rentang.inputs["To Max"].default_value = 0.0
    nt.links.new(butir.outputs["Distance"], rentang.inputs["Value"])
    aliran = nt.nodes.new("ShaderNodeTexNoise")
    peta = nt.nodes.new("ShaderNodeMapping")
    peta.inputs["Scale"].default_value = (30.0, 30.0, 3.0)  # memanjang ke bawah
    nt.links.new(koor.outputs["Object"], peta.inputs["Vector"])
    nt.links.new(peta.outputs["Vector"], aliran.inputs["Vector"])
    tambah = nt.nodes.new("ShaderNodeMath")
    tambah.operation = "ADD"
    nt.links.new(rentang.outputs["Result"], tambah.inputs[0])
    kali = nt.nodes.new("ShaderNodeMath")
    kali.operation = "MULTIPLY"
    kali.inputs[1].default_value = 0.3
    nt.links.new(aliran.outputs["Fac"], kali.inputs[0])
    nt.links.new(kali.outputs[0], tambah.inputs[1])
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.inputs["Distance"].default_value = 0.002
    nt.links.new(tambah.outputs[0], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Coat Normal"])


# --------------------------------------------------------------------------
# Mesh


class _Mesh:
    """Titik, muka, bahan per muka, dan grup titik (satu tulang per titik)."""

    def __init__(self, bahan_list):
        self.v, self.f, self.mat, self.grup = [], [], [], []
        self.bahan = bahan_list

    def lonjong(self, a, b, rx, ry, tulang, nama_bahan, lebih=0.03, n=14, m=9, potong=None):
        """Lonjong (elipsoid) sepanjang ruas a-b. potong: (z_min_lokal 0..1) untuk topi rambut."""
        a, b = Vector(a), Vector(b)
        sumbu = b - a
        panjang = sumbu.length / 2 + lebih
        d = sumbu.normalized()
        pusat = (a + b) / 2
        ux = Vector((1, 0, 0)) - d * d.x
        ux = ux.normalized() if ux.length > 1e-4 else Vector((0, 1, 0))
        uy = d.cross(ux).normalized()
        o = len(self.v)
        cincin = []
        for j in range(1, m):
            t = math.pi * j / m
            if potong is not None and math.cos(t) < potong:
                break
            cincin.append(t)
        for t in cincin:
            for i in range(n):
                s = 2 * math.pi * i / n
                self.v.append(pusat + d * (panjang * math.cos(t)) + ux * (rx * math.sin(t) * math.cos(s))
                              + uy * (ry * math.sin(t) * math.sin(s)))
                self.grup.append(tulang)
        kutub = len(self.v)
        self.v.append(pusat + d * panjang)
        self.grup.append(tulang)
        k = self.bahan.index(nama_bahan)
        for i in range(n):
            self.f.append((kutub, o + (i + 1) % n, o + i))
            self.mat.append(k)
        for j in range(len(cincin) - 1):
            for i in range(n):
                p, q = o + j * n, o + (j + 1) * n
                self.f.append((p + i, p + (i + 1) % n, q + (i + 1) % n, q + i))
                self.mat.append(k)
        if potong is None:
            bawah = len(self.v)
            self.v.append(pusat - d * panjang)
            self.grup.append(tulang)
            p = o + (len(cincin) - 1) * n
            for i in range(n):
                self.f.append((bawah, p + i, p + (i + 1) % n))
                self.mat.append(k)

    def objek(self, nama, kol, arm):
        mesh = bpy.data.meshes.new(nama)
        mesh.from_pydata([tuple(p) for p in self.v], [], self.f)
        for nb in self.bahan:
            mesh.materials.append(bpy.data.materials[nb])
        for poly, k in zip(mesh.polygons, self.mat):
            poly.material_index = k
        mesh.validate()
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(mesh)
        bm.free()
        mesh.shade_smooth()
        obj = bpy.data.objects.new(nama, mesh)
        kol.objects.link(obj)
        for t in sorted(set(self.grup)):
            vg = obj.vertex_groups.new(name=t)
            vg.add([i for i, g in enumerate(self.grup) if g == t], 1.0, "REPLACE")
        _ke_armature(obj, arm)
        return obj


def _ke_armature(obj, arm):
    obj.parent = arm
    mod = obj.modifiers.new("Armature", "ARMATURE")
    mod.object = arm


def _tubuh(kol, arm):
    m = _Mesh(["kurir_baju", "kurir_celana", "kurir_bot", "kurir_sarung_tangan", "kurir_kulit", "kurir_rambut"])
    m.lonjong((0, 0, 0.88), (0, 0, 1.04), 0.17, 0.12, "pinggul", "kurir_celana")
    m.lonjong((0, 0, 1.04), (0, 0, 1.27), 0.155, 0.105, "punggung", "kurir_baju")
    m.lonjong((0, 0, 1.25), (0, 0, 1.44), 0.19, 0.12, "dada", "kurir_baju")
    m.lonjong((0, 0, 1.43), (0, 0.01, 1.57), 0.055, 0.055, "leher", "kurir_baju", lebih=0.02)
    m.lonjong((0, 0.012, 1.56), (0, 0.012, 1.79), 0.085, 0.1, "kepala", "kurir_kulit", lebih=0.0)
    m.lonjong((0, 0.0, 1.58), (0, 0.0, 1.8), 0.09, 0.105, "kepala", "kurir_rambut", lebih=0.005, potong=-0.15)
    for x in (-1, 1):  # telinga (terlihat dari belakang saat helm dilepas)
        m.lonjong((x * 0.086, -0.005, 1.65), (x * 0.092, -0.01, 1.7), 0.012, 0.022, "kepala", "kurir_kulit",
                  lebih=0.004, n=10, m=6)
    for s, x in (("L", -1), ("R", 1)):
        m.lonjong((x * 0.04, 0, 1.42), (x * 0.18, 0, 1.42), 0.06, 0.06, f"bahu.{s}", "kurir_baju", lebih=0.04)
        m.lonjong((x * 0.18, 0, 1.42), (x * 0.2, 0, 1.13), 0.055, 0.055, f"lengan_atas.{s}", "kurir_baju")
        m.lonjong((x * 0.2, 0, 1.13), (x * 0.21, 0.03, 0.88), 0.045, 0.045, f"lengan_bawah.{s}", "kurir_baju")
        m.lonjong((x * 0.21, 0.03, 0.9), (x * 0.21, 0.05, 0.79), 0.032, 0.05, f"tangan.{s}",
                  "kurir_sarung_tangan", lebih=0.0)
        m.lonjong((x * 0.1, 0, 0.95), (x * 0.1, 0.02, 0.52), 0.08, 0.08, f"paha.{s}", "kurir_celana")
        m.lonjong((x * 0.1, 0.02, 0.52), (x * 0.1, 0.01, 0.3), 0.06, 0.06, f"betis.{s}", "kurir_celana")
        m.lonjong((x * 0.1, 0.01, 0.36), (x * 0.1, 0, 0.08), 0.066, 0.066, f"betis.{s}", "kurir_bot", lebih=0.0)
        m.lonjong((x * 0.1, -0.05, 0.065), (x * 0.1, 0.18, 0.05), 0.055, 0.05, f"kaki.{s}", "kurir_bot", lebih=0.0)
    tubuh = m.objek("Kurir_Tubuh", kol, arm)
    sub = tubuh.modifiers.new("Halus", "SUBSURF")
    sub.levels = sub.render_levels = 1
    return tubuh


def _helm(kol, arm):
    """Helm full face yang terbaca sebagai helm dari segala arah.

    Cangkang putih; kaca gelap menonjol yang melingkar sampai ke samping
    (dengan bingkai hitam); pelindung dagu yang menonjol; engsel kaca di kedua
    sisi; spoiler, ventilasi, dan strip pemantul di belakang; lis karet di bibir
    bawah. Semua lembaran diberi ketebalan dengan Solidify.
    """
    m = _Mesh(["helm_putih", "helm_kaca", "helm_karet", "strip_pemantul"])
    pusat = Vector((0, 0.025, 1.69))
    rx, ry, rz = 0.145, 0.165, 0.155

    def titik(el, az, skala):
        el, az = math.radians(el), math.radians(az)
        return pusat + Vector((rx * skala * math.cos(el) * math.sin(az), ry * skala * math.cos(el) * math.cos(az),
                               rz * skala * math.sin(el)))

    def lembar(el0, el1, az0, az1, skala, bahan_i, nel=6, naz=24, tutup=False):
        """Lembaran pada permukaan elipsoid (el = elevasi, az = azimut dari depan)."""
        o = len(m.v)
        for j in range(nel + 1):
            for i in range(naz + (0 if tutup else 1)):
                az = az0 + (az1 - az0) * i / naz
                m.v.append(titik(el0 + (el1 - el0) * j / nel, az, skala))
                m.grup.append("helm")
        lebar = naz if tutup else naz + 1
        for j in range(nel):
            for i in range(naz):
                a, b = o + j * lebar + i, o + j * lebar + (i + 1) % lebar
                m.f.append((a, b, b + lebar, a + lebar))
                m.mat.append(bahan_i)

    lembar(-70, 90, 0, 360, 1.0, 0, nel=18, naz=32, tutup=True)  # cangkang
    lembar(-70, -60, 0, 360, 1.012, 2, nel=1, naz=32, tutup=True)  # lis karet bibir bawah
    lembar(-17, 27, -82, 82, 1.035, 1, nel=6, naz=26)  # kaca gelap melingkar
    for e0, e1 in ((27, 30.5), (-20.5, -17)):  # bingkai kaca atas dan bawah
        lembar(e0, e1, -84, 84, 1.04, 2, nel=1, naz=26)
    lembar(-58, -20, -52, 52, 1.045, 0, nel=5, naz=16)  # pelindung dagu menonjol
    lembar(-52, -40, -18, 18, 1.06, 2, nel=1, naz=6)  # ventilasi dagu
    lembar(12, 34, 150, 210, 1.07, 0, nel=3, naz=10)  # spoiler belakang
    lembar(36, 48, 160, 200, 1.025, 2, nel=1, naz=6)  # ventilasi atas belakang
    lembar(-12, -4, 140, 220, 1.012, 3, nel=1, naz=12)  # strip pemantul belakang
    for s in (-1, 1):  # engsel kaca di kedua sisi
        m.lonjong(titik(5, s * 84, 1.0), titik(5, s * 84, 1.08), 0.022, 0.022, "helm", "helm_karet",
                  lebih=0.0, n=12, m=5)
    helm = m.objek("Kurir_Helm", kol, arm)
    sub = helm.modifiers.new("Halus", "SUBSURF")
    sub.levels = sub.render_levels = 1
    sol = helm.modifiers.new("Tebal", "SOLIDIFY")
    sol.thickness = 0.008
    return helm


TEPI_BEBAS = 0.15  # hanya 15 cm terbawah ponco yang disimulasikan sebagai kain


def _ponco(kol, arm, nama="Kurir_Ponco"):
    """Ponco sebagai mesh yang mengikuti tulang; hanya tepi bawahnya kain.

    Bentuk: jubah dari kerah sampai lutut, menutupi bahu dan lengan atas
    (lengan tetap di dalam), sedikit lebih panjang di depan. Bobot halus
    (invers jarak ke 4 tulang terdekat), dengan "tudung bahu" yang dibobot ke
    lengan atas; dual quaternion mencegah bahu kolaps saat lengan terangkat.

    Pin (vertex group "pin"): bernilai 1 (terkunci penuh ke badan) di semua
    bagian kecuali TEPI_BEBAS terbawah, yang turun halus dari 1 ke 0. Jadi
    hanya ujung ponco yang bergoyang (angin laju, langkah); sisanya tidak
    bisa menggembung atau lepas dari badan.
    """
    # (z, setengah lebar X, setengah tebal Y). Bahu: puncak bahu z 1,48, lengan
    # menggantung di x 0,18-0,26, jadi ponco di x 0,31-0,34 menutupi lengan atas.
    atas = [(1.56, 0.07, 0.065), (1.53, 0.1, 0.09), (1.5, 0.2, 0.13), (1.47, 0.27, 0.17),
            (1.43, 0.31, 0.19), (1.37, 0.33, 0.2)]
    n = 56
    baris = 24
    titik, z_ujung = [], []
    for j, (z, rx, ry) in enumerate(atas):
        for i in range(n):
            s = 2 * math.pi * i / n  # s = 0 di depan (+Y)
            titik.append(Vector((rx * math.sin(s), ry * math.cos(s) + 0.01, z)))
            z_ujung.append(None)
    # Bahu membulat: di baris bahu, sisi kiri-kanan menggembung mengikuti bahu
    for j in range(2, len(atas)):
        for i in range(n):
            s = 2 * math.pi * i / n
            p = titik[j * n + i]
            p.x *= 1 + 0.07 * math.sin(s) ** 2
            p.z += 0.012 * math.sin(s) ** 2 * (1 if j < 4 else 0)
    # Lipatan kain yang jatuh ke bawah: tonjolan vertikal, makin dalam ke bawah
    import random as _r
    rl = _r.Random(5150)
    fase = [rl.uniform(0, 6.28) for _ in range(3)]
    for j in range(1, baris + 1):
        t = j / baris
        for i in range(n):
            s = 2 * math.pi * i / n
            ujung = 0.5 - 0.04 * math.cos(s)  # sampai lutut; depan sedikit lebih panjang
            z = 1.37 - (1.37 - ujung) * t
            rx, ry = 0.33 + 0.04 * t, 0.2 + 0.05 * t
            lipat = (0.024 * t ** 0.8) * (0.55 * math.sin(9 * s + fase[0]) + 0.3 * math.sin(14 * s + fase[1])
                                         + 0.15 * math.sin(5 * s + fase[2]))
            arah = Vector((math.sin(s) / rx, math.cos(s) / ry, 0)).normalized()
            titik.append(Vector((rx * math.sin(s), ry * math.cos(s) + 0.01 + 0.03 * t, z)) + arah * lipat)
            z_ujung.append(ujung)
    muka = [(j * n + i, j * n + (i + 1) % n, (j + 1) * n + (i + 1) % n, (j + 1) * n + i)
            for j in range(len(atas) + baris - 1) for i in range(n)]
    # Tudung terlipat di punggung: kantong setengah kubah dengan bibir tergulung di atasnya
    pusat_t, rxt, ryt, rzt = Vector((0, -0.19, 1.37)), 0.15, 0.065, 0.12
    o = len(titik)
    nu, nv = 14, 8
    for jv in range(nv + 1):
        el = -math.pi / 2 + math.pi * jv / nv
        for iu in range(nu + 1):
            az = math.pi * iu / nu  # setengah ke luar (ke belakang, -Y)
            kerut = 1 + 0.06 * math.sin(5 * az + 0.7) * math.cos(el)  # sedikit berkerut
            titik.append(pusat_t + Vector((-rxt * math.cos(el) * math.cos(az),
                                           -ryt * kerut * math.cos(el) * math.sin(az), rzt * math.sin(el))))
            z_ujung.append(None)
    lebar_t = nu + 1
    muka += [(o + jv * lebar_t + iu, o + jv * lebar_t + iu + 1, o + (jv + 1) * lebar_t + iu + 1,
              o + (jv + 1) * lebar_t + iu) for jv in range(nv) for iu in range(nu)]
    o = len(titik)  # bibir tudung yang tergulung: tabung kecil melengkung di tepi atas
    lingkar, ruas = 8, 16
    for k in range(ruas + 1):
        a = math.pi * k / ruas
        c = pusat_t + Vector((-rxt * 1.02 * math.cos(a), -0.012 - 0.02 * math.sin(a), rzt * 0.92 + 0.012 * math.sin(a)))
        for q in range(lingkar):
            b = 2 * math.pi * q / lingkar
            titik.append(c + Vector((0, 0.014 * math.cos(b), 0.014 * math.sin(b))))
            z_ujung.append(None)
    muka += [(o + k * lingkar + q, o + k * lingkar + (q + 1) % lingkar, o + (k + 1) * lingkar + (q + 1) % lingkar,
              o + (k + 1) * lingkar + q) for k in range(ruas) for q in range(lingkar)]
    mesh = bpy.data.meshes.new(nama)
    mesh.from_pydata([tuple(p) for p in titik], [], muka)
    mesh.materials.append(bpy.data.materials["ponco_kuning"])
    mesh.shade_smooth()
    obj = bpy.data.objects.new(nama, mesh)
    kol.objects.link(obj)

    calon = ["leher", "dada", "punggung", "pinggul", "paha.L", "paha.R", "betis.L", "betis.R"]
    ruas = {b.name: (b.head_local, b.tail_local) for b in arm.data.bones if b.name in calon}
    grup = {nama: obj.vertex_groups.new(name=nama) for nama in calon + ["lengan_atas.L", "lengan_atas.R"]}
    pin = obj.vertex_groups.new(name="pin")
    tepi = obj.vertex_groups.new(name="tepi")  # kebalikan pin: bagian yang boleh bergoyang
    for idx, p in enumerate(titik):
        jarak = []
        for nama_t, (a, b) in ruas.items():
            ab = b - a
            t = max(0.0, min(1.0, (p - a).dot(ab) / ab.length_squared))
            jarak.append(((p - (a + ab * t)).length, nama_t))
        jarak.sort()
        bobot = [(1 / max(d, 0.03) ** 2, nama_t) for d, nama_t in jarak[:4]]  # halus: kuadrat, 4 tulang
        total = sum(w for w, _ in bobot)
        bahu = (min(1.0, max(0.0, (abs(p.x) - 0.14) / 0.14)) * min(1.0, max(0.0, (p.z - 1.12) / 0.18)))
        bahu = bahu * bahu * (3 - 2 * bahu)
        for w, nama_t in bobot:
            grup[nama_t].add([idx], (1 - bahu) * w / total, "REPLACE")
        if bahu > 0:
            grup["lengan_atas.L" if p.x < 0 else "lengan_atas.R"].add([idx], bahu, "REPLACE")
        w_pin = 1.0
        if z_ujung[idx] is not None:
            u = min(1.0, max(0.0, (p.z - z_ujung[idx]) / TEPI_BEBAS))
            w_pin = u * u * (3 - 2 * u)
        pin.add([idx], w_pin, "REPLACE")
        if w_pin < 1.0:
            tepi.add([idx], 1.0 - w_pin, "REPLACE")
    _ke_armature(obj, arm)
    obj.modifiers["Armature"].use_deform_preserve_volume = True

    # Tepi bawah bergoyang tanpa simulasi: Displace dengan noise berkoordinat dunia,
    # hanya pada grup "tepi" (15 cm terbawah). Polanya bergulir saat kurir
    # bergerak dan diam saat kurir diam; kekuatannya mengikuti properti "laju".
    tekstur = bpy.data.textures.get("Ponco_Angin") or bpy.data.textures.new("Ponco_Angin", "CLOUDS")
    tekstur.noise_scale = 0.18
    goyang = obj.modifiers.new("Goyang", "DISPLACE")
    goyang.texture = tekstur
    goyang.texture_coords = "GLOBAL"
    goyang.direction = "NORMAL"
    goyang.vertex_group = "tepi"
    goyang.mid_level = 0.5
    fc = goyang.driver_add("strength")
    var = fc.driver.variables.new()
    var.name, var.type = "v", "SINGLE_PROP"
    var.targets[0].id = arm
    var.targets[0].data_path = '["laju"]'
    fc.driver.expression = "0.012 + 0.008 * min(v, 8)"
    sub = obj.modifiers.new("Halus", "SUBSURF")
    sub.levels = sub.render_levels = 1
    sol = obj.modifiers.new("Tebal", "SOLIDIFY")
    sol.thickness = 0.003
    return obj


# --------------------------------------------------------------------------
# Armature


def _armature(kol, nama):
    data = bpy.data.armatures.new(nama)
    arm = bpy.data.objects.new(nama, data)
    kol.objects.link(arm)
    data.display_type = "STICK"
    lapisan = bpy.context.view_layer
    for o in lapisan.objects:
        o.select_set(False)
    lapisan.objects.active = arm
    arm.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    eb = data.edit_bones
    for nm, kepala, ekor, induk, deform in _tulang():
        b = eb.new(nm)
        b.head, b.tail = kepala, ekor
        b.roll = 0.0
        b.use_deform = deform
        if induk:
            b.parent = eb[induk]
            b.use_connect = (Vector(kepala) - eb[induk].tail).length < 1e-6 and nm not in ("helm",)
    bpy.ops.object.mode_set(mode="OBJECT")

    pb = arm.pose.bones
    for p in pb:
        p.rotation_mode = "XYZ"
    for s in ("L", "R"):
        for rantai, ujung, sasaran, tiang, jenis in (("lengan_bawah", "tangan", "ik_tangan", "siku", "lengan"),
                                                       ("betis", "kaki", "ik_kaki", "lutut", "kaki")):
            ik = pb[f"{rantai}.{s}"].constraints.new("IK")
            ik.target = arm
            ik.subtarget = f"{sasaran}.{s}"
            ik.pole_target = arm
            ik.pole_subtarget = f"{tiang}.{s}"
            ik.pole_angle = math.radians(TIANG_IK[jenis])
            ik.chain_count = 2
            rot = pb[f"{ujung}.{s}"].constraints.new("COPY_ROTATION")
            rot.target = arm
            rot.subtarget = f"{sasaran}.{s}"
    # Helm: ikut kepala, atau tangan kanan saat helm_di_tangan = 1
    arm["helm_di_tangan"] = 0.0
    arm["laju"] = 0.0
    ke_kepala = pb["helm"].constraints.new("COPY_TRANSFORMS")
    ke_kepala.target, ke_kepala.subtarget = arm, "soket_kepala"
    ke_tangan = pb["helm"].constraints.new("COPY_TRANSFORMS")
    ke_tangan.target, ke_tangan.subtarget = arm, "soket_tangan.L"
    fc = ke_tangan.driver_add("influence")
    var = fc.driver.variables.new()
    var.name, var.type = "h", "SINGLE_PROP"
    var.targets[0].id = arm
    var.targets[0].data_path = '["helm_di_tangan"]'
    fc.driver.expression = "h"
    return arm


def buat_kurir(kol, nama="Kurir"):
    """Bangun Mas Adit berdiri di titik asal. Kembalikan objek armature."""
    _bahan()
    arm = _armature(kol, nama)
    tubuh = _tubuh(kol, arm)
    _rambut(kol, arm)
    _helm(kol, arm)
    _ponco(kol, arm)
    pasang_tumbukan(tubuh, 0.02, gesek=80.0)
    return arm


def pasang_tumbukan(obj, tebal, gesek=40.0):
    """Collision diletakkan sebelum Subdivision: kain bertumbukan dengan cage
    kasar (bentuk sama, muka kira-kira seperempat), simulasi jauh lebih cepat."""
    if any(m.type == "COLLISION" for m in obj.modifiers):
        return
    obj.modifiers.new("Tumbukan", "COLLISION")
    urutan = [m.type for m in obj.modifiers]
    if "SUBSURF" in urutan:
        obj.modifiers.move(len(urutan) - 1, urutan.index("SUBSURF"))
    obj.collision.thickness_outer = tebal
    obj.collision.cloth_friction = gesek


# --------------------------------------------------------------------------
# Pose


def terapkan_pose(arm, nama, frame=None):
    """Pasang pose dari POSE; jika frame diberikan, simpan sebagai keyframe."""
    p = POSE[nama]
    pb, tl = arm.pose.bones, arm.data.bones
    for b in pb:
        b.location = (0, 0, 0)
        b.rotation_euler = (0, 0, 0)
    bpy.context.view_layer.update()

    def rot(derajat):
        return Euler([math.radians(a) for a in derajat]).to_matrix().to_4x4()

    rest = tl["pinggul"].matrix_local
    pb["pinggul"].matrix = (Matrix.Translation(p["pinggul"]) @ rot(p.get("pinggul_rot", (0, 0, 0)))
                            @ rest.to_3x3().to_4x4())
    bpy.context.view_layer.update()
    for nm, r in p.get("fk", {}).items():
        pb[nm].rotation_euler = [math.radians(a) for a in r]
    istirahat = POSE["berdiri"]["ik"]
    for nm in [b.name for b in tl if b.name.startswith(("ik_", "siku", "lutut"))]:
        pos = p["ik"].get(nm, istirahat.get(nm, tl[nm].head_local))
        r = p.get("ik_rot", {}).get(nm, (0, 0, 0))
        pb[nm].matrix = Matrix.Translation(pos) @ rot(r) @ tl[nm].matrix_local.to_3x3().to_4x4()
    arm["helm_di_tangan"] = p.get("helm", 0.0)
    bpy.context.view_layer.update()
    if frame is not None:
        for b in pb:
            b.keyframe_insert("location", frame=frame)
            b.keyframe_insert("rotation_euler", frame=frame)
        arm.keyframe_insert('["helm_di_tangan"]', frame=frame)


def duduk_di(arm, motor, frame_mulai, frame_selesai):
    """Kurir menjadi anak motor dan duduk; simulasi ponco untuk rentang frame ini."""
    arm.parent = motor
    arm.location = (0, 0, 0)
    arm.rotation_euler = (0, 0, 0)
    terapkan_pose(arm, "duduk_tangan_turun", frame=frame_mulai - MULAI_KAIN)
    terapkan_pose(arm, "duduk_motor", frame=frame_mulai - MULAI_KAIN + 30)
    for o in motor.children_recursive:
        if (o.type == "MESH" and o.name.startswith(("Motor_Jok", "Motor_Bodi", "Motor_Dek", "Motor_Tameng",
                                                     "Motor_Boks", "Motor_Hidung"))
                and "strip_pemantul" not in o.name):
            pasang_tumbukan(o, 0.008)


# Berjalan sambil menggendong: kaki dari pose jalan, tangan dari bawa_kucing
for _sisi in ("kiri", "kanan"):
    _j = POSE[f"jalan_{_sisi}"]
    POSE[f"jalan_bawa_{_sisi}"] = {
        **_j, "fk": {"punggung": (3, 0, 0)},
        "ik": {**{k: v for k, v in _j["ik"].items() if k.startswith("ik_kaki")}, **POSE["bawa_kucing"]["ik"],
               **{k: v for k, v in _j["ik"].items() if k.startswith("ik_kaki")}},
        "ik_rot": {**{k: v for k, v in _j.get("ik_rot", {}).items() if k.startswith("ik_kaki")},
                   **POSE["bawa_kucing"]["ik_rot"]},
    }


def kunci_tempat(arm, frame, lokasi, arah_derajat):
    """Tempat dan arah hadap kurir (koordinat induk, biasanya motor) pada frame."""
    arm.location = lokasi
    arm.rotation_euler = (0, 0, math.radians(arah_derajat))
    arm.keyframe_insert("location", frame=frame)
    arm.keyframe_insert("rotation_euler", index=2, frame=frame)


def tampil_di(obj, frame_awal, frame_akhir):
    """Objek hanya muncul di render dari frame_awal sampai frame_akhir.

    Hanya visibilitas render; di viewport tetap ada supaya simulasinya tetap
    dihitung saat frame dijalankan berurutan.
    """
    for f, sembunyi in ((frame_awal - 1, True), (frame_awal, False), (frame_akhir, False), (frame_akhir + 1, True)):
        obj.hide_render = sembunyi
        obj.keyframe_insert("hide_render", frame=f)


# Pose shot 6-7 di teras: paket di tangan kiri, helm dilepas dengan tangan kanan
# Tangan kiri memegang paket di depan-kiri, keluar dari sisi ponco; helm tergantung
# dari pergelangan kiri. Tangan kanan bebas untuk mengetuk.
_PAKET_KIRI = {"ik_tangan.L": (-0.3, 0.2, 0.98), "siku.L": (-0.7, -0.2, 1.1)}
_PAKET_KIRI_ROT = {"ik_tangan.L": (60, 0, -50)}
POSE["berdiri_paket"] = {
    "pinggul": (0, 0, 0.94),
    "ik": {**_PAKET_KIRI, "ik_tangan.R": (0.21, 0.04, 0.88),
           "ik_kaki.L": (-0.1, 0, 0.1), "ik_kaki.R": (0.1, 0, 0.1)},
    "ik_rot": dict(_PAKET_KIRI_ROT),
}
POSE["pegang_helm"] = {  # tangan kanan memegang sisi helm
    **POSE["berdiri_paket"],
    "ik": {**POSE["berdiri_paket"]["ik"], "ik_tangan.R": (0.15, 0.04, 1.66), "siku.R": (0.7, 0.1, 1.4)},
    "ik_rot": {**_PAKET_KIRI_ROT, "ik_tangan.R": (180, 0, 0)},
}
POSE["angkat_helm"] = {  # helm terangkat lepas dari kepala, sudah di tangan
    **POSE["pegang_helm"], "helm": 1.0,
    "ik": {**POSE["pegang_helm"]["ik"], "ik_tangan.R": (0.2, 0.06, 1.62)},
}
POSE["helm_di_tangan_paket"] = {**POSE["berdiri_paket"], "helm": 1.0,
                                "ik": {**POSE["berdiri_paket"]["ik"], "ik_tangan.R": (0.2, 0.1, 0.92)}}
POSE["ketuk"] = {**POSE["ketuk_pintu"], "helm": 1.0,
                 "ik": {**POSE["ketuk_pintu"]["ik"], **_PAKET_KIRI}, "ik_rot": {**POSE["ketuk_pintu"]["ik_rot"],
                                                                               **_PAKET_KIRI_ROT}}
POSE["ketuk_tarik"] = {**POSE["ketuk"], "ik": {**POSE["ketuk"]["ik"], "ik_tangan.R": (0.14, 0.3, 1.4)}}

# Tangan kiri sedikit menjauh dari badan: helm yang tergantung di pergelangan
# kiri berada di luar sisi ponco dan terlihat dari belakang.
_HELM_KIRI = {"ik_tangan.L": (-0.4, 0.04, 0.96), "siku.L": (-0.8, -0.3, 1.2)}
POSE["teras_paket"] = {**POSE["berdiri_paket"], "helm": 1.0,
                       "ik": {**POSE["berdiri_paket"]["ik"], **_HELM_KIRI}, "ik_rot": {}}
for _n in ("ketuk", "ketuk_tarik"):
    POSE[_n] = {**POSE[_n], "helm": 1.0, "ik": {**POSE[_n]["ik"], **_HELM_KIRI},
                "ik_rot": {k: v for k, v in POSE[_n]["ik_rot"].items() if k != "ik_tangan.L"}}


def _bahan_rambut():
    if "kurir_rambut_helai" in bpy.data.materials:
        return
    b = bpy.data.materials.new("kurir_rambut_helai")
    if b.node_tree is None:
        b.use_nodes = True
    nt = b.node_tree
    nt.nodes.clear()
    h = nt.nodes.new("ShaderNodeBsdfHairPrincipled")
    h.parametrization = "MELANIN"
    for soket, nilai in (("Melanin", 0.97), ("Melanin Redness", 0.15), ("Roughness", 0.16),
                         ("Radial Roughness", 0.25), ("Coat", 0.35)):  # hitam, basah dan licin
        if soket in h.inputs:
            h.inputs[soket].default_value = nilai
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    nt.links.new(h.outputs[0], out.inputs["Surface"])


def _rambut(kol, arm):
    """Rambut hitam pendek yang basah: hair curves di kulit kepala, menggumpal, rebah.

    Menempel kaku pada tulang kepala (bone parent). Garis rambut di dahi lebih
    tinggi daripada di belakang dan samping.
    """
    import random as _r
    _bahan_rambut()
    rng = _r.Random(808)
    pusat, ax, ay, az = Vector((0, 0.0, 1.69)), 0.093, 0.108, 0.113
    posisi, jari = [], []
    n_gumpal = 2600
    for _ in range(n_gumpal):
        while True:
            u = Vector((rng.gauss(0, 1), rng.gauss(0, 1), rng.gauss(0, 1))).normalized()
            p = pusat + Vector((u.x * ax, u.y * ay, u.z * az))
            batas = 1.725 if u.y > 0.55 else 1.62 - 0.02 * max(0.0, -u.y)  # dahi lebih tinggi
            if p.z > batas:
                break
        nrm = Vector((u.x / ax, u.y / ay, u.z / az)).normalized()
        alir = Vector((0, -0.35, -1.0))
        alir = (alir - nrm * alir.dot(nrm)).normalized()  # menyusur kulit kepala, ke belakang-bawah
        pj = rng.uniform(0.022, 0.036)
        ujung_g = p + (alir * 0.85 + nrm * 0.18) * pj
        for _ in range(5):  # 5 helai per gumpalan basah
            geser = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))) * 0.003
            dasar = p + geser - nrm * 0.002
            ujung = (dasar + (alir * 0.85 + nrm * 0.22) * pj * rng.uniform(0.85, 1.1)).lerp(ujung_g, 0.7)
            for k in range(4):
                f = k / 3
                posisi.append(dasar.lerp(ujung, f) + nrm * (pj * 0.12 * math.sin(f * math.pi)))
                jari.append(0.0005 * (1 - 0.7 * f))
    n_helai = len(posisi) // 4
    tl = arm.data.bones["kepala"]
    ke_tulang = (tl.matrix_local @ Matrix.Translation((0, tl.length, 0))).inverted()
    cv = bpy.data.hair_curves.new("Kurir_Rambut")
    cv.add_curves([4] * n_helai)
    datar = []
    for p in posisi:
        q = ke_tulang @ p
        datar += [q.x, q.y, q.z]
    cv.position_data.foreach_set("vector", datar)
    cv.attributes.new("radius", "FLOAT", "POINT").data.foreach_set("value", jari)
    cv.materials.append(bpy.data.materials["kurir_rambut_helai"])
    obj = bpy.data.objects.new("Kurir_Rambut", cv)
    kol.objects.link(obj)
    obj.parent = arm
    obj.parent_type = "BONE"
    obj.parent_bone = "kepala"
    return obj


def tampil_rentang(obj, rentang):
    """Objek hanya tampil di render pada rentang frame yang diberikan [(awal, akhir), ...]."""
    obj.hide_render = True
    obj.keyframe_insert("hide_render", frame=min(a for a, _ in rentang) - 1)
    for a, b in rentang:
        obj.hide_render = False
        obj.keyframe_insert("hide_render", frame=a)
        obj.hide_render = True
        obj.keyframe_insert("hide_render", frame=b + 1)




def hitung_laju(arm, motor, frame_awal, frame_akhir):
    """Isi properti "laju" (m/s) kurir per frame dari kurva animasi motor dan kurir.

    Tanpa menjalankan adegan: posisi dunia = lokasi motor + putaran motor (Z)
    x lokasi kurir. Lompatan di potongan shot (lebih dari 15 m/s) diabaikan.
    """
    from bpy_extras import anim_utils
    from mathutils import Matrix

    def kurva(obj):
        ad = obj.animation_data
        cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
        return lambda jalur, i, f, d=0.0: (cb.fcurves.find(jalur, index=i).evaluate(f)
                                           if cb.fcurves.find(jalur, index=i) else d)

    km, kk = kurva(motor), kurva(arm)
    fps = bpy.context.scene.render.fps

    def posisi(f):
        m_lok = Vector([km("location", i, f) for i in range(3)])
        k_lok = Vector([kk("location", i, f) for i in range(3)])
        return m_lok + Matrix.Rotation(km("rotation_euler", 2, f), 3, "Z") @ k_lok

    lalu, laju = posisi(frame_awal), 0.0
    for f in range(frame_awal, frame_akhir + 1):
        p = posisi(f)
        v = (p - lalu).length * fps
        if v < 15:
            laju = v
        arm["laju"] = laju
        arm.keyframe_insert('["laju"]', frame=f)
        lalu = p

# Shot 5: memegang paket dengan dua tangan di depan dada, menunduk membaca label
POSE["baca_label"] = {
    "pinggul": (0, 0, 0.94), "fk": {"punggung": (-6, 0, 0), "leher": (-18, 0, 0), "kepala": (-15, 0, 0)},
    "ik": {"ik_tangan.L": (-0.17, 0.36, 1.12), "ik_tangan.R": (0.17, 0.36, 1.12),
           "ik_kaki.L": (-0.11, 0, 0.1), "ik_kaki.R": (0.11, 0, 0.1),
           "siku.L": (-0.6, -0.2, 0.9), "siku.R": (0.6, -0.2, 0.9)},
    "ik_rot": {"ik_tangan.L": (90, 0, -80), "ik_tangan.R": (90, 0, 80)},
}

# Shot 2: menoleh ke kali (kanan-depan, sedikit menunduk) dan ke layar HP (menunduk)
POSE["lihat_kali"] = {**_DUDUK, "fk": {**_DUDUK["fk"], "leher": (6, -18, 0), "kepala": (-6, -20, 0)}}
POSE["lihat_hp"] = {**_DUDUK, "fk": {**_DUDUK["fk"], "leher": (-12, 0, 0), "kepala": (-18, 0, 0)}}
