"""Anak kecil di ambang pintu: hanya siluet gelap, membawa kue dengan tiga lilin.

Wajah anak tidak pernah terlihat:
- tubuh memakai bahan hampir hitam dan sangat kasar (tidak ada detail);
- cahaya rumah datang dari belakang anak (lihat dunia_kota._isi_rumah_tujuan);
- api lilin tidak menjadi sumber cahaya bagi permukaan lain (visibilitas
  sinar dimatikan), dan lampu lilin memakai light linking: hanya menerangi
  kue, piring, dan lilin, bukan anak.

Api lilin bergoyang dengan pola tetap (random.Random(SEED)).
Titik pusat "Anak" di lantai di antara kedua kaki, menghadap +Y lokal.
"""

import math
import random

import bpy
from mathutils import Vector

from . import bahan
from .geo import Gabung, Kanvas

SEED = 1997
TINGGI_KUE = 0.74  # tinggi permukaan piring kue dari lantai
POSISI_KUE = Vector((0, 0.24, TINGGI_KUE))  # disodorkan sedikit ke depan
CONDONG = 7.0  # derajat badan condong ke depan (poros di pinggul)


def _condong(derajat, poros=Vector((0, 0, 0.5))):
    """Fungsi titik -> titik: badan atas diputar ke depan (+Y) di sekitar pinggul."""
    from mathutils import Matrix
    r = Matrix.Rotation(math.radians(-derajat), 3, "X")
    return lambda p: poros + r @ (Vector(p) - poros)


def _loft(g, ruas, n=16, tutup_bawah=True):
    """Tabung lembut melewati beberapa titik: [(pusat, jari_u, jari_w, gelombang), ...].

    Penampang tegak lurus arah ruas; gelombang membuat tepi kain tidak rata.
    """
    titik, muka = [], []
    for k, (c, ru, rw, gel) in enumerate(ruas):
        a = ruas[max(k - 1, 0)][0]
        b = ruas[min(k + 1, len(ruas) - 1)][0]
        sumbu = (b - a).normalized()
        bantu = Vector((1, 0, 0)) if abs(sumbu.x) < 0.9 else Vector((0, 1, 0))
        u = (bantu - sumbu * bantu.dot(sumbu)).normalized()
        w = sumbu.cross(u)
        for i in range(n):
            t = 2 * math.pi * i / n
            r = 1 + gel / max(ru, 1e-3) * math.sin(5 * t + 0.7 * k) if gel else 1
            titik.append(c + (u * math.cos(t) * ru + w * math.sin(t) * rw) * r)
    for k in range(len(ruas) - 1):
        for i in range(n):
            p, q = k * n, (k + 1) * n
            muka.append((p + i, p + (i + 1) % n, q + (i + 1) % n, q + i))
    if tutup_bawah:
        muka.append(tuple(reversed(range(n))))
    muka.append(tuple(range((len(ruas) - 1) * n, len(ruas) * n)))
    g.poly(titik, muka)


def _bahan():
    if "siluet" in bpy.data.materials:
        return
    b = bahan.polos("siluet", (0.002, 0.002, 0.002), kasar=1.0)
    # Tanpa kilap: tidak memantulkan ruangan yang terang ke arah kamera
    b.node_tree.nodes["Principled BSDF"].inputs["Specular IOR Level"].default_value = 0.0
    bahan.polos("kue_krim", (0.85, 0.78, 0.66), kasar=0.45)
    bahan.polos("kue_coklat", (0.12, 0.05, 0.025), kasar=0.6)
    bahan.polos("kue_piring", (0.8, 0.8, 0.78), kasar=0.2)
    bahan.polos("lilin_merah", (0.8, 0.12, 0.15), kasar=0.4)
    bahan.polos("lilin_biru", (0.12, 0.3, 0.8), kasar=0.4)
    bahan.polos("lilin_kuning", (0.9, 0.75, 0.15), kasar=0.4)
    bahan.polos("api_lilin", (0.0, 0.0, 0.0), emisi=(1.0, 0.62, 0.22), kuat=18.0)


