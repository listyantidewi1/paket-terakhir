"""Ekspor motor bebek (dengan boks dan paket) dan helm ke glTF biner untuk game Kurir Senja.

Jalankan:
    blender --background --python ekspor.py

Hasil:
    ekspor/motor_bebek.glb   Motor_Bebek
                               Badan          rangka, mesin, jok, boks (titik pusat di tanah)
                               Setang         titik putar di kepala rangka (belok: putar sumbu tegak)
                                 Roda_Depan   titik putar di as roda depan (putar sumbu X)
                               Roda_Belakang  titik putar di as roda belakang (putar sumbu X)
                               Boks_Tutup     titik putar di engsel belakang boks
                               Paket          titik pusat di dasar paket
    ekspor/helm.glb          Helm, titik pusat di tengah bawah helm

Motor dan helm dibangun baru dari kode di film/ (bukan dari film.blend), jadi
selalu dalam posisi diam: tanpa animasi, driver, kurir, kamera, atau lampu.
Satuan meter. Di Blender depan = +Y dan atas = +Z; eksportir glTF (Y ke atas)
mengubahnya menjadi depan = -Z, atas = +Y, kanan = +X.

Hampir semua bahan berwarna polos (faktor warna, kilap, logam, emisi, clearcoat
di glTF). Satu-satunya pola, noda air di label paket (noise prosedural), di-bake
ke tekstur PNG 512 px yang disimpan di dalam file .glb. Setelah ekspor, kedua
file dibaca kembali dan isinya ditampilkan sebagai tabel.
"""

import json
import os
import struct
import sys

import bpy
from mathutils import Matrix, Vector

AKAR = os.path.dirname(os.path.abspath(__file__))
if AKAR not in sys.path:
    sys.path.insert(0, AKAR)

from film import kurir, motor  # noqa: E402

FOLDER = os.path.join(AKAR, "ekspor")
TEKSTUR_LABEL = 512

# Empty di motor asli -> (nama objek ekspor, nama induknya di ekspor)
BAGIAN = {
    "Motor": ("Badan", "Motor_Bebek"),
    "Motor_Kemudi": ("Setang", "Motor_Bebek"),
    "Motor_Roda_Depan": ("Roda_Depan", "Setang"),
    "Motor_Roda_Belakang": ("Roda_Belakang", "Motor_Bebek"),
    "Motor_Boks_Tutup": ("Boks_Tutup", "Motor_Bebek"),
    "Paket": ("Paket", "Motor_Bebek"),
}


def mulai_kosong():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    sumber = bpy.data.collections.new("Sumber")
    hasil = bpy.data.collections.new("Ekspor")
    sc.collection.children.link(sumber)
    sc.collection.children.link(hasil)
    return sumber, hasil


def mesh_dunia(obj, depsgraph):
    """Mesh dengan semua modifier diterapkan (teks juga), dalam koordinat dunia."""
    me = bpy.data.meshes.new_from_object(obj.evaluated_get(depsgraph), preserve_all_data_layers=True,
                                         depsgraph=depsgraph)
    me.transform(obj.matrix_world)
    return me


def aktifkan(obj, pilih):
    lapisan = bpy.context.view_layer
    for o in lapisan.objects:
        o.select_set(False)
    for o in pilih:
        o.select_set(True)
    lapisan.objects.active = obj


def gabung(nama, meshes, poros, kol):
    """Satukan beberapa mesh (koordinat dunia) menjadi satu objek dengan titik pusat di `poros`."""
    objs = []
    for i, me in enumerate(meshes):
        o = bpy.data.objects.new(f"{nama}_{i}", me)
        kol.objects.link(o)
        objs.append(o)
    aktifkan(objs[0], objs)
    if len(objs) > 1:
        bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    lama = bpy.data.objects.get(nama)
    if lama is not None and lama is not obj:  # objek sumber bernama sama (misalnya empty "Paket")
        lama.name = f"{nama}_sumber"
    obj.name = obj.data.name = nama
    obj.data.transform(Matrix.Translation(-poros))
    obj.location = poros
    return obj


