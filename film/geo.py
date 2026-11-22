"""Alat bantu geometri: menggabung banyak kotak per bahan menjadi satu objek.

Kota berisi ribuan kotak kecil (jeruji pagar, jendela, papan). Daripada
membuat ribuan objek, setiap Kanvas mengumpulkan geometri per bahan lalu
membuat satu objek per bahan. Titik mesh memakai koordinat dunia, jadi
koordinat tekstur "Object" sama dengan meter dunia.
"""

import math
import random

import bmesh
import bpy
from bpy_extras import anim_utils
from mathutils import Vector

Z = Vector((0, 0, 1))
HALUS = {"daun", "siluet"}  # bahan yang permukaannya dihaluskan (semak, sulur)


def koleksi(nama, induk=None):
    kol = bpy.data.collections.new(nama)
    (induk or bpy.context.scene.collection).children.link(kol)
    return kol


class Gabung:
    """Penampung titik dan muka untuk satu bahan."""

    def __init__(self):
        self.v = []
        self.f = []
        self.tepi = []  # atribut per titik: 0 di pusat genangan, 1 di tepinya

    def poly(self, titik, muka, tepi=None):
        o = len(self.v)
        titik = [tuple(p) for p in titik]
        self.v.extend(titik)
        self.tepi.extend(tepi if tepi is not None else [0.0] * len(titik))
        self.f.extend(tuple(i + o for i in m) for m in muka)

    def kotak(self, a, b):
        (x0, x1), (y0, y1), (z0, z1) = (sorted(p) for p in zip(a, b))
        v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
             (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
        self.poly(v, [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
                      (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)])

    def silinder(self, bawah, r, h, n=12):
        x, y, z = bawah
        v = []
        for zz in (z, z + h):
            for i in range(n):
                t = 2 * math.pi * i / n
                v.append((x + r * math.cos(t), y + r * math.sin(t), zz))
        muka = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        muka += [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
        self.poly(v, muka)

    def cakram(self, pusat, jari, z, rng, n=40, goyang=0.45):
        """Genangan datar tak beraturan: kipas dari pusat ke tepi.

        Atribut "tepi" naik dari 0 di pusat ke 1 di tepi, dipakai shader untuk
        tepi yang lembut. Tepat tiga bilangan acak diambil dari rng supaya
        urutan acak benda lain di kota tidak berubah.
        """
        x, y = pusat
        fase = [rng.uniform(0, 6.28) for _ in range(3)]
        # Lonjong dan miring, diturunkan dari fase (tanpa mengambil bilangan acak baru)
        lonjong = 1.0 + 0.45 * abs(math.sin(fase[0] * 3.7))
        miring = fase[1]
        v = [(x, y, z)]
        for i in range(n):
            t = 2 * math.pi * i / n
            r = jari * (1 + goyang * (0.45 * math.sin(2 * t + fase[0])
                                      + 0.3 * math.sin(3 * t + fase[1])
                                      + 0.15 * math.sin(5 * t + fase[2])
                                      + 0.1 * math.sin(9 * t + fase[0] + fase[2])))
            px, py = r * math.cos(t) * lonjong, r * math.sin(t) / lonjong
            v.append((x + px * math.cos(miring) - py * math.sin(miring),
                      y + px * math.sin(miring) + py * math.cos(miring), z))
        muka = [(0, 1 + i, 1 + (i + 1) % n) for i in range(n)]
        self.poly(v, muka, tepi=[0.0] + [1.0] * n)

    def bola(self, pusat, skala, rimbun=7):
        """Gumpalan daun: bola halus ditambah gumpalan kecil di permukaannya.

        Gumpalan tambahan memakai rng sendiri dari posisi, jadi pusat dan ukuran
        bola utama (dan urutan rng kota) tidak berubah.
        """
        sx, sy, sz = skala
        px, py, pz = pusat
        tv, tf = _ikosfer(3)
        self.poly([(px + x * sx, py + y * sy, pz + z * sz) for x, y, z in tv], tf)
        rd = random.Random(f"daun {px:.3f} {py:.3f} {pz:.3f}")
        kv, kf = _ikosfer(2)
        for _ in range(rimbun):
            arah = Vector((rd.gauss(0, 1), rd.gauss(0, 1), abs(rd.gauss(0, 1)) * 0.8)).normalized()
            r = rd.uniform(0.35, 0.55)
            qx, qy, qz = (px + arah.x * sx * 0.72, py + arah.y * sy * 0.72, pz + arah.z * sz * 0.72)
            self.poly([(qx + x * sx * r, qy + y * sy * r, qz + z * sz * r) for x, y, z in kv], kf)

    def tabung(self, p0, p1, r, n=10):
        """Tabung bulat dari p0 ke p1 (pipa, garpu, setang)."""
        p0, p1 = Vector(p0), Vector(p1)
        sumbu = (p1 - p0).normalized()
        bantu = Vector((0, 0, 1)) if abs(sumbu.z) < 0.9 else Vector((1, 0, 0))
        u = sumbu.cross(bantu).normalized()
        w = sumbu.cross(u).normalized()
        ring = [(u * math.cos(2 * math.pi * i / n) + w * math.sin(2 * math.pi * i / n)) * r for i in range(n)]
        muka = [(i, (i + 1) % n, n + (i + 1) % n, n + i) for i in range(n)]
        muka += [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
        self.poly([p0 + q for q in ring] + [p1 + q for q in ring], muka)

    def batang(self, p0, p1, tebal):
        """Batang persegi dari p0 ke p1 (siku, pipa miring)."""
        p0, p1 = Vector(p0), Vector(p1)
        sumbu = (p1 - p0).normalized()
        bantu = Vector((0, 0, 1)) if abs(sumbu.z) < 0.9 else Vector((1, 0, 0))
        u = sumbu.cross(bantu).normalized() * tebal / 2
        w = sumbu.cross(u).normalized() * tebal / 2
        sudut = [u + w, u - w, -u - w, -u + w]
        self.poly([p0 + s for s in sudut] + [p1 + s for s in sudut],
                  [(0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)])


_IKO = {}


def _ikosfer(sub):
    if sub not in _IKO:
        bm = bmesh.new()
        bmesh.ops.create_icosphere(bm, subdivisions=sub, radius=1.0)
        _IKO[sub] = ([tuple(v.co) for v in bm.verts], [tuple(v.index for v in f.verts) for f in bm.faces])
        bm.free()
    return _IKO[sub]


class Kanvas:
    """Satu koleksi; geometri dikumpulkan per nama bahan."""

    def __init__(self, nama, induk=None):
        self.nama = nama
        self.kol = koleksi(nama, induk)
        self._g = {}

    def __getitem__(self, bahan):
        return self._g.setdefault(bahan, Gabung())

    def objek(self, nama, data):
        obj = bpy.data.objects.new(nama, data)
        self.kol.objects.link(obj)
        return obj

    def selesai(self):
        for bahan, g in self._g.items():
            if not g.f:
                continue
            mesh = bpy.data.meshes.new(f"{self.nama}_{bahan}")
            mesh.from_pydata(g.v, [], g.f)
            if any(g.tepi):
                atr = mesh.attributes.new("tepi", "FLOAT", "POINT")
                atr.data.foreach_set("value", g.tepi)
            bm = bmesh.new()
            bm.from_mesh(mesh)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bm.to_mesh(mesh)
            bm.free()
            mesh.materials.append(bpy.data.materials[bahan])
            if bahan in HALUS:
                mesh.shade_smooth()
            self.objek(f"{self.nama}_{bahan}", mesh)
        self._g.clear()


class Bingkai:
    """Koordinat lokal untuk deretan bangunan.

    a: sepanjang jalan (u), b: masuk ke dalam kavling (n), c: ke atas.
    b < 0 berarti di depan fasad, ke arah jalan.
    Hanya untuk u dan n yang sejajar sumbu X atau Y.
    """

    def __init__(self, asal, u, n):
        self.asal = Vector(asal)
        self.u = Vector(u)
        self.n = Vector(n)

    def titik(self, a, b, c=0.0):
        return self.asal + self.u * a + self.n * b + Z * c

    def kotak(self, g, a0, a1, b0, b1, c0, c1):
        g.kotak(self.titik(a0, b0, c0), self.titik(a1, b1, c1))

    def poly(self, g, titik_lokal, muka):
        g.poly([self.titik(*p) for p in titik_lokal], muka)

    def batang(self, g, p0, p1, tebal):
        g.batang(self.titik(*p0), self.titik(*p1), tebal)

    def lingkaran(self, g, a, b, c, r, n=20):
        """Cakram tegak menghadap jalan, di bidang a-c pada kedalaman b."""
        g.poly([self.titik(a + r * math.cos(2 * math.pi * i / n), b, c + r * math.sin(2 * math.pi * i / n))
                for i in range(n)], [tuple(range(n))])

    def silinder(self, g, a, b, c, r, tinggi, n=10):
        g.silinder(self.titik(a, b, c), r, tinggi, n)

    @property
    def muka(self):
        """Arah hadap fasad (ke jalan)."""
        return -self.n


def kabel(kanvas, nama, pasangan, bahan, tebal=0.008):
    """Kabel melendut. pasangan: daftar (titik_a, titik_b, lendut)."""
    kurva = bpy.data.curves.new(nama, type="CURVE")
    kurva.dimensions = "3D"
    kurva.bevel_depth = tebal
    kurva.bevel_resolution = 1
    for a, b, lendut in pasangan:
        a, b = Vector(a), Vector(b)
        sp = kurva.splines.new("POLY")
        n = 14
        sp.points.add(n - 1)
        for i in range(n):
            t = i / (n - 1)
            p = a.lerp(b, t) - Z * (4 * lendut * t * (1 - t))
            sp.points[i].co = (*p, 1.0)
    kurva.materials.append(bpy.data.materials[bahan])
    return kanvas.objek(nama, kurva)


def teks(kanvas, nama, isi, lokasi, hadap, ukuran, bahan, tebal=0.004):
    """Tulisan berdiri, menghadap vektor horizontal `hadap`."""
    kurva = bpy.data.curves.new(nama, type="FONT")
    kurva.body = isi
    kurva.align_x = "CENTER"
    kurva.align_y = "CENTER"
    kurva.size = ukuran
    kurva.extrude = tebal
    kurva.materials.append(bpy.data.materials[bahan])
    obj = kanvas.objek(nama, kurva)
    obj.location = lokasi
    obj.rotation_euler = (math.pi / 2, 0, math.atan2(hadap[0], -hadap[1]))
    return obj


def animasi_linear(id_data, siklus=False):
    """Jadikan semua kunci animasi linear; berulang (siklus) atau terus berlanjut."""
    ad = id_data.animation_data
    cb = anim_utils.action_get_channelbag_for_slot(ad.action, ad.action_slot)
    for fc in cb.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = "LINEAR"
        if siklus:
            fc.modifiers.new("CYCLES")
        else:
            fc.extrapolation = "LINEAR"
