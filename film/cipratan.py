"""Cipratan air saat roda motor melewati genangan.

Genangan dicatat oleh dunia_kota (GENANGAN: pusat dan poligon tepi). Dari
lintasan motor per frame (hasil motor.animasi_jalan) dicari frame-frame
ketika titik sentuh roda depan atau belakang berada di dalam genangan. Tiap
kejadian menjadi satu sistem partikel yang hanya memancar selama roda di
dalam genangan, dari pemancar kecil di titik sentuh roda tersebut.

Partikel disimulasikan frame demi frame (seperti kain), jadi cek.py
menjalankan simulasi berurutan sebelum merender.
"""

import math

import bpy
from mathutils import Vector

from . import bahan
from .motor import Y_BELAKANG, Y_DEPAN

DALAM = 0.8  # roda dianggap di air bila di dalam 80% poligon (tepi genangan lembut/dangkal)


def _di_dalam(x, y, genangan):
    cx, cy = genangan["pusat"]
    poli = [(cx + (px - cx) * DALAM, cy + (py - cy) * DALAM) for px, py in genangan["tepi"]]
    dalam = False
    j = len(poli) - 1
    for i in range(len(poli)):
        xi, yi = poli[i]
        xj, yj = poli[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dalam = not dalam
        j = i
    return dalam


def cari_kejadian(jalur, genangan, frame_awal, frame_akhir):
    """Kembalikan daftar (roda, frame_mulai, frame_selesai, indeks_genangan)."""
    kejadian = []
    for roda, y_roda in (("depan", Y_DEPAN), ("belakang", Y_BELAKANG)):
        aktif = None
        for f, p, arah in jalur:
            if not frame_awal <= f <= frame_akhir:
                continue
            a = math.radians(arah)
            x, y = p.x - math.sin(a) * y_roda, p.y + math.cos(a) * y_roda
            kena = next((i for i, g in enumerate(genangan) if _di_dalam(x, y, g)), None)
            if kena is not None and aktif is None:
                aktif = [roda, f, f, kena]
            elif kena is not None:
                aktif[2] = f
            elif aktif is not None:
                kejadian.append(tuple(aktif))
                aktif = None
        if aktif is not None:
            kejadian.append(tuple(aktif))
    return sorted(kejadian, key=lambda k: k[1])


def _tetes(kol):
    """Satu tetes air (sumber instans), disembunyikan jauh di bawah tanah."""
    obj = bpy.data.objects.get("Cipratan_Tetes")
    if obj:
        return obj
    if "air_tetes" not in bpy.data.materials:
        b = bahan.polos("air_tetes", (0.9, 0.92, 0.95), kasar=0.05)
        bsdf = b.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Transmission Weight"].default_value = 1.0
        bsdf.inputs["IOR"].default_value = 1.33
    mesh = bpy.data.meshes.new("Cipratan_Tetes")
    import bmesh
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=1, radius=1.0)
    bm.to_mesh(mesh)
    bm.free()
    mesh.materials.append(bpy.data.materials["air_tetes"])
    mesh.shade_smooth()
    obj = bpy.data.objects.new("Cipratan_Tetes", mesh)
    kol.objects.link(obj)
    obj.location = (0, 0, -50)
    return obj


def _pemancar(kol, motor, roda, y_roda):
    nama = f"Cipratan_Roda_{roda.capitalize()}"
    obj = bpy.data.objects.get(nama)
    if obj:
        return obj
    mesh = bpy.data.meshes.new(nama)
    w, l = 0.05, 0.08  # selebar tapak ban
    mesh.from_pydata([(-w, -l, 0), (w, -l, 0), (w, l, 0), (-w, l, 0)], [], [(0, 1, 2, 3)])
    obj = bpy.data.objects.new(nama, mesh)
    kol.objects.link(obj)
    obj.parent = motor
    obj.location = (0, y_roda, 0.015)
    obj.show_instancer_for_render = False
    obj.show_instancer_for_viewport = False
    return obj


def buat(kol, motor, kejadian):
    """Satu sistem partikel per kejadian roda masuk genangan."""
    tetes = _tetes(kol)
    for n, (roda, f0, f1, g) in enumerate(kejadian):
        pemancar = _pemancar(kol, motor, roda, Y_DEPAN if roda == "depan" else Y_BELAKANG)
        st = bpy.data.particles.new(f"Cipratan_{n:02d}_{roda}_f{f0}")
        st.count = 350
        st.frame_start = f0 - 0.5
        st.frame_end = f1 + 0.5
        st.lifetime = 16
        st.lifetime_random = 0.5
        st.emit_from = "FACE"
        st.physics_type = "NEWTON"
        st.normal_factor = 1.4  # ke atas
        st.object_align_factor = (0.0, -1.6, 0.6)  # dilempar tapak ban ke belakang
        st.factor_random = 1.3  # menyebar ke samping
        st.object_factor = 0.25  # sedikit ikut laju motor
        st.render_type = "OBJECT"
        st.instance_object = tetes
        st.particle_size = 0.007
        st.size_random = 0.7
        st.use_rotations = False
        mod = pemancar.modifiers.new(f"Cipratan_{n:02d}", "PARTICLE_SYSTEM")
        mod.particle_system.settings = st
        mod.particle_system.seed = 11 + n
    return kejadian