def bake_label(obj_label, kol):
    """Bake warna label kertas (noda air prosedural) ke gambar; bahan memakai gambar itu."""
    sc = bpy.context.scene
    aktifkan(obj_label, [obj_label])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(island_margin=0.02)
    bpy.ops.object.mode_set(mode="OBJECT")

    bahan = obj_label.data.materials[0]
    nt = bahan.node_tree
    img = bpy.data.images.new("label_noda", TEKSTUR_LABEL, TEKSTUR_LABEL)
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    nt.nodes.active = tex
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 16
    bpy.ops.object.bake(type="DIFFUSE", pass_filter={"COLOR"}, margin=4, use_clear=True)
    img.file_format = "PNG"
    img.pack()
    # Warna dasar kini dari gambar (UV), bukan dari noise berkoordinat objek
    bsdf = nt.nodes["Principled BSDF"]
    for l in list(bsdf.inputs["Base Color"].links):
        nt.links.remove(l)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return img


def bangun_motor(sumber, hasil):
    akar = motor.buat_motor(sumber)
    for o in akar.children_recursive:  # roda diam: tanpa driver jarak_tempuh
        if o.animation_data:
            o.animation_data_clear()
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()

    def pemilik(o):
        p = o.parent
        while p.name not in BAGIAN:
            p = p.parent
        return p.name

    kumpulan = {k: [] for k in BAGIAN}
    for o in akar.children_recursive:
        if o.type in ("MESH", "FONT", "CURVE"):
            kumpulan[pemilik(o)].append(o)

    root = bpy.data.objects.new("Motor_Bebek", None)  # titik pusat: tanah, tengah antara titik sentuh roda
    hasil.objects.link(root)
    dibuat = {"Motor_Bebek": root}
    label = None
    for asal in BAGIAN:  # urutan BAGIAN: induk selalu dibuat lebih dulu
        nama, induk = BAGIAN[asal]
        meshes = []
        for o in kumpulan[asal]:
            me = mesh_dunia(o, dg)
            if me.materials and me.materials[0].name == "kertas_label":
                tmp = bpy.data.objects.new("Label_Bake", me)
                hasil.objects.link(tmp)
                label = bake_label(tmp, hasil)
                bpy.data.objects.remove(tmp)
            meshes.append(me)
        poros = bpy.data.objects[asal].matrix_world.translation.copy()
        obj = gabung(nama, meshes, poros, hasil)
        obj.parent = dibuat[induk]
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.location = poros - dibuat[induk].matrix_world.translation
        bpy.context.view_layer.update()
        dibuat[nama] = obj
    if label is None:
        print("[ekspor] PERINGATAN: label kertas tidak ditemukan; tidak ada tekstur yang di-bake")
    return root


