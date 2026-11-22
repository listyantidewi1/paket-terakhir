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


def _bahan():
    if "siluet" in bpy.data.materials:
        return
    bahan.polos("siluet", (0.004, 0.004, 0.004), kasar=1.0)
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

    k = Kanvas("Anak_Siluet", kol)
    g = k["siluet"]
    for x in (-0.06, 0.06):  # kaki
        g.tabung((x, 0.0, 0.0), (x, 0.0, 0.5), 0.045, n=10)
        g.kotak((x - 0.04, -0.03, 0.0), (x + 0.04, 0.09, 0.05))
    g.bola((0, 0.0, 0.66), (0.13, 0.09, 0.2), rimbun=0)  # badan
    g.bola((0, 0.0, 0.92), (0.085, 0.095, 0.1), rimbun=0)  # kepala
    g.bola((0, -0.02, 0.95), (0.095, 0.095, 0.085), rimbun=0)  # rambut, sedikit mengembang
    for x in (-1, 1):  # lengan: bahu turun lalu menjulur ke depan menyangga piring
        g.tabung((x * 0.11, 0.0, 0.8), (x * 0.12, 0.08, 0.66), 0.03, n=8)
        g.tabung((x * 0.12, 0.08, 0.66), (x * 0.1, 0.2, TINGGI_KUE - 0.02), 0.026, n=8)
    k.selesai()
    for o in k.kol.objects:
        o.parent = akar

    # Kue di atas piring, tiga lilin
    kue = Kanvas("Anak_Kue", kol)
    pusat = Vector((0, 0.22, TINGGI_KUE))
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
