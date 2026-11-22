"""Bahan (material) dan langit untuk Kota Senja.

Tekstur dan HDRI dibaca dari aset/ (diunduh oleh aset.py). Benda yang tidak
punya tekstur (cat pagar, kayu, kabel, lampu) memakai bahan prosedural.
Semua permukaan luar dibuat basah: lebih gelap dan lebih licin.
"""

import os

import bpy

AKAR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASET = os.path.join(AKAR, "aset")

NATRIUM = (1.0, 0.42, 0.08)  # warna lampu jalan natrium
HIJAU_PAGAR = (0.035, 0.22, 0.07)  # satu warna hijau untuk semua pagar Gang Melati

# Warna cat dinding rumah dan ruko (dikalikan dengan tekstur plester)
WARNA_DINDING = [
    (0.95, 0.90, 0.78),  # krem
    (0.80, 0.90, 0.95),  # biru muda
    (0.95, 0.80, 0.78),  # merah jambu pudar
    (0.85, 0.95, 0.80),  # hijau pupus
    (0.98, 0.96, 0.92),  # putih kusam
    (0.95, 0.88, 0.60),  # kuning gading
]


# --------------------------------------------------------------------------
# Alat bantu simpul


def _sok(socks, ident):
    for s in socks:
        if s.identifier == ident or s.name == ident:
            return s
    raise KeyError(ident)


class _Pohon:
    def __init__(self, bahan=None, pohon=None):
        self.nt = pohon if pohon is not None else bahan.node_tree
        self.nt.nodes.clear()

    def n(self, tipe, **atur):
        node = self.nt.nodes.new(tipe)
        for k, v in atur.items():
            setattr(node, k, v)
        return node

    def s(self, keluar, masuk):
        self.nt.links.new(keluar, masuk)

    def isi(self, node, ident, nilai):
        _sok(node.inputs, ident).default_value = nilai

    def math(self, op, a, b=None):
        m = self.n("ShaderNodeMath", operation=op)
        for i, x in enumerate((a, b)):
            if x is None:
                continue
            if isinstance(x, (int, float)):
                m.inputs[i].default_value = x
            else:
                self.s(x, m.inputs[i])
        return m.outputs[0]

    def campur(self, fak, a, b, warna=True):
        tipe = "Color" if warna else "Float"
        m = self.n("ShaderNodeMix", data_type="RGBA" if warna else "FLOAT")
        for ident, x in ((f"Factor_Float", fak), (f"A_{tipe}", a), (f"B_{tipe}", b)):
            sok = _sok(m.inputs, ident)
            if isinstance(x, (int, float, tuple)):
                sok.default_value = x if not (warna and isinstance(x, tuple) and len(x) == 3) else (*x, 1)
            else:
                self.s(x, sok)
        return _sok(m.outputs, f"Result_{tipe}")


def _bahan_baru(nama):
    b = bpy.data.materials.get(nama) or bpy.data.materials.new(nama)
    if b.node_tree is None:
        b.use_nodes = True
    return b, _Pohon(b)