def bangun_helm(sumber, hasil):
    motor._bahan()  # strip_pemantul di helm memakai bahan yang sama dengan boks motor
    kurir._bahan()
    arm = kurir._armature(sumber, "Kurir_Ekspor")
    arm.data.pose_position = "REST"
    helm = kurir._helm(sumber, arm)
    bpy.context.view_layer.update()
    me = mesh_dunia(helm, bpy.context.evaluated_depsgraph_get())
    xs, ys, zs = zip(*(v.co for v in me.vertices))
    poros = Vector(((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, min(zs)))  # tengah bawah helm
    obj = gabung("Helm", [me], poros, hasil)
    obj.location = (0, 0, 0)  # helm berdiri di tanah, di titik asal
    return obj


def ekspor(root, berkas):
    aktifkan(root, [root] + list(root.children_recursive))
    bpy.ops.export_scene.gltf(
        filepath=berkas, export_format="GLB", use_selection=True,
        export_yup=True, export_apply=True, export_cameras=False, export_lights=False,
        export_animations=False, export_extras=False, export_image_format="AUTO",
    )


# --------------------------------------------------------------------------
# Membaca kembali

def baca_glb(berkas):
    with open(berkas, "rb") as f:
        data = f.read()
    sihir, versi, panjang = struct.unpack_from("<III", data, 0)
    assert sihir == 0x46546C67 and versi == 2 and panjang == len(data), f"{berkas} bukan GLB 2.0 yang utuh"
    n_json, jenis = struct.unpack_from("<II", data, 12)
    assert jenis == 0x4E4F534A
    return json.loads(data[20:20 + n_json])


def laporan(berkas):
    g = baca_glb(berkas)
    induk = {c: i for i, n in enumerate(g["nodes"]) for c in n.get("children", [])}

    def dunia(i):
        t = Vector(g["nodes"][i].get("translation", (0, 0, 0)))
        return t + dunia(induk[i]) if i in induk else t

    baris, bawah = [], []
    for i, n in enumerate(g["nodes"]):
        segitiga = 0
        if "mesh" in n:
            for p in g["meshes"][n["mesh"]]["primitives"]:
                assert p.get("mode", 4) == 4
                segitiga += g["accessors"][p["indices"]]["count"] // 3
                a = g["accessors"][p["attributes"]["POSITION"]]
                bawah.append((Vector(a["min"]) + dunia(i), Vector(a["max"]) + dunia(i)))
        rot = n.get("rotation", (0, 0, 0, 1))
        baris.append((n["name"], g["nodes"][induk[i]]["name"] if i in induk else "-", segitiga,
                      tuple(round(x, 3) for x in n.get("translation", (0, 0, 0))), rot == (0, 0, 0, 1) or rot == [0, 0, 0, 1]))
    lo = Vector([min(b[0][k] for b in bawah) for k in range(3)])
    hi = Vector([max(b[1][k] for b in bawah) for k in range(3)])
    gambar = [(im.get("name", "?"), im.get("mimeType", "?")) for im in g.get("images", [])]
    return baris, lo, hi, gambar, g


def tampilkan(berkas):
    baris, lo, hi, gambar, g = laporan(berkas)
    ukuran = os.path.getsize(berkas)
    print(f"\n{os.path.relpath(berkas, AKAR)}  ({ukuran / 1024:.1f} KB, {ukuran:,} byte)")
    print(f"  {'objek':15s} {'induk':12s} {'segitiga':>9s}  titik putar (glTF x, y, z)")
    for nama, ind, seg, t, _ in baris:
        print(f"  {nama:15s} {ind:12s} {seg:9,d}  {t}")
    print(f"  {'jumlah':15s} {'':12s} {sum(b[2] for b in baris):9,d}")
    print(f"  batas glTF: x {lo.x:.3f}..{hi.x:.3f}, y {lo.y:.3f}..{hi.y:.3f} (tanah di y=0), "
          f"z {lo.z:.3f}..{hi.z:.3f} m")
    print(f"  tekstur di dalam file: {gambar or 'tidak ada'}; bahan: {len(g.get('materials', []))}; "
          f"kamera: {len(g.get('cameras', []))}; lampu: {len(g.get('extensions', {}).get('KHR_lights_punctual', {}).get('lights', []))}; "
          f"animasi: {len(g.get('animations', []))}")
    return baris, lo, hi


def periksa_impor(berkas):
    """Impor ke adegan kosong: file bisa dibaca Blender, nama objek dan segitiga sama."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=berkas)
    hasil = {}
    for o in bpy.context.scene.objects:
        if o.type == "MESH":
            o.data.calc_loop_triangles()
            hasil[o.name] = len(o.data.loop_triangles)
    return hasil


def main():
    os.makedirs(FOLDER, exist_ok=True)
    keluaran = []

    sumber, hasil = mulai_kosong()
    root = bangun_motor(sumber, hasil)
    berkas = os.path.join(FOLDER, "motor_bebek.glb")
    ekspor(root, berkas)
    keluaran.append(berkas)

    sumber, hasil = mulai_kosong()
    helm = bangun_helm(sumber, hasil)
    berkas = os.path.join(FOLDER, "helm.glb")
    ekspor(helm, berkas)
    keluaran.append(berkas)

    for berkas in keluaran:
        baris, lo, hi = tampilkan(berkas)
        impor = periksa_impor(berkas)
        cocok = all(impor.get(n) == s for n, _, s, _, _ in baris if s)
        print(f"  dibaca ulang dengan importer glTF Blender: {len(impor)} mesh, segitiga "
              f"{'sama' if cocok else 'BERBEDA: ' + str(impor)}")
        if abs(lo.y) > 0.005:
            print(f"  PERINGATAN: titik terendah di y={lo.y:.3f}, bukan di tanah")


main()