def buat_anak(kol, lokasi, arah_derajat):
    """Siluet anak (sekitar 1,1 m) memegang kue di depan dada. Kembalikan (anak, api, lampu)."""
    _bahan()
    akar = bpy.data.objects.new("Anak", None)
    kol.objects.link(akar)
    akar.location = lokasi
    akar.rotation_euler = (0, 0, math.radians(arah_derajat))

    # Anak umur enam tahun (sekitar 112 cm): kepala besar (seperlima tinggi),
    # badan pendek, baju tidur longgar yang ujungnya bergelombang, celana tidur
    # lebar, lutut sedikit menekuk, badan condong ke depan menyodorkan kue.
    k = Kanvas("Anak_Siluet", kol)
    g = k["siluet"]
    condong = _condong(CONDONG)
    for x in (-0.065, 0.065):  # celana tidur: pinggul, lutut (sedikit ke depan), pergelangan
        _loft(g, [(Vector((x, -0.012, 0.55)), 0.075, 0.075, 0.0), (Vector((x, 0.02, 0.42)), 0.068, 0.07, 0.003),
                  (Vector((x, 0.055, 0.29)), 0.062, 0.064, 0.004), (Vector((x, 0.035, 0.17)), 0.062, 0.064, 0.004),
                  (Vector((x, 0.01, 0.05)), 0.066, 0.068, 0.007)])
        g.bola((x * 1.05, 0.045, 0.032), (0.045, 0.085, 0.032), rimbun=0)  # sandal rumah
    g.bola((0, 0.0, 0.53), (0.13, 0.095, 0.08), rimbun=0)  # pinggul
    # Baju tidur: lebar dan longgar, ujung bawah bergelombang
    _loft(g, [(condong(Vector((0, 0, z))), rx, ry, gel) for z, rx, ry, gel in (
        (0.43, 0.185, 0.14, 0.018), (0.5, 0.17, 0.127, 0.01), (0.6, 0.152, 0.11, 0.004),
        (0.72, 0.143, 0.1, 0.0), (0.79, 0.135, 0.092, 0.0), (0.83, 0.1, 0.075, 0.0), (0.855, 0.05, 0.048, 0.0))],
          tutup_bawah=True)
    g.tabung(condong(Vector((0, 0, 0.83))), condong(Vector((0, 0.008, 0.9))), 0.034, n=10)  # leher
    kepala = condong(Vector((0, 0.012, 1.0)))
    g.bola(kepala, (0.1, 0.106, 0.112), rimbun=0)  # kepala besar
    g.bola(kepala + Vector((0, -0.012, 0.018)), (0.107, 0.11, 0.102), rimbun=0)  # rambut
    rr = random.Random(SEED + 1)
    for _ in range(16):  # ujung rambut bergumpal kecil di tepi siluet
        a = rr.uniform(-0.2, 3.34)
        g.bola(kepala + Vector((0.106 * math.cos(a), -0.02 - 0.05 * rr.random(), 0.018 + 0.08 * math.sin(a))),
               (0.022, 0.022, 0.02), rimbun=0)
    for x in (-1, 1):  # lengan baju longgar: bahu, siku menjauh dari badan, tangan di bawah piring
        bahu = condong(Vector((x * 0.125, 0.0, 0.8)))
        siku = Vector((x * 0.175, bahu.y + 0.07, 0.65))
        tangan = Vector((x * 0.125, POSISI_KUE.y + 0.01, POSISI_KUE.z - 0.012))
        _loft(g, [(bahu, 0.05, 0.05, 0.0), (siku, 0.047, 0.047, 0.0),
                  (siku.lerp(tangan, 0.85), 0.045, 0.045, 0.003)])
        g.bola(tangan, (0.03, 0.04, 0.022), rimbun=0)
    k.selesai()
    for o in k.kol.objects:
        o.parent = akar
        sub = o.modifiers.new("Halus", "SUBSURF")
        sub.levels = sub.render_levels = 2

    # Kue di atas piring, tiga lilin
    kue = Kanvas("Anak_Kue", kol)
    pusat = POSISI_KUE.copy()
    kue["kue_piring"].tabung(pusat, pusat + Vector((0, 0, 0.01)), 0.14, n=28)
    kue["kue_coklat"].tabung(pusat + Vector((0, 0, 0.01)), pusat + Vector((0, 0, 0.05)), 0.105, n=28)
    kue["kue_krim"].tabung(pusat + Vector((0, 0, 0.05)), pusat + Vector((0, 0, 0.085)), 0.108, n=28)
    lilin_pos = []
    for i, nama_bahan in enumerate(("lilin_merah", "lilin_biru", "lilin_kuning")):
        s = 2 * math.pi * i / 3 + 0.4
        p = pusat + Vector((0.05 * math.cos(s), 0.05 * math.sin(s), 0.085))
        kue[nama_bahan].tabung(p, p + Vector((0, 0, 0.065)), 0.0055, n=8)
        lilin_pos.append(p + Vector((0, 0, 0.065)))
    kue.selesai()
    for o in kue.kol.objects:
        o.parent = akar

    # Api dan lampu lilin; lampu hanya menerangi kue (light linking)
    terima = bpy.data.collections.new("Kue_Diterangi_Lilin")
    for o in kue.kol.objects:
        terima.objects.link(o)
    api_list, lampu_list = [], []
    for i, p in enumerate(lilin_pos):
        g = Gabung()
        g.bola((0, 0, 0.012), (0.0045, 0.0045, 0.013), rimbun=0)
        mesh = bpy.data.meshes.new(f"Api_Lilin_{i}")
        mesh.from_pydata(g.v, [], g.f)
        mesh.materials.append(bpy.data.materials["api_lilin"])
        mesh.shade_smooth()
        api = bpy.data.objects.new(f"Api_Lilin_{i}", mesh)
        kol.objects.link(api)
        api.parent = akar
        api.location = p + Vector((0, 0, 0.002))
        # Api terlihat kamera, tetapi tidak menerangi permukaan lain (wajah anak)
        api.visible_diffuse = False
        api.visible_glossy = False
        api.visible_transmission = False
        api.visible_volume_scatter = False
        api.visible_shadow = False
        data = bpy.data.lights.new(f"Lampu_Lilin_{i}", type="POINT")
        data.color = (1.0, 0.6, 0.25)
        data.energy = 0.6
        data.shadow_soft_size = 0.004
        lampu = bpy.data.objects.new(f"Lampu_Lilin_{i}", data)
        kol.objects.link(lampu)
        lampu.parent = akar
        lampu.location = p + Vector((0, 0, 0.014))
        lampu.light_linking.receiver_collection = terima
        api_list.append(api)
        lampu_list.append(lampu)
    for item in terima.collection_objects:
        item.light_linking.link_state = "INCLUDE"
    return akar, api_list, lampu_list


def goyang_api(api_list, lampu_list, frame_awal, frame_akhir, langkah=2):
    """Api bergoyang dengan pola tetap: tinggi, condong, dan terang berubah tiap `langkah` frame."""
    rng = random.Random(SEED)
    for api, lampu in zip(api_list, lampu_list):
        fase = rng.uniform(0, 6.28)
        for f in range(frame_awal, frame_akhir + 1, langkah):
            t = f * 0.35 + fase
            tinggi = 1.0 + 0.12 * math.sin(t) + rng.uniform(-0.08, 0.08)
            api.scale = (1.0, 1.0, tinggi)
            api.rotation_euler = (math.radians(rng.uniform(-6, 6)), math.radians(6 * math.sin(t * 0.7)), 0)
            api.keyframe_insert("scale", frame=f)
            api.keyframe_insert("rotation_euler", frame=f)
            lampu.data.energy = 0.6 * (0.85 + 0.15 * tinggi + rng.uniform(-0.05, 0.05))
            lampu.data.keyframe_insert("energy", frame=f)