def _bsdf(p):
    bsdf = p.n("ShaderNodeBsdfPrincipled")
    out = p.n("ShaderNodeOutputMaterial")
    p.s(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return bsdf, out


def _gambar(id_aset, peta, non_color):
    folder = os.path.join(ASET, "tekstur", id_aset)
    for ext in ("jpg", "png"):
        jalur = os.path.join(folder, f"{id_aset}_{peta}_2k.{ext}")
        if os.path.exists(jalur):
            break
    else:
        raise FileNotFoundError(f"{id_aset}_{peta} tidak ada di {folder}. Jalankan: python3 aset.py")
    img = bpy.data.images.load(jalur, check_existing=True)
    img.colorspace_settings.name = "Non-Color" if non_color else "sRGB"
    img.filepath = "//" + os.path.relpath(jalur, AKAR)
    return img


# --------------------------------------------------------------------------
# Jenis bahan


def polos(nama, warna, kasar=0.5, logam=0.0, emisi=None, kuat=0.0, alpha=1.0):
    b, p = _bahan_baru(nama)
    bsdf, _ = _bsdf(p)
    p.isi(bsdf, "Base Color", (*warna, 1))
    p.isi(bsdf, "Roughness", kasar)
    p.isi(bsdf, "Metallic", logam)
    p.isi(bsdf, "Alpha", alpha)
    if emisi:
        p.isi(bsdf, "Emission Color", (*emisi, 1))
        p.isi(bsdf, "Emission Strength", kuat)
    return b


def riak_hujan():
    """Grup shader: tinggi riak tetes hujan untuk permukaan genangan.

    Setiap sel Voronoi (sekitar 14 cm) memunculkan satu cincin yang mengembang
    dan memudar, berulang dengan fase acak per sel. Ditambah getaran halus
    dari noise 4D. Waktu berjalan lewat node Value yang dianimasikan linear.
    """
    g = bpy.data.node_groups.get("Riak_Hujan")
    if g:
        return g
    g = bpy.data.node_groups.new("Riak_Hujan", "ShaderNodeTree")
    g.interface.new_socket("Vector", in_out="INPUT", socket_type="NodeSocketVector")
    g.interface.new_socket("Tinggi", in_out="OUTPUT", socket_type="NodeSocketFloat")
    p = _Pohon(pohon=g)
    masuk = p.n("NodeGroupInput")
    keluar = p.n("NodeGroupOutput")
    waktu = p.n("ShaderNodeValue", name="Waktu")
    sok = waktu.outputs[0]
    sok.default_value = 0.0
    sok.keyframe_insert("default_value", frame=1)
    sok.default_value = 1.0
    sok.keyframe_insert("default_value", frame=25)  # 1 satuan per detik

    sel = p.n("ShaderNodeTexVoronoi", voronoi_dimensions="2D")
    p.isi(sel, "Scale", 7.0)
    p.s(masuk.outputs[0], sel.inputs["Vector"])
    acak = p.n("ShaderNodeSeparateColor")
    p.s(sel.outputs["Color"], acak.inputs[0])
    fase = p.math("FRACT", p.math("ADD", p.math("MULTIPLY", sok, 1.3), acak.outputs[0]))
    jari = p.math("MULTIPLY", fase, 0.45)
    jarak = p.math("ABSOLUTE", p.math("SUBTRACT", sel.outputs["Distance"], jari))
    cincin = p.math("MAXIMUM", p.math("SUBTRACT", 1.0, p.math("MULTIPLY", jarak, 12.0)), 0.0)
    cincin = p.math("MULTIPLY", cincin, p.math("SUBTRACT", 1.0, fase))

    getar = p.n("ShaderNodeTexNoise", noise_dimensions="4D")
    p.isi(getar, "Scale", 25.0)
    p.isi(getar, "Detail", 2.0)
    p.s(masuk.outputs[0], getar.inputs["Vector"])
    p.s(p.math("MULTIPLY", sok, 3.0), _sok(getar.inputs, "W"))
    tinggi = p.math("ADD", p.math("MULTIPLY", cincin, 0.7), p.math("MULTIPLY", getar.outputs["Fac"], 0.3))
    p.s(tinggi, keluar.inputs[0])

    from .geo import animasi_linear
    animasi_linear(g)
    return g


def _normal_riak(p, koor, kuat, normal_dasar=None):
    """Bump riak hujan; kuat boleh angka atau soket (topeng genangan)."""
    riak = p.n("ShaderNodeGroup", node_tree=riak_hujan())
    p.s(koor.outputs["Object"], riak.inputs[0])
    bump = p.n("ShaderNodeBump")
    p.isi(bump, "Distance", 0.003)
    if isinstance(kuat, float):
        p.isi(bump, "Strength", kuat)
    else:
        p.s(kuat, bump.inputs["Strength"])
    p.s(riak.outputs[0], bump.inputs["Height"])
    if normal_dasar is not None:
        p.s(normal_dasar, bump.inputs["Normal"])
    return bump.outputs["Normal"]


def genangan_air(nama):
    """Bahan piringan genangan: air di tengah, tepi lembut yang tembus ke aspal.

    Atribut mesh "tepi" (0 pusat, 1 tepi) diganggu noise supaya batasnya tidak
    beraturan, lalu dihaluskan. Bagian luar menjadi transparan.
    """
    b, p = _bahan_baru(nama)
    koor = p.n("ShaderNodeTexCoord")
    atr = p.n("ShaderNodeAttribute", attribute_name="tepi")
    noise = p.n("ShaderNodeTexNoise")
    p.isi(noise, "Scale", 2.5)
    p.isi(noise, "Detail", 4.0)
    p.s(koor.outputs["Object"], noise.inputs["Vector"])
    ganggu = p.math("MULTIPLY", p.math("SUBTRACT", noise.outputs["Fac"], 0.5), 0.7)
    e = p.math("ADD", atr.outputs["Fac"], ganggu)
    rentang = p.n("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
    p.isi(rentang, "From Min", 0.35)
    p.isi(rentang, "From Max", 0.9)
    p.isi(rentang, "To Min", 1.0)
    p.isi(rentang, "To Max", 0.0)
    p.s(e, rentang.inputs["Value"])

    bsdf = p.n("ShaderNodeBsdfPrincipled")
    p.isi(bsdf, "Base Color", (0.01, 0.01, 0.012, 1))
    p.isi(bsdf, "Roughness", 0.06)
    p.isi(bsdf, "IOR", 1.33)
    p.s(_normal_riak(p, koor, 0.35), bsdf.inputs["Normal"])
    tembus = p.n("ShaderNodeBsdfTransparent")
    campur = p.n("ShaderNodeMixShader")
    p.s(rentang.outputs["Result"], campur.inputs["Fac"])
    p.s(tembus.outputs[0], campur.inputs[1])
    p.s(bsdf.outputs[0], campur.inputs[2])
    out = p.n("ShaderNodeOutputMaterial")
    p.s(campur.outputs[0], out.inputs["Surface"])
    return b


def pbr(nama, id_aset, ukuran=2.0, warna=(1, 1, 1), basah=0.5, benjol=0.25,
        genangan=0.0, logam=False, licin=None):
    """Bahan bertekstur Poly Haven dengan proyeksi kotak (tanpa UV).

    ukuran   : lebar satu ulangan tekstur dalam meter
    basah    : 0 kering .. 1 sangat basah (lebih gelap)
    licin    : seberapa banyak kekasaran turun karena basah (bawaan = basah)
    genangan : 0 tanpa genangan .. 1 banyak genangan kecil (noise prosedural)
    """
    licin = basah if licin is None else licin
    b, p = _bahan_baru(nama)
    bsdf, _ = _bsdf(p)
    koor = p.n("ShaderNodeTexCoord")
    peta = p.n("ShaderNodeMapping")
    p.isi(peta, "Scale", (1 / ukuran,) * 3)
    p.s(koor.outputs["Object"], peta.inputs["Vector"])

    def tex(nama_peta, non_color):
        t = p.n("ShaderNodeTexImage", projection="BOX", projection_blend=0.2,
                image=_gambar(id_aset, nama_peta, non_color))
        p.s(peta.outputs["Vector"], t.inputs["Vector"])
        return t.outputs["Color"]

    gelap = 1 - 0.45 * basah
    warna_dasar = p.campur(1.0, tex("diff", False), tuple(w * gelap for w in warna))
    warna_dasar.node.blend_type = "MULTIPLY"
    kasar = p.math("MULTIPLY", tex("rough", True), 1 - 0.6 * licin)
    tinggi = tex("disp", True)
    kuat_benjol = benjol

    topeng = None
    if genangan > 0:
        # Genangan kecil-kecil (sekitar 1 m), tepi lembut lewat smoothstep
        noise = p.n("ShaderNodeTexNoise")
        p.isi(noise, "Scale", 1.1)
        p.isi(noise, "Detail", 6.0)
        p.isi(noise, "Roughness", 0.65)
        p.isi(noise, "Distortion", 0.4)
        p.s(koor.outputs["Object"], noise.inputs["Vector"])
        rentang = p.n("ShaderNodeMapRange", interpolation_type="SMOOTHSTEP")
        batas = 0.64 - 0.06 * genangan
        p.isi(rentang, "From Min", batas)
        p.isi(rentang, "From Max", batas + 0.07)
        p.s(noise.outputs["Fac"], rentang.inputs["Value"])
        topeng = rentang.outputs["Result"]
        warna_dasar = p.campur(topeng, warna_dasar, (0.012, 0.012, 0.014))
        kasar = p.campur(topeng, kasar, 0.05, warna=False)
        kuat_benjol = p.math("MULTIPLY", p.math("SUBTRACT", 1.0, topeng), benjol)

    p.s(warna_dasar, bsdf.inputs["Base Color"])
    p.s(kasar, bsdf.inputs["Roughness"])
    bump = p.n("ShaderNodeBump")
    p.isi(bump, "Distance", 0.02)
    if isinstance(kuat_benjol, float):
        p.isi(bump, "Strength", kuat_benjol)
    else:
        p.s(kuat_benjol, bump.inputs["Strength"])
    p.s(tinggi, bump.inputs["Height"])
    normal = bump.outputs["Normal"]
    if topeng is not None:
        normal = _normal_riak(p, koor, p.math("MULTIPLY", topeng, 0.35), normal)
    p.s(normal, bsdf.inputs["Normal"])
    if logam:
        p.s(tex("metal", True), bsdf.inputs["Metallic"])
    return b


def kayu(nama, warna_a, warna_b, basah=0.4):
    b, p = _bahan_baru(nama)
    bsdf, _ = _bsdf(p)
    koor = p.n("ShaderNodeTexCoord")
    peta = p.n("ShaderNodeMapping")
    p.isi(peta, "Scale", (2.0, 2.0, 30.0))
    p.s(koor.outputs["Object"], peta.inputs["Vector"])
    noise = p.n("ShaderNodeTexNoise")
    p.isi(noise, "Scale", 3.0)
    p.isi(noise, "Detail", 8.0)
    p.s(peta.outputs["Vector"], noise.inputs["Vector"])
    ramp = p.n("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*warna_a, 1)
    ramp.color_ramp.elements[1].color = (*warna_b, 1)
    p.s(noise.outputs["Fac"], ramp.inputs["Fac"])
    p.s(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    p.isi(bsdf, "Roughness", 0.7 - 0.4 * basah)
    return b


def garis(nama, warna_a, warna_b, lebar=0.5, sumbu="X", kasar=0.4):
    """Belang dua warna di sepanjang satu sumbu dunia (polisi tidur)."""
    b, p = _bahan_baru(nama)
    bsdf, _ = _bsdf(p)
    koor = p.n("ShaderNodeTexCoord")
    pisah = p.n("ShaderNodeSeparateXYZ")
    p.s(koor.outputs["Object"], pisah.inputs[0])
    t = p.math("FRACT", p.math("DIVIDE", pisah.outputs[sumbu], 2 * lebar))
    fak = p.math("GREATER_THAN", t, 0.5)
    p.s(p.campur(fak, warna_a, warna_b), bsdf.inputs["Base Color"])
    p.isi(bsdf, "Roughness", kasar)
    return b


def rolling_door(nama, warna=(0.28, 0.29, 0.3)):
    b, p = _bahan_baru(nama)
    bsdf, _ = _bsdf(p)
    koor = p.n("ShaderNodeTexCoord")
    gel = p.n("ShaderNodeTexWave", wave_type="BANDS", bands_direction="Z")
    p.isi(gel, "Scale", 6.0)
    p.s(koor.outputs["Object"], gel.inputs["Vector"])
    bump = p.n("ShaderNodeBump")
    p.isi(bump, "Strength", 0.6)
    p.s(gel.outputs["Fac"], bump.inputs["Height"])
    p.s(bump.outputs["Normal"], bsdf.inputs["Normal"])
    p.isi(bsdf, "Base Color", (*warna, 1))
    p.isi(bsdf, "Metallic", 0.7)
    p.isi(bsdf, "Roughness", 0.4)
    return b


def air(nama):
    """Air kali: gelap, licin, riak bergerak (noise 4D dianimasikan)."""
    b, p = _bahan_baru(nama)
    bsdf, _ = _bsdf(p)
    koor = p.n("ShaderNodeTexCoord")
    peta = p.n("ShaderNodeMapping")
    p.isi(peta, "Scale", (0.8, 0.25, 1.0))
    p.s(koor.outputs["Object"], peta.inputs["Vector"])
    noise = p.n("ShaderNodeTexNoise", noise_dimensions="4D", name="Riak")
    p.isi(noise, "Scale", 3.0)
    p.isi(noise, "Detail", 6.0)
    p.s(peta.outputs["Vector"], noise.inputs["Vector"])
    bump = p.n("ShaderNodeBump")
    p.isi(bump, "Strength", 0.08)
    p.s(noise.outputs["Fac"], bump.inputs["Height"])
    p.s(bump.outputs["Normal"], bsdf.inputs["Normal"])
    p.isi(bsdf, "Base Color", (0.015, 0.018, 0.012, 1))
    p.isi(bsdf, "Roughness", 0.04)
    p.isi(bsdf, "IOR", 1.33)
    w = _sok(noise.inputs, "W")
    w.default_value = 0.0
    w.keyframe_insert("default_value", frame=1)
    w.default_value = 1.5
    w.keyframe_insert("default_value", frame=25)
    from .geo import animasi_linear
    animasi_linear(b.node_tree)
    return b


def daun(nama):
    """Daun rimbun: warna hijau bervariasi dan benjolan helai daun (Voronoi)."""
    b, p = _bahan_baru(nama)
    bsdf, _ = _bsdf(p)
    koor = p.n("ShaderNodeTexCoord")
    warna = p.n("ShaderNodeTexNoise")
    p.isi(warna, "Scale", 4.0)
    p.s(koor.outputs["Object"], warna.inputs["Vector"])
    ramp = p.n("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.012, 0.04, 0.01, 1)
    ramp.color_ramp.elements[1].color = (0.05, 0.11, 0.025, 1)
    p.s(warna.outputs["Fac"], ramp.inputs["Fac"])
    p.s(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    helai = p.n("ShaderNodeTexVoronoi")
    p.isi(helai, "Scale", 28.0)
    p.s(koor.outputs["Object"], helai.inputs["Vector"])
    bump = p.n("ShaderNodeBump")
    p.isi(bump, "Strength", 0.9)
    p.isi(bump, "Distance", 0.03)
    p.s(helai.outputs["Distance"], bump.inputs["Height"])
    p.s(bump.outputs["Normal"], bsdf.inputs["Normal"])
    p.isi(bsdf, "Roughness", 0.35)
    p.isi(bsdf, "Subsurface Weight", 0.1)
    return b


def kabut(nama, kerapatan):
    b, p = _bahan_baru(nama)
    vol = p.n("ShaderNodeVolumePrincipled")
    out = p.n("ShaderNodeOutputMaterial")
    p.isi(vol, "Color", (0.7, 0.8, 1.0, 1))
    p.isi(vol, "Density", kerapatan)
    p.isi(vol, "Anisotropy", 0.55)
    p.s(vol.outputs["Volume"], out.inputs["Volume"])
    return b


# --------------------------------------------------------------------------


def siapkan():
    """Buat semua bahan kota sekali. Nama bahan dipakai sebagai kunci Kanvas."""
    # Basah (gelap) tetapi tetap kasar; yang licin hanya genangannya
    pbr("aspal_basah", "asphalt_01", ukuran=3.0, basah=0.8, licin=0.65, benjol=0.45, genangan=0.6)
    pbr("trotoar", "concrete_floor_02", ukuran=2.5, warna=(0.75, 0.75, 0.72), basah=0.7, genangan=0.3)
    pbr("paving_gang", "concrete_floor_02", ukuran=2.0, warna=(0.7, 0.7, 0.68), basah=0.8, licin=0.6, genangan=0.5)
    pbr("beton", "concrete_floor_02", ukuran=2.5, warna=(0.8, 0.8, 0.78), basah=0.5)
    pbr("beton_kali", "concrete_floor_02", ukuran=3.0, warna=(0.55, 0.6, 0.5), basah=0.9, benjol=0.5)
    pbr("bata", "red_bricks_04", ukuran=1.5, basah=0.6, benjol=0.5)
    pbr("genteng", "clay_roof_tiles_02", ukuran=2.0, basah=0.7, benjol=0.6)
    pbr("seng_karat", "rusty_metal_04", ukuran=2.0, basah=0.5, logam=True)
    for i, w in enumerate(WARNA_DINDING):
        pbr(f"plester_{i}", "plastered_wall", ukuran=2.5, warna=w, basah=0.4)

    rolling_door("rolling_door")
    rolling_door("rolling_door_biru", (0.12, 0.2, 0.3))
    polos("seng_galvanis", (0.45, 0.47, 0.48), kasar=0.3, logam=0.85)
    polos("pvc", (0.42, 0.43, 0.42), kasar=0.45)
    polos("plastik_ac", (0.62, 0.62, 0.58), kasar=0.4)
    polos("pipa_ac", (0.55, 0.55, 0.52), kasar=0.6)
    polos("kusen", (0.5, 0.5, 0.48), kasar=0.35, logam=0.6)
    polos("teralis_gelap", (0.03, 0.03, 0.03), kasar=0.35, logam=0.5)
    polos("teralis_putih", (0.55, 0.55, 0.52), kasar=0.35)
    polos("huruf_putih", (0.85, 0.85, 0.82), kasar=0.4)
    polos("huruf_gelap", (0.02, 0.02, 0.03), kasar=0.4)
    kayu("kayu", (0.10, 0.05, 0.02), (0.25, 0.14, 0.06))
    kayu("kayu_pintu", (0.08, 0.035, 0.015), (0.18, 0.09, 0.04), basah=0.1)
    garis("polisi_tidur", (0.9, 0.65, 0.02), (0.02, 0.02, 0.02), lebar=0.5, sumbu="X")
    air("air_kali")
    genangan_air("genangan")
    polos("tanah", (0.025, 0.022, 0.018), kasar=0.6)
    polos("cat_hijau", HIJAU_PAGAR, kasar=0.25, logam=0.3)
    polos("cat_hijau_tembok", HIJAU_PAGAR, kasar=0.45)
    polos("marka", (0.75, 0.75, 0.72), kasar=0.35)
    polos("logam_gelap", (0.08, 0.08, 0.085), kasar=0.35, logam=0.8)
    polos("tiang_beton", (0.45, 0.45, 0.43), kasar=0.6)
    polos("kabel", (0.01, 0.01, 0.01), kasar=0.4)
    daun("daun")
    polos("pot", (0.35, 0.12, 0.05), kasar=0.5)
    polos("plat_nomor", (0.85, 0.85, 0.8), kasar=0.3)
    polos("huruf_nomor", (0.02, 0.05, 0.2), kasar=0.4)
    polos("papan_gapura", (0.9, 0.88, 0.8), kasar=0.5)
    polos("huruf_gapura", HIJAU_PAGAR, kasar=0.4)

    polos("kaca_gelap", (0.01, 0.012, 0.015), kasar=0.05)
    polos("kaca_hangat", (0.12, 0.06, 0.02), kasar=0.2, emisi=(1.0, 0.42, 0.12), kuat=0.55)
    polos("kaca_dingin", (0.06, 0.08, 0.1), kasar=0.2, emisi=(0.75, 0.88, 1.0), kuat=0.6)
    polos("lampu_natrium", (0.1, 0.05, 0.0), emisi=NATRIUM, kuat=60.0)
    polos("lampu_teras", (0.1, 0.08, 0.05), emisi=(1.0, 0.7, 0.4), kuat=40.0)
    polos("ll_merah_nyala", (0.2, 0.0, 0.0), emisi=(1.0, 0.03, 0.02), kuat=2.5)
    # Lensa mati tetap sedikit berpendar supaya terbaca sebagai lampu
    polos("ll_merah_mati", (0.08, 0.01, 0.01), kasar=0.1, emisi=(1.0, 0.05, 0.03), kuat=0.08)
    polos("ll_kuning_mati", (0.08, 0.06, 0.01), kasar=0.1, emisi=(1.0, 0.6, 0.05), kuat=0.12)
    polos("ll_hijau_mati", (0.01, 0.06, 0.03), kasar=0.1, emisi=(0.1, 1.0, 0.55), kuat=0.08)
    polos("ll_papan", (0.015, 0.015, 0.015), kasar=0.5)
    polos("ll_bingkai", (0.02, 0.02, 0.02), kasar=0.4)
    polos("ll_kotak", (0.012, 0.012, 0.012), kasar=0.45)
    polos("logam_abu", (0.5, 0.51, 0.52), kasar=0.35, logam=0.25)  # besi bercat abu-abu
    polos("ll_hijau_nyala", (0.0, 0.2, 0.1), emisi=(0.1, 1.0, 0.55), kuat=2.5)
    papan = [(0.8, 0.1, 0.08), (0.1, 0.3, 0.8), (0.95, 0.75, 0.1), (0.1, 0.6, 0.3), (0.9, 0.9, 0.9)]
    for i, w in enumerate(papan):
        polos(f"papan_{i}", tuple(x * 0.5 for x in w), kasar=0.4)
        polos(f"papan_nyala_{i}", tuple(x * 0.3 for x in w), kasar=0.4, emisi=w, kuat=1.0)
    polos("hujan", (0.8, 0.82, 0.85), kasar=0.1, alpha=0.3)


def langit(scene, kuat=1.0, putar=0.0):
    """HDRI malam; belahan bawah dihitamkan supaya padang rumputnya tidak terlihat."""
    jalur = os.path.join(ASET, "hdri", "moonless_golf", "moonless_golf_2k.hdr")
    if not os.path.exists(jalur):
        raise FileNotFoundError(f"{jalur} tidak ada. Jalankan: python3 aset.py")
    dunia = bpy.data.worlds.new("Langit_Malam")
    p = _Pohon(dunia)
    koor = p.n("ShaderNodeTexCoord")
    peta = p.n("ShaderNodeMapping")
    p.isi(peta, "Rotation", (0, 0, putar))
    p.s(koor.outputs["Generated"], peta.inputs["Vector"])
    env = p.n("ShaderNodeTexEnvironment", image=bpy.data.images.load(jalur, check_existing=True))
    env.image.filepath = "//" + os.path.relpath(jalur, AKAR)
    p.s(peta.outputs["Vector"], env.inputs["Vector"])
    pisah = p.n("ShaderNodeSeparateXYZ")
    p.s(koor.outputs["Generated"], pisah.inputs[0])
    rentang = p.n("ShaderNodeMapRange")
    # Sekitar 2 sampai 13 derajat di atas cakrawala: HDRI memudar ke kabut rata.
    # Cakrawala HDRI berisi pepohonan lapangan golf yang tersorot lampu; tanpa
    # ini, mereka tampak sebagai gumpalan hijau-kuning di ujung setiap jalan.
    p.isi(rentang, "From Min", 0.03)
    p.isi(rentang, "From Max", 0.22)
    p.s(pisah.outputs["Z"], rentang.inputs["Value"])
    # Redam cahaya kota oranye dari HDRI: langit malam kebiruan
    biru = p.campur(1.0, env.outputs["Color"], (0.45, 0.65, 1.0))
    biru.node.blend_type = "MULTIPLY"
    warna = p.campur(rentang.outputs["Result"], (0.07, 0.085, 0.11), biru)
    latar = p.n("ShaderNodeBackground")
    p.isi(latar, "Strength", kuat)
    p.s(warna, latar.inputs["Color"])
    out = p.n("ShaderNodeOutputWorld")
    p.s(latar.outputs["Background"], out.inputs["Surface"])
    scene.world = dunia
    return dunia
