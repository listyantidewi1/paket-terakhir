"""Pemeriksa film otomatis: tembus, roda, lompatan gambar, dan lembar kontak.

Jalankan (setelah bangun.py dan gabung.py):
    blender --background --python periksa.py
    blender --background --python periksa.py -- --hanya tembus roda
    blender --background --python periksa.py -- --blend lain/film.blend --keluar lain/cek

Pemeriksaan:
  tembus   Setiap 2 frame: benda bergerak (motor, kurir, paket, kucing, anak,
           pintu) yang masuk ke benda lain, tubuh kurir yang keluar dari ponco,
           dan benda kecil yang menempel di benda bergerak tetapi tertinggal
           melayang saat benda itu bergerak (misalnya gagang pintu).
  roda     Setiap frame: jarak tempuh tiap roda dibandingkan dengan putarannya
           (jari-jari x sudut), dan geser menyamping.
  lompatan Setiap frame film_lebar.mp4 dibandingkan dengan frame sebelumnya;
           perubahan yang jauh di atas rata-rata shot ditandai.
  lembar   Lembar kontak per shot dari film_lebar.mp4: satu gambar tiap 12
           frame, dengan nomor frame.

Hasil: cek/laporan.md, cek/lembar_kontak/S0N.png, cek/periksa.json.
Tidak ada yang diubah atau disimpan ke film.blend.
"""

import json
import math
import os
import subprocess
import sys
import time

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree

AKAR = os.path.dirname(os.path.abspath(__file__))
if AKAR not in sys.path:
    sys.path.insert(0, AKAR)

from film import waktu  # noqa: E402

# ---------------------------------------------------------------- pengaturan

LANGKAH_TEMBUS = 2          # periksa tembus setiap 2 frame
BATAS_TEMBUS = 0.02         # m; masuk lebih dalam dari ini = temuan
BATAS_PONCO = 0.02          # m; tubuh keluar dari ponco lebih jauh dari ini = temuan
JARAK_TEPI_PONCO = 0.04     # m; tubuh yang lewat di tepi ponco (leher, ujung bawah) itu wajar
JARAK_SENTUH = 0.01         # m; dianggap menempel
UKURAN_KECIL = 0.6          # m; benda kecil yang bisa "menempel" (gagang, pelat)
BATAS_RODA = 0.02           # m per frame; selisih jarak tempuh dan putaran roda
BATAS_RODA_RELATIF = 0.10   # dan lebih dari 10 % jarak tempuh
BATAS_GESER = 0.02          # m per frame; roda bergeser menyamping
KALI_LOMPATAN = 3.0         # perubahan > 3x rata-rata shot
LANTAI_LOMPATAN = 1.5       # dan > 1,5 (skala 0-255), supaya shot diam tidak ramai
JARAK_LEMBAR = 12
KOLOM_LEMBAR = 6
LEBAR_GAMBAR_LEMBAR = 320

# Kelompok benda bergerak: nama kelompok -> fungsi pengenal nama objek.
# Benda dalam satu kelompok tidak diperiksa satu sama lain (mis. bagian motor),
# kecuali tubuh kurir terhadap ponco yang punya pemeriksaan sendiri.
KELOMPOK = {
    "motor": lambda n: (n.startswith("Motor") or n.startswith("HP_")),
    "kurir": lambda n: n in ("Kurir_Tubuh", "Kurir_Ponco", "Kurir_Helm"),
    "paket": lambda n: n.startswith("Paket_"),
    "kucing": lambda n: n == "Kucing_Tubuh",
    "anak": lambda n: n.startswith("Anak_"),
    "pintu": lambda n: n.startswith("Pintu_Tujuan"),
}
# Bukan benda padat: tidak bisa "ditembus"
BUKAN_PADAT = ("hujan", "kabut", "genangan", "air_kali", "Api_Lilin", "Cipratan", "Kamera")
# Bahan tubuh kurir yang harus tertutup ponco bila berada di bawahnya.
# Lengan berbahan ponco_kuning (lengan ponco) dilaporkan terpisah sebagai catatan.
BAHAN_TUBUH = ("kurir_baju", "kurir_celana", "kurir_kulit", "kurir_sarung_tangan", "kurir_bot", "kurir_rambut")


def argumen():
    a = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    hasil = {"hanya": None, "blend": os.path.join(AKAR, "film.blend"),
             "video": os.path.join(AKAR, "film_lebar.mp4"), "keluar": os.path.join(AKAR, "cek"),
             "frame": None, "dari_json": False, "banding": None}
    i = 0
    while i < len(a):
        if a[i] == "--hanya":
            hasil["hanya"] = []
            while i + 1 < len(a) and not a[i + 1].startswith("--"):
                i += 1
                hasil["hanya"].append(a[i])
        elif a[i] == "--dari-json":
            hasil["dari_json"] = True
        elif a[i] == "--frame":  # untuk menguji: --frame 400 470
            hasil["frame"] = (int(a[i + 1]), int(a[i + 2]))
            i += 2
        elif a[i] in ("--blend", "--video", "--keluar", "--banding"):
            hasil[a[i][2:]] = os.path.abspath(a[i + 1])
            i += 1
        i += 1
    return hasil


def shot_untuk(f):
    for s in waktu.SHOTS:
        if s.frame_mulai <= f <= s.frame_selesai:
            return s
    return None


def potongan_kamera(scene):
    """Frame pertama setiap potongan kamera (marker), termasuk S02b."""
    return sorted({m.frame for m in scene.timeline_markers} | {s.frame_mulai for s in waktu.SHOTS})


def segmen_kamera(scene):
    """(frame awal, frame akhir, nama marker) untuk setiap potongan kamera."""
    nama = {m.frame: m.name for m in scene.timeline_markers}
    awal = potongan_kamera(scene)
    akhir = awal[1:] + [waktu.FRAME_AKHIR + 1]
    return [(a, b - 1, nama.get(a, shot_untuk(a).nama)) for a, b in zip(awal, akhir)]


def log(*a):
    print("[periksa]", *a, flush=True)


# ---------------------------------------------------------------- geometri

def kelompok_dari(nama):
    for k, cocok in KELOMPOK.items():
        if cocok(nama):
            return k
    return None


def padat(o):
    return o.type == "MESH" and not any(b.lower() in o.name.lower() for b in BUKAN_PADAT)


class Geo:
    """Segitiga satu atau beberapa objek dalam koordinat dunia, siap untuk BVH."""

    def __init__(self, bagian):
        # bagian: daftar (nama objek, V (n,3), T (m,3), nama bahan per segitiga)
        self.nama = [b[0] for b in bagian]
        vs, ts, obj, bahan = [], [], [], []
        n = 0
        for i, (nama, V, T, B) in enumerate(bagian):
            vs.append(V)
            ts.append(T + n)
            obj.append(np.full(len(T), i))
            bahan.extend(B)
            n += len(V)
        self.V = np.concatenate(vs) if vs else np.zeros((0, 3))
        self.T = np.concatenate(ts) if ts else np.zeros((0, 3), dtype=np.int64)
        self.obj_tri = np.concatenate(obj) if obj else np.zeros(0, dtype=np.int64)
        self.bahan_tri = bahan
        # Arah normal: pulau tertutup dengan volume negatif dibalik, supaya normal selalu
        # menunjuk keluar. Pulau terbuka (bidang, kain tanpa tebal) ditandai.
        self.terbuka = np.zeros(len(self.T), dtype=bool)
        pulau_semua, n_pulau = [], 0
        for i, (nama, V, T, B) in enumerate(bagian):
            balik, buka, pt = arah_pulau(nama, V, T)
            pulau_semua.append(pt + n_pulau)
            n_pulau += len(V)
            m = self.obj_tri == i
            Ti = self.T[m]
            Ti[balik] = Ti[balik][:, ::-1]
            self.T[m] = Ti
            self.terbuka[np.flatnonzero(m)[buka]] = True
        # nomor pulau (bagian lepas) per segitiga, unik di seluruh Geo
        self.pulau_tri = np.concatenate(pulau_semua) if pulau_semua else np.zeros(0, dtype=np.int64)
        self._bvh = None
        self._tetangga = None
        self._bvh_obj = {}

    @property
    def bvh(self):
        if self._bvh is None:
            self._bvh = BVHTree.FromPolygons(self.V.tolist(), self.T.tolist(), all_triangles=True)
        return self._bvh

    def bvh_bagian(self, i):
        """BVH satu objek saja (untuk mengukur kedalaman terhadap objek itu).
        Mengembalikan (bvh, penanda terbuka per segitiga BVH itu)."""
        if i not in self._bvh_obj:
            m = self.obj_tri == i
            self._bvh_obj[i] = (BVHTree.FromPolygons(self.V.tolist(), self.T[m].tolist(), all_triangles=True),
                                self.terbuka[m])
        return self._bvh_obj[i]

    @property
    def tetangga(self):
        """Tetangga tiap titik (CSR): ptr, idx."""
        if self._tetangga is None:
            T = self.T
            e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
            e = np.concatenate([e, e[:, ::-1]])
            e = np.unique(e, axis=0)
            ptr = np.searchsorted(e[:, 0], np.arange(len(self.V) + 1))
            self._tetangga = (ptr, e[:, 1])
        return self._tetangga

    def tepi(self, maska_tri):
        """Titik di tepi terbuka (rusuk milik satu segitiga saja)."""
        T = self.T[maska_tri]
        e = np.sort(np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]]), axis=1)
        u, c = np.unique(e, axis=0, return_counts=True)
        return np.unique(u[c == 1].ravel())


_ARAH = {}


def arah_pulau(nama, V, T):
    """Per segitiga: perlu dibalik? dan termasuk pulau terbuka? (disimpan per objek)."""
    kunci = (nama, len(V), len(T))
    if kunci in _ARAH:
        return _ARAH[kunci]
    n = len(V)
    lab = np.arange(n)
    e = np.concatenate([T[:, [0, 1]], T[:, [1, 2]], T[:, [2, 0]]])
    for _ in range(200):
        m = np.minimum(lab[e[:, 0]], lab[e[:, 1]])
        baru = lab.copy()
        np.minimum.at(baru, e[:, 0], m)
        np.minimum.at(baru, e[:, 1], m)
        baru = baru[baru]
        if np.array_equal(baru, lab):
            break
        lab = baru
    pulau_tri = lab[T[:, 0]]
    # rusuk tepi: dipakai satu segitiga saja
    es = np.sort(e, axis=1)
    u, inv, c = np.unique(es, axis=0, return_inverse=True, return_counts=True)
    tepi_tri = (c[inv.ravel()] == 1).reshape(3, -1).any(axis=0)
    buka_pulau = np.unique(pulau_tri[tepi_tri])
    a, b, cc = V[T[:, 0]], V[T[:, 1]], V[T[:, 2]]
    vol = np.einsum("ij,ij->i", a, np.cross(b, cc)) / 6.0
    ids, inv2 = np.unique(pulau_tri, return_inverse=True)
    vol_pulau = np.zeros(len(ids))
    np.add.at(vol_pulau, inv2.ravel(), vol)
    balik = (vol_pulau < 0)[inv2.ravel()] & ~np.isin(pulau_tri, buka_pulau)
    buka = np.isin(pulau_tri, buka_pulau)
    _ARAH[kunci] = (balik, buka, pulau_tri)
    return _ARAH[kunci]


def segitiga_dunia(o, dg, tanpa=()):
    """Mesh hasil evaluasi (modifier, armature) dalam koordinat dunia."""
    mati = [m for m in o.modifiers if m.type in tanpa and m.show_viewport]
    for m in mati:
        m.show_viewport = False
    if mati:
        dg.update()
    oe = o.evaluated_get(dg)
    me = oe.to_mesh()
    me.calc_loop_triangles()
    n = len(me.vertices)
    V = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get("co", V)
    V = V.reshape(n, 3)
    M = np.array(oe.matrix_world)
    V = V @ M[:3, :3].T + M[:3, 3]
    nt = len(me.loop_triangles)
    T = np.empty(nt * 3, dtype=np.int64)
    me.loop_triangles.foreach_get("vertices", T)
    T = T.reshape(nt, 3)
    if np.linalg.det(M[:3, :3]) < 0:
        T = T[:, ::-1]
    mi = np.empty(nt, dtype=np.int64)
    me.loop_triangles.foreach_get("material_index", mi)
    nama_bahan = [s.material.name if s.material else "" for s in o.material_slots] or [""]
    B = [nama_bahan[min(i, len(nama_bahan) - 1)] for i in mi]
    oe.to_mesh_clear()
    for m in mati:
        m.show_viewport = True
    if mati:
        dg.update()
    return o.name, V, T, B


MAKS_TERBUKA = 0.10  # m; di permukaan terbuka (tanpa tebal) sisi dalam tidak pasti, jadi dibatasi


def kedalaman(A, seed, B, arah=-1, tepi_kd=None, maks=0.5, batas_kunjung=6000):
    """Seberapa jauh titik-titik A masuk ke B.

    Mulai dari titik A di segitiga yang berpotongan, lalu menjalar ke tetangga
    selama titik masih berada di sisi "dalam" B (arah=-1: di belakang normal
    permukaan B; arah=+1: di depan normal, dipakai untuk 'keluar dari ponco').
    Mengembalikan (kedalaman, titik terdalam).
    """
    B_bvh, B_buka = B if isinstance(B, tuple) else (B, None)
    ptr, idx = A.tetangga
    V = A.V
    dikunjungi = set()
    tumpuk = list(seed)
    terdalam, titik = 0.0, None
    while tumpuk and len(dikunjungi) < batas_kunjung:
        v = tumpuk.pop()
        if v in dikunjungi:
            continue
        dikunjungi.add(v)
        p = Vector(V[v])
        loc, nor, ti, d = B_bvh.find_nearest(p, maks)
        if loc is None:
            continue
        if B_buka is not None and B_buka[ti] and d > MAKS_TERBUKA:
            continue
        if (p - loc).dot(nor) * (-arah) >= -1e-5:  # di sisi luar
            continue
        if tepi_kd is not None:
            _, _, dt = tepi_kd.find(loc)
            if dt is not None and dt < JARAK_TEPI_PONCO:
                continue
        if d > terdalam:
            terdalam, titik = d, V[v].copy()
        tumpuk.extend(int(x) for x in idx[ptr[v]:ptr[v + 1]] if int(x) not in dikunjungi)
    return terdalam, titik


def sampel_permukaan(V, T, sekitar=None, jarak=0.03, maks=4000):
    """Titik-titik sampel di permukaan segitiga T (grid barisentris), dibatasi kotak 'sekitar'."""
    titik = []
    for a, b, c in V[T]:
        n = int(min(max(np.linalg.norm(b - a), np.linalg.norm(c - a), np.linalg.norm(c - b)) / jarak, 60)) + 1
        i, j = np.meshgrid(np.arange(n + 1), np.arange(n + 1))
        m = (i + j) <= n
        u, v = i[m] / n, j[m] / n
        titik.append(a + np.outer(u, b - a) + np.outer(v, c - a))
    P = np.concatenate(titik) if titik else np.zeros((0, 3))
    if sekitar is not None and len(P):
        lo, hi = sekitar
        P = P[np.all((P >= lo) & (P <= hi), axis=1)]
    if len(P) > maks:
        P = P[np.linspace(0, len(P) - 1, maks).astype(int)]
    return P


def kedalaman_sampel(P, B):
    """Kedalaman terbesar titik-titik P di dalam B (bvh, terbuka)."""
    B_bvh, B_buka = B
    terdalam, titik = 0.0, None
    for p in P:
        p = Vector(p)
        loc, nor, ti, d = B_bvh.find_nearest(p, 0.5)
        if loc is None or (p - loc).dot(nor) >= -1e-5:
            continue
        if B_buka[ti] and d > MAKS_TERBUKA:
            continue
        if d > terdalam:
            terdalam, titik = d, np.array(p)
    return terdalam, titik


def kotak(V, pad):
    return V.min(axis=0) - pad, V.max(axis=0) + pad


def terlihat(scene, dg, p, objek):
    """Apakah titik p ada di dalam bingkai kamera aktif dan tidak tertutup benda lain."""
    from bpy_extras.object_utils import world_to_camera_view
    cam = scene.camera
    if cam is None or p is None:
        return False
    p = Vector(p)
    c = world_to_camera_view(scene, cam, p)
    if not (0 <= c.x <= 1 and 0 <= c.y <= 1 and c.z > 0):
        return False
    asal = cam.matrix_world.translation
    arah = p - asal
    jarak = arah.length
    hit, loc, _, _, o, _ = scene.ray_cast(dg, asal, arah.normalized(), distance=jarak + 0.01)
    if not hit:
        return True
    return o.name in objek or (loc - asal).length >= jarak - 0.06


# ---------------------------------------------------------------- tembus

def siapkan_adegan(scene):
    """Matikan yang tidak perlu (hujan, bulu, partikel) supaya evaluasi cepat. Tidak disimpan."""
    for o in scene.objects:
        if o.type in ("CURVES", "FONT", "CURVE") or "hujan" in o.name.lower() or "kabut" in o.name.lower():
            o.hide_viewport = True
        for m in o.modifiers:
            if m.type in ("PARTICLE_SYSTEM", "CLOTH"):
                m.show_viewport = False


def benda_bergerak(scene):
    hasil = {}
    for o in scene.objects:
        k = kelompok_dari(o.name)
        if k and padat(o) and not o.hide_viewport:
            hasil.setdefault(k, []).append(o)
    return hasil


def benda_diam(scene, dg):
    bagian = []
    for o in scene.objects:
        if kelompok_dari(o.name) or not padat(o) or o.hide_viewport or o.hide_render:
            continue
        if o.animation_data and o.animation_data.action:
            log(f"PERINGATAN: {o.name} beranimasi tetapi bukan benda bergerak yang diperiksa")
        g = segitiga_dunia(o, dg)
        if len(g[2]):
            bagian.append(g)
    return Geo(bagian)


def periksa_tembus(scene, frames):
    dg = bpy.context.evaluated_depsgraph_get()
    siapkan_adegan(scene)
    dg.update()
    statis = benda_diam(scene, dg)
    log(f"benda diam: {len(statis.nama)} objek, {len(statis.T)} segitiga")
    gerak = benda_bergerak(scene)
    log("benda bergerak: " + ", ".join(f"{k} ({len(v)})" for k, v in gerak.items()))
    ponco = bpy.data.objects.get("Kurir_Ponco")

    temuan = []
    lampiran = {}  # (objek bergerak, objek statis, pulau) -> keadaan menempel
    mulai = time.time()
    for n, f in enumerate(frames):
        scene.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        geo = {}
        for k, objs in gerak.items():
            bagian = [segitiga_dunia(o, dg) for o in objs if not o.hide_render]
            bagian = [b for b in bagian if len(b[2])]
            if bagian:
                geo[k] = Geo(bagian)

        def catat(jenis, A, ia, B_nama, d, titik, keterangan=""):
            if d < (BATAS_PONCO if jenis == "ponco" else BATAS_TEMBUS):
                return
            objek = {A.nama[ia], B_nama}
            temuan.append({"jenis": jenis, "frame": f, "a": A.nama[ia], "b": B_nama,
                           "cm": round(float(d) * 100, 1), "titik": [round(float(x), 2) for x in titik],
                           "terlihat": terlihat(scene, dg, titik, objek), "ket": keterangan})

        # 1. benda bergerak vs benda diam dan vs kelompok bergerak lain
        nama_k = list(geo)
        lawan = [(k, statis) for k in nama_k] + [(a, geo[b]) for i, a in enumerate(nama_k) for b in nama_k[i + 1:]]
        for k, B in lawan:
            A = geo[k]
            pasangan = A.bvh.overlap(B.bvh)
            if not pasangan:
                continue
            per = {}
            for ta, tb in pasangan:
                per.setdefault((int(A.obj_tri[ta]), int(B.obj_tri[tb])), ([], []))
                per[(int(A.obj_tri[ta]), int(B.obj_tri[tb]))][0].append(ta)
                per[(int(A.obj_tri[ta]), int(B.obj_tri[tb]))][1].append(tb)
            for (ia, ib), (tas, tbs) in per.items():
                da, pa = kedalaman(A, np.unique(A.T[tas]).tolist(), B.bvh_bagian(ib))
                db, pb = kedalaman(B, np.unique(B.T[tbs]).tolist(), A.bvh_bagian(ia))
                # Lempeng tipis (daun pintu) yang membelah benda lain tidak punya titik sudut
                # di dalamnya, jadi permukaan di sekitar perpotongan juga diambil sampelnya.
                VA, VB = A.V[np.unique(A.T[tas])], B.V[np.unique(B.T[tbs])]
                sa, qa = kedalaman_sampel(sampel_permukaan(A.V, A.T[tas], kotak(VB, 0.3)), B.bvh_bagian(ib))
                sb, qb = kedalaman_sampel(sampel_permukaan(B.V, B.T[tbs], kotak(VA, 0.3)), A.bvh_bagian(ia))
                d, p = max([(da, pa), (db, pb), (sa, qa), (sb, qb)], key=lambda x: x[0])
                if p is None:
                    p = A.V[A.T[tas[0]]].mean(axis=0)
                catat("tembus", A, ia, B.nama[ib], d, p)

        # 2. tubuh kurir keluar dari ponco
        if "kurir" in geo and ponco is not None and not ponco.hide_render:
            tubuh_g = geo["kurir"]
            it = tubuh_g.nama.index("Kurir_Tubuh") if "Kurir_Tubuh" in tubuh_g.nama else None
            if it is not None:
                P = Geo([segitiga_dunia(ponco, dg, tanpa=("SOLIDIFY",))])
                tepi = P.tepi(np.ones(len(P.T), dtype=bool))
                kd = KDTree(len(tepi))
                for j, v in enumerate(tepi):
                    kd.insert(P.V[v], j)
                kd.balance()
                T = Geo([(n_, V_, T_, B_) for (n_, V_, T_, B_) in [segitiga_dunia(bpy.data.objects["Kurir_Tubuh"], dg)]])
                # arah normal ponco: sebagian besar badan harus berada "di dalam"
                baju = np.unique(T.T[[i for i, b in enumerate(T.bahan_tri) if b == "kurir_baju"]])
                tanda = []
                for v in baju[:: max(1, len(baju) // 150)]:
                    loc, nor, _, _ = P.bvh.find_nearest(Vector(T.V[v]), 0.5)
                    if loc is not None:
                        tanda.append((Vector(T.V[v]) - loc).dot(nor))
                balik = np.median(tanda) > 0 if tanda else False
                arah = -1 if balik else 1  # sisi luar ponco
                pasangan = T.bvh.overlap(P.bvh)
                per_bahan = {}
                for ta, _ in pasangan:
                    per_bahan.setdefault(T.bahan_tri[ta], []).append(ta)
                for bhn, tas in per_bahan.items():
                    d, p = kedalaman(T, np.unique(T.T[tas]).tolist(), P.bvh, arah=arah, tepi_kd=kd)
                    if p is None:
                        continue
                    jenis = "ponco" if bhn in BAHAN_TUBUH else "lengan_ponco"
                    catat(jenis, T, 0, "Kurir_Ponco", d, p, keterangan=bhn)

        # 3. benda kecil menempel di benda bergerak lalu tertinggal melayang
        for k, A in geo.items():
            if k == "kurir":
                continue
            cek_lampiran(scene, dg, f, k, A, statis, lampiran, temuan, cari=(n % 4 == 0))

        if n % 50 == 0:
            log(f"tembus frame {f} ({n + 1}/{len(frames)}), {len(temuan)} catatan, "
                f"{time.time() - mulai:.0f} detik")
    return temuan


def pulau_kecil(statis):
    """Pulau benda diam yang kecil (gagang, pelat, pot): {pulau: (objek, indeks titik, kotak)}."""
    if hasattr(statis, "_kecil"):
        return statis._kecil
    hasil = {}
    urut = np.argsort(statis.pulau_tri, kind="stable")
    batas = np.flatnonzero(np.diff(statis.pulau_tri[urut])) + 1
    for kel in np.split(urut, batas):
        titik = np.unique(statis.T[kel])
        V = statis.V[titik]
        if np.ptp(V, axis=0).max() <= UKURAN_KECIL:
            hasil[int(statis.pulau_tri[kel[0]])] = (int(statis.obj_tri[kel[0]]), titik, V.min(axis=0), V.max(axis=0))
    statis._kecil = hasil
    log(f"pulau kecil benda diam: {len(hasil)}")
    return hasil


def cek_lampiran(scene, dg, f, kel, A, statis, lampiran, temuan, cari=True):
    """Benda kecil diam yang menempel di benda bergerak A. Bila A menjauh dan benda
    itu tidak lagi menyentuh apa pun, berarti benda itu seharusnya ikut bergerak."""
    kecil = pulau_kecil(statis)
    if cari:
        lo, hi = kotak(A.V, JARAK_SENTUH)
        for pid, (ib, titik, a, b) in kecil.items():
            if (kel, pid) in lampiran or np.any(b < lo) or np.any(a > hi):
                continue
            d = min(A.bvh.find_nearest(Vector(v))[3] for v in statis.V[titik])
            if d <= JARAK_SENTUH:
                lampiran[(kel, pid)] = {"sejak": f}
    for (k, pid), info in lampiran.items():
        if k != kel or info.get("selesai"):
            continue
        ib, titik, _, _ = kecil[pid]
        V = statis.V[titik]
        dA = min(A.bvh.find_nearest(Vector(v))[3] for v in V)
        if dA <= JARAK_SENTUH * 2:
            continue
        disangga = any(statis.pulau_tri[ti] != pid
                       for v in V for _, _, ti, _ in statis.bvh.find_nearest_range(Vector(v), JARAK_SENTUH))
        if disangga:
            info["selesai"] = True  # bersandar di benda lain: memang bukan bagian benda bergerak
            continue
        pusat = V.mean(axis=0)
        temuan.append({"jenis": "melayang", "frame": f, "a": statis.nama[ib], "b": kel,
                       "cm": round(dA * 100, 1), "titik": [round(float(x), 2) for x in pusat],
                       "terlihat": terlihat(scene, dg, pusat, {statis.nama[ib]}),
                       "ket": f"menempel di {kel} sejak frame {info['sejak']}, kini terpisah {dA * 100:.0f} cm"})


# ---------------------------------------------------------------- roda

def periksa_roda(scene, frames):
    motor = bpy.data.objects.get("Motor")
    roda = [bpy.data.objects.get(n) for n in ("Motor_Roda_Depan", "Motor_Roda_Belakang")]
    if motor is None or None in roda:
        return [], {}
    jari = {}
    for r in roda:  # jari-jari dari ban sebenarnya, bukan dari angka di kode
        ban = [c for c in r.children if "karet" in c.name]
        V = np.array([v.co[:] for v in ban[0].data.vertices]) if ban else np.zeros((1, 3))
        M = np.array(ban[0].matrix_local) if ban else np.eye(4)
        V = V @ M[:3, :3].T + M[:3, 3]
        jari[r.name] = float(np.sqrt(V[:, 1] ** 2 + V[:, 2] ** 2).max()) if ban else float(motor.get("jari_roda", 0.29))
    potong = set(potongan_kamera(scene))
    data, temuan = [], []
    sebelum = None
    for f in frames:
        scene.frame_set(f)
        keadaan = {}
        for r in roda:
            Mp = r.parent.matrix_world
            lokal = Mp.inverted() @ r.matrix_world
            sudut = math.atan2(lokal[2][1], lokal[1][1])
            kanan = Vector((Mp[0][0], Mp[1][0], Mp[2][0])).normalized()  # sumbu X induk = sumbu as roda
            maju = Vector((Mp[0][1], Mp[1][1], Mp[2][1])).normalized()   # sumbu Y induk = arah gelinding
            keadaan[r.name] = (r.matrix_world.translation.copy(), sudut, maju, kanan)
        if sebelum is not None and f - sebelum[0] == 1:
            for r in roda:
                p0, s0, _, _ = sebelum[1][r.name]
                p1, s1, maju, kanan = keadaan[r.name]
                dp = p1 - p0
                # Geser samping = searah as roda. Naik-turun (polisi tidur) tetap dihitung
                # sebagai jalan menggelinding, bukan geser.
                samping = abs(dp.dot(kanan))
                jalan = math.copysign(math.sqrt(max(dp.length_squared - samping ** 2, 0.0)), dp.dot(maju))
                ds = (s1 - s0 + math.pi) % (2 * math.pi) - math.pi
                putar = -ds * jari[r.name]
                selisih = jalan - putar
                baris = {"frame": f, "roda": r.name, "jalan": jalan, "putar": putar,
                         "selisih": selisih, "samping": samping}
                data.append(baris)
                if f in potong:
                    continue
                if (abs(selisih) > BATAS_RODA and abs(selisih) > BATAS_RODA_RELATIF * abs(jalan)) \
                        or samping > BATAS_GESER:
                    temuan.append(baris)
        sebelum = (f, keadaan)
    return temuan, {"jari": jari, "data": data}


# ---------------------------------------------------------------- rana (motion blur)

BATAS_RANA_PX = 8.0       # geser di layar selama rana terbuka, piksel 1920x1080
KALI_RANA = 3.0           # dan lebih dari 3x geser biasa di potongan kamera itu


def kamera_frame(scene, f):
    """Kamera yang dipakai untuk merender frame f (marker terakhir <= f)."""
    tanda = [m for m in scene.timeline_markers if m.frame <= f and m.camera]
    return max(tanda, key=lambda m: m.frame).camera if tanda else scene.camera


def jendela_rana(scene, f):
    """Waktu buka, tengah, dan tutup rana untuk frame f, seperti Cycles:
    CENTER = f -/+ setengah rana, START = mulai di f, END = berakhir di f."""
    scene.frame_set(f)
    r = scene.render
    h = r.motion_blur_shutter / 2
    pos = r.motion_blur_position
    a = {"START": f, "END": f - 2 * h}.get(pos, f - h)
    return pos, (a, a + h, a + 2 * h)


def set_waktu(scene, t):
    i = math.floor(t + 1e-9)
    scene.frame_set(i, subframe=t - i)


SAMPEL_MESH = 20  # tubuh yang dibengkokkan rangka: setiap titik ke-20 mesh hasil evaluasi


def titik_gerak(scene):
    """Titik yang mewakili benda bergerak: sudut kotak batas objek bergerak, titik
    mesh hasil evaluasi untuk tubuh yang dibengkokkan (kurir, kucing, anak),
    posisi api dan lampu lilin, serta pangkal/ujung tulang armature.
    Mengembalikan (nama per titik, array)."""
    nama, P = [], []
    dg = bpy.context.evaluated_depsgraph_get()
    for o in scene.objects:
        if o.type in ("MESH", "LIGHT") and o.name.startswith(("Api_Lilin", "Lampu_Lilin")):
            nama.append(o.name)
            P.append(o.matrix_world.translation.copy())
            continue
        if o.type == "MESH" and kelompok_dari(o.name) in ("kurir", "kucing", "anak"):
            oe = o.evaluated_get(dg)
            me = oe.to_mesh()
            M = oe.matrix_world
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get("co", co)
            Mn = np.array(M)
            for v in co.reshape(-1, 3)[::SAMPEL_MESH] @ Mn[:3, :3].T + Mn[:3, 3]:
                nama.append(o.name)
                P.append(Vector(v))
            oe.to_mesh_clear()
            continue
        if o.type == "ARMATURE" and o.pose:
            M = o.matrix_world
            for b in o.pose.bones:
                for v in (b.head, b.tail):
                    nama.append(o.name)
                    P.append(M @ v)
        elif kelompok_dari(o.name) and o.type == "MESH" and not o.hide_render:
            M = o.matrix_world
            if "_Roda_" in o.name:  # roda berputar: blur putaran itu wajar, cukup as rodanya
                nama.append(o.name)
                P.append(M.translation.copy())
                continue
            for c in o.bound_box:
                nama.append(o.name)
                P.append(M @ Vector(c))
    return nama, np.array([p[:] for p in P])


def proyeksi(scene, cam, P):
    from bpy_extras.object_utils import world_to_camera_view
    W, H = 1920, 1080
    hasil = np.array([world_to_camera_view(scene, cam, Vector(p))[:] for p in P])
    return hasil[:, 0] * W, hasil[:, 1] * H, hasil[:, 2]


def sampel_rana(scene, frames):
    """Per frame: kamera, posisi rana, dan keadaan kamera serta titik bergerak di
    tiga waktu rana. Dipakai untuk mengukur geser dan membandingkan dua versi."""
    siapkan_adegan(scene)
    hasil = []
    for n, f in enumerate(frames):
        cam = kamera_frame(scene, f)
        pos, ts = jendela_rana(scene, f)
        keadaan = []
        for t in ts:
            set_waktu(scene, t)
            nama, P = titik_gerak(scene)
            # titik latar: 9 titik 10 m di depan kamera pada waktu tengah (diisi nanti)
            keadaan.append({"t": t, "cam": np.array(cam.matrix_world), "lensa": cam.data.lens,
                            "nama": nama, "P": P})
        hasil.append({"frame": f, "kamera": cam.name, "posisi": pos, "keadaan": keadaan})
        if n % 200 == 0:
            log(f"rana frame {f} ({n + 1}/{len(frames)})")
    return hasil


def ukur_geser(scene, sampel):
    """Geser di layar (piksel) selama rana: subjek (titik bergerak yang tampak) dan
    latar (titik diam 10 m di depan kamera, jadi hanya gerak kamera)."""
    from mathutils import Matrix
    hasil = []
    for s_ in sampel:
        f = s_["frame"]
        cam = bpy.data.objects[s_["kamera"]]
        k0, km, k1 = s_["keadaan"]
        Mm = Matrix(km["cam"].tolist())
        latar = np.array([(Mm @ Vector((x, y, -10.0)))[:] for x in (-3, 0, 3) for y in (-2, 0, 2)])
        layar = []
        for k in (k0, km, k1):
            cam.matrix_world = Matrix(k["cam"].tolist())
            cam.data.lens = k["lensa"]
            xs, ys, zs = proyeksi(scene, cam, k["P"]) if len(k["P"]) else (np.zeros(0),) * 3
            lx, ly, _ = proyeksi(scene, cam, latar)
            layar.append((xs, ys, zs, lx, ly))
        (x0, y0, z0, lx0, ly0), (xm, ym, zm, _, _), (x1, y1, z1, lx1, ly1) = layar
        geser_latar = float(np.hypot(lx1 - lx0, ly1 - ly0).max())
        geser_subjek, siapa = 0.0, ""
        if len(xm) == len(x0) == len(x1) and len(xm):
            tampak = (zm > 0) & (xm >= 0) & (xm <= 1920) & (ym >= 0) & (ym <= 1080) & (z0 > 0) & (z1 > 0)
            jalan = np.hypot(xm - x0, ym - y0) + np.hypot(x1 - xm, y1 - ym)
            if tampak.any():
                i = int(np.argmax(np.where(tampak, jalan, -1)))
                geser_subjek, siapa = float(jalan[i]), km["nama"][i]
        # benda yang berpindah jauh (> 1 m) di dunia selama rana: teleport antar shot
        loncat = sorted({km["nama"][i] for i in range(min(len(k0["P"]), len(k1["P"])))
                         if np.linalg.norm(k1["P"][i] - k0["P"][i]) > 1.0}) if len(k0["P"]) == len(k1["P"]) else []
        hasil.append({"frame": f, "kamera": s_["kamera"], "posisi": s_["posisi"],
                      "waktu": [round(k["t"], 3) for k in s_["keadaan"]],
                      "subjek": round(geser_subjek, 1), "siapa": siapa, "latar": round(geser_latar, 1),
                      "loncat": loncat})
    return hasil


def periksa_rana(scene, frames):
    sampel = sampel_rana(scene, frames)
    ukur = ukur_geser(scene, sampel)
    # geser biasa per potongan kamera: median frame-frame di potongan itu
    biasa = {}
    for a, b, nama in segmen_kamera(scene):
        isi = [u for u in ukur if a <= u["frame"] <= b]
        if isi:
            biasa[nama] = (float(np.median([u["subjek"] for u in isi])), float(np.median([u["latar"] for u in isi])))
    nama_seg = {f: nm for a, b, nm in segmen_kamera(scene) for f in range(a, b + 1)}
    temuan = []
    for u in ukur:
        # pembanding: median frame tetangga (6 ke kiri dan kanan) di potongan yang sama,
        # jadi gerakan wajar yang berlangsung lama (kurir berjalan) tidak ditandai
        seg = nama_seg.get(u["frame"])
        tetangga = [v for v in ukur if 0 < abs(v["frame"] - u["frame"]) <= 6 and nama_seg.get(v["frame"]) == seg]
        bs = float(np.median([v["subjek"] for v in tetangga])) if tetangga else 0.0
        bl = float(np.median([v["latar"] for v in tetangga])) if tetangga else 0.0
        alasan = []
        if u["subjek"] > BATAS_RANA_PX and u["subjek"] > KALI_RANA * max(bs, 1.0):
            alasan.append(f"subjek {u['subjek']:.0f} px ({u['siapa']}; frame tetangga {bs:.1f} px)")
        if u["latar"] > BATAS_RANA_PX and u["latar"] > KALI_RANA * max(bl, 1.0):
            alasan.append(f"kamera {u['latar']:.0f} px (frame tetangga {bl:.1f} px)")
        if u["loncat"]:
            alasan.append("berpindah > 1 m selama rana: " + ", ".join(u["loncat"][:4]) +
                          (f" dan {len(u['loncat']) - 4} lainnya" if len(u["loncat"]) > 4 else ""))
        if alasan:
            temuan.append(dict(u, alasan="; ".join(alasan), segmen=nama_seg.get(u["frame"])))
    return temuan, ukur, biasa, sampel


def _per_objek(k):
    hasil = {}
    for i, n in enumerate(k["nama"]):
        hasil.setdefault(n, []).append(i)
    return {n: k["P"][ix] for n, ix in hasil.items()}


def banding_rana(sampel_a, sampel_b, tol=1e-4):
    """Frame yang keadaan kamera atau benda bergeraknya di dalam rana berbeda antara dua versi."""
    beda = []
    for a, b in zip(sampel_a, sampel_b):
        assert a["frame"] == b["frame"]
        alasan = []
        if a["kamera"] != b["kamera"]:
            alasan.append("kamera")
        if a["posisi"] != b["posisi"]:
            alasan.append(f"posisi rana {a['posisi']} -> {b['posisi']}")
        for ka, kb in zip(a["keadaan"], b["keadaan"]):
            if abs(ka["t"] - kb["t"]) > 1e-6:
                continue  # sudah tercatat lewat posisi rana
            if np.abs(ka["cam"] - kb["cam"]).max() > tol or abs(ka["lensa"] - kb["lensa"]) > tol:
                alasan.append("gerak kamera")
                break
            # dibandingkan per objek yang ada di kedua versi (tulang rangka baru tidak
            # ada di versi lama; pengaruhnya terlihat lewat titik mesh)
            pa, pb_ = _per_objek(ka), _per_objek(kb)
            beda_obj = [n for n in pa.keys() & pb_.keys()
                        if pa[n].shape != pb_[n].shape or np.abs(pa[n] - pb_[n]).max() > tol]
            if beda_obj:
                alasan.append("gerak benda: " + ", ".join(sorted(beda_obj)[:3]))
                break
        if alasan:
            beda.append((a["frame"], ", ".join(dict.fromkeys(alasan))))
    return beda


# ---------------------------------------------------------------- video

def baca_video(video, lebar=192, tinggi=108):
    cmd = ["ffmpeg", "-v", "error", "-i", video, "-vf", f"scale={lebar}:{tinggi}:flags=area,format=gray",
           "-f", "rawvideo", "-"]
    data = subprocess.run(cmd, check=True, capture_output=True).stdout
    return np.frombuffer(data, dtype=np.uint8).reshape(-1, tinggi, lebar).astype(np.float32)


def periksa_lompatan(video, segmen):
    F = baca_video(video)
    log(f"video: {len(F)} frame")
    beda = np.zeros(len(F))
    blok = np.zeros(len(F))
    d = np.abs(F[1:] - F[:-1])
    beda[1:] = d.mean(axis=(1, 2))
    # perubahan terbesar di satu bagian gambar (grid 8x6), supaya benda kecil yang meloncat juga tertangkap
    h, w = F.shape[1:]
    g = d[:, : h // 6 * 6, : w // 8 * 8].reshape(len(d), 6, h // 6, 8, w // 8).mean(axis=(2, 4))
    blok[1:] = g.reshape(len(d), -1).max(axis=1)
    temuan, ringkas = [], []
    for a, b, nama in segmen:
        i0, i1 = a - 1, b - 1  # indeks video = frame - 1
        isi = list(range(i0 + 1, min(i1, len(F) - 1) + 1))  # frame pertama segmen = pergantian, dilewati
        if not isi:
            continue
        rb, rk = beda[isi].mean(), blok[isi].mean()
        ringkas.append({"segmen": nama, "awal": a, "akhir": b, "rata": round(float(rb), 2),
                        "maks": round(float(beda[isi].max()), 2),
                        "frame_maks": int(isi[int(np.argmax(beda[isi]))] + 1),
                        "potong": round(float(beda[i0]), 2) if i0 > 0 else None})
        for i in isi:
            alasan = []
            if beda[i] > KALI_LOMPATAN * rb and beda[i] > LANTAI_LOMPATAN:
                alasan.append(f"seluruh gambar {beda[i]:.1f} (rata-rata shot {rb:.1f}, {beda[i] / rb:.1f}x)")
            # Lonjakan setempat: satu bagian gambar berubah jauh di atas rata-rata shot DAN di atas
            # frame-frame tetangganya (gerakan cepat yang berlangsung lama tidak ditandai).
            sekitar = [j for j in range(i - 6, i + 7) if j != i and i0 < j <= i1 and j < len(F)]
            if sekitar and blok[i] > KALI_LOMPATAN * rk and blok[i] > LANTAI_LOMPATAN * 3 \
                    and blok[i] > KALI_LOMPATAN * np.median(blok[sekitar]):
                alasan.append(f"lonjakan di satu bagian gambar {blok[i]:.1f} (rata-rata shot {rk:.1f}, "
                              f"tetangga {np.median(blok[sekitar]):.1f})")
            if alasan and i == i0 + 1:
                alasan.append(f"tepat setelah pergantian: frame pertama potongan ({a}) juga patut dilihat")
            if alasan and i == i1:
                alasan.append("frame terakhir potongan")
            if alasan:
                temuan.append({"frame": i + 1, "segmen": nama, "beda": round(float(beda[i]), 2),
                               "alasan": "; ".join(alasan)})
    return temuan, ringkas, beda


def lembar_kontak(video, folder):
    os.makedirs(folder, exist_ok=True)
    hasil = []
    for s in waktu.SHOTS:
        a, b = s.frame_mulai - 1, s.frame_selesai - 1
        n = len(range(a, b + 1, JARAK_LEMBAR))
        baris = math.ceil(n / KOLOM_LEMBAR)
        teks = (f"drawtext=text='{s.nama}  frame %{{eif\\:n*{JARAK_LEMBAR}+{s.frame_mulai}\\:d}}':"
                "x=8:y=8:fontsize=20:fontcolor=white:box=1:boxcolor=black@0.6:boxborderw=4")
        vf = (f"select='between(n\\,{a}\\,{b})*not(mod(n-{a}\\,{JARAK_LEMBAR}))',"
              f"scale={LEBAR_GAMBAR_LEMBAR}:-2,setpts=N/TB," + teks +
              f",tile={KOLOM_LEMBAR}x{baris}:padding=4:margin=4:color=0x202020")
        keluar = os.path.join(folder, f"{s.nama}.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", video, "-vf", vf, "-frames:v", "1",
                        "-fps_mode", "vfr", "-update", "1", keluar], check=True)
        hasil.append((s, keluar, n))
        log(f"lembar kontak {keluar} ({n} gambar)")
    return hasil


# ---------------------------------------------------------------- laporan

NAMA_JENIS = {"tembus": "Benda menembus benda lain", "ponco": "Tubuh kurir keluar dari ponco",
              "melayang": "Benda tertinggal melayang (tidak ikut bergerak)"}


def label_benda(nama):
    k = kelompok_dari(nama)
    return f"{k} ({nama})" if k and nama in ("Kurir_Ponco", "Kurir_Tubuh", "Kurir_Helm") else (k or nama)


def gabung_kejadian(temuan):
    """Satukan temuan per pasangan (kelompok bergerak, benda lain) pada frame yang
    berdekatan menjadi satu kejadian; bagian-bagian yang masuk dicatat."""
    per_frame = {}
    for t in temuan:
        kunci = (t["jenis"], kelompok_dari(t["a"]) or t["a"], label_benda(t["b"]), t["frame"])
        if kunci not in per_frame or t["cm"] > per_frame[kunci]["cm"]:
            lama = per_frame.get(kunci, {}).get("bagian", set())
            per_frame[kunci] = dict(t, bagian=lama)
        per_frame[kunci]["bagian"].add(t["a"] + (f" ({t['ket']})" if t["ket"] and t["jenis"] != "melayang" else ""))
        per_frame[kunci]["terlihat"] = per_frame[kunci]["terlihat"] or t["terlihat"]
    kej = []
    for (jenis, ka, kb, f), t in sorted(per_frame.items()):
        k = kej[-1] if kej else None
        if (k and (k["jenis"], k["a"], k["b"]) == (jenis, ka, kb)
                and f - k["akhir"] <= LANGKAH_TEMBUS * 2 and shot_untuk(f) is shot_untuk(k["awal"])):
            k["akhir"] = f
            k["jumlah"] += 1
            k["terlihat_n"] += int(t["terlihat"])
            k["bagian"] |= t["bagian"]
            if t["cm"] > k["cm"]:
                k.update(cm=t["cm"], frame_maks=f, titik=t["titik"])
        else:
            kej.append(dict(jenis=jenis, a=ka, b=kb, awal=f, akhir=f, jumlah=1, terlihat_n=int(t["terlihat"]),
                            cm=t["cm"], frame_maks=f, titik=t["titik"], bagian=set(t["bagian"])))
    return sorted(kej, key=lambda k: (k["awal"], k["a"]))


def ringkas_bagian(bagian, n=4):
    b = sorted(bagian)
    return ", ".join(b[:n]) + (f", dan {len(b) - n} lainnya" if len(b) > n else "")


def tulis_laporan(jalur, info, tembus, roda, lompatan, lembar, potong, rana=None):
    L = ["# Laporan pemeriksaan film", ""]
    L.append(f"- Berkas: `{info['blend']}`" + (f", video `{info['video']}`" if info.get("video") else ""))
    L.append(f"- Dibuat: {time.strftime('%Y-%m-%d %H:%M')}, oleh `periksa.py`")
    L.append(f"- Potongan kamera (frame pertama): {', '.join(str(p) for p in potong)}")
    L.append("")
    ringkas = []
    if tembus is not None:
        kej = gabung_kejadian(tembus)
        utama = [k for k in kej if k["jenis"] != "lengan_ponco"]
        ringkas.append(f"Tembus: {len(utama)} kejadian ({sum(1 for k in utama if k['terlihat_n'])} terlihat kamera)")
    if roda is not None:
        ringkas.append(f"Roda: {len(roda[0])} frame-roda tidak cocok")
    if lompatan is not None:
        ringkas.append(f"Lompatan: {len(lompatan[0])} frame ditandai")
    if rana is not None:
        ringkas.append(f"Rana (motion blur): {len(rana['temuan'])} frame ditandai")
    if lembar is not None:
        ringkas.append(f"Lembar kontak: {len(lembar)} shot")
    L += ["## Ringkasan", ""] + [f"- {r}" for r in ringkas] + [""]

    if tembus is not None:
        L += ["## Tembus", "",
              f"Diperiksa setiap {LANGKAH_TEMBUS} frame. Kedalaman = seberapa jauh permukaan satu benda masuk "
              f"ke benda lain (batas {BATAS_TEMBUS * 100:.0f} cm). \"Terlihat\" = titik terdalam ada di dalam "
              "bingkai kamera aktif dan tidak tertutup benda lain, pada berapa frame dari kejadian itu.", ""]
        for jenis in ("tembus", "ponco", "melayang"):
            ks = [k for k in kej if k["jenis"] == jenis]
            L += [f"### {NAMA_JENIS[jenis]} ({len(ks)})", ""]
            if not ks:
                L += ["Tidak ada.", ""]
                continue
            if jenis == "melayang":
                L += ["Benda kecil yang menempel di benda bergerak, lalu tertinggal dan tidak menyentuh apa pun "
                      "saat benda itu bergerak. Kolom kedalaman = jarak terpisah terbesar.", ""]
            kol = ("Benda yang tertinggal | Seharusnya ikut" if jenis == "melayang" else "Benda bergerak | Benda lain")
            L += [f"| Shot | Frame | {kol} | Kedalaman maks | Frame terdalam | Terlihat | Titik (x, y, z) | Bagian |",
                  "|---|---|---|---|---|---|---|---|---|"]
            for k in ks:
                s = shot_untuk(k["awal"])
                fr = f"{k['awal']}–{k['akhir']}" if k["akhir"] > k["awal"] else f"{k['awal']}"
                L.append(f"| {s.nama} | {fr} | {k['a']} | {k['b']} | {k['cm']} cm | "
                         f"{k['frame_maks']} | {k['terlihat_n']}/{k['jumlah']} | "
                         f"{', '.join(f'{x:.2f}' for x in k['titik'])} | {ringkas_bagian(k['bagian'])} |")
            L.append("")
        ks = [k for k in kej if k["jenis"] == "lengan_ponco"]
        if ks:
            L += ["### Catatan: lengan ponco melewati badan ponco", "",
                  "Lengan kurir berbahan ponco kuning, jadi saat lengan keluar menembus badan ponco yang "
                  "tampak hanyalah kain kuning bertemu kain kuning. Secara bentuk lengan tetap menembus "
                  "kain; dicatat di sini, bukan sebagai kesalahan.", "",
                  "| Shot | Frame | Kedalaman maks | Frame terdalam | Terlihat |", "|---|---|---|---|---|"]
            for k in ks:
                L.append(f"| {shot_untuk(k['awal']).nama} | {k['awal']}–{k['akhir']} | {k['cm']} cm | "
                         f"{k['frame_maks']} | {k['terlihat_n']}/{k['jumlah']} |")
            L.append("")

    if roda is not None:
        tem, d = roda
        L += ["## Roda", "",
              "Setiap frame: jarak yang ditempuh as roda ke arah depan motor dibandingkan dengan putaran roda "
              "(sudut × jari-jari ban). Jari-jari diukur dari mesh ban: " +
              ", ".join(f"{k} {v * 100:.1f} cm" for k, v in d["jari"].items()) +
              f". Ditandai bila selisih > {BATAS_RODA * 100:.0f} cm per frame dan > "
              f"{BATAS_RODA_RELATIF * 100:.0f} % jarak tempuh, atau roda bergeser menyamping > "
              f"{BATAS_GESER * 100:.0f} cm per frame. Frame pergantian shot dilewati.", ""]
        if d["data"]:
            sel = np.array([abs(x["selisih"]) for x in d["data"] if x["frame"] not in potong])
            L.append(f"Selisih terbesar di luar pergantian shot: {sel.max() * 100:.2f} cm per frame; "
                     f"rata-rata {sel.mean() * 100:.3f} cm.")
            L.append("")
        if not tem:
            L += ["Tidak ada temuan.", ""]
        else:
            # satukan frame berturutan per roda
            kel = []
            for t in sorted(tem, key=lambda t: (t["roda"], t["frame"])):
                if kel and kel[-1]["roda"] == t["roda"] and t["frame"] - kel[-1]["akhir"] <= 1:
                    k = kel[-1]
                    k["akhir"] = t["frame"]
                    if abs(t["selisih"]) > abs(k["selisih"]):
                        k.update(selisih=t["selisih"], jalan=t["jalan"], putar=t["putar"], fm=t["frame"])
                    k["samping"] = max(k["samping"], t["samping"])
                else:
                    kel.append(dict(t, awal=t["frame"], akhir=t["frame"], fm=t["frame"]))
            L += ["| Shot | Frame | Roda | Frame terburuk | Jalan (cm/frame) | Putaran (cm/frame) | Selisih | Geser samping maks |",
                  "|---|---|---|---|---|---|---|---|"]
            for k in sorted(kel, key=lambda k: k["awal"]):
                L.append(f"| {shot_untuk(k['awal']).nama} | {k['awal']}–{k['akhir']} | {k['roda']} | {k['fm']} | "
                         f"{k['jalan'] * 100:.1f} | {k['putar'] * 100:.1f} | {k['selisih'] * 100:.1f} cm | "
                         f"{k['samping'] * 100:.1f} cm |")
            L.append("")

    if rana is not None:
        L += ["## Rana (motion blur)", "",
              "Setiap frame, rana Cycles terbuka sebentar (0,25 frame). Pemeriksa meniru rana itu: kamera frame "
              "tersebut dan benda bergerak dievaluasi di waktu buka, tengah, dan tutup rana, lalu diukur gesernya "
              "di layar 1920x1080. Subjek = titik benda bergerak yang tampak (sudut kotak batas, tulang); "
              "kamera = titik diam 10 m di depan kamera. Ditandai bila geser > "
              f"{BATAS_RANA_PX:.0f} px dan > {KALI_RANA:.0f}x median 6 frame tetangga di potongan kamera yang sama, "
              "atau bila ada benda berpindah > 1 m selama rana (lompat ke lokasi shot lain).", ""]
        pot = set(potong)
        L += ["Semua pergantian shot (frame terakhir sebelum potongan dan frame pertama sesudahnya):", "",
              "| Potongan | Frame | Kamera | Posisi rana | Waktu rana | Geser subjek | Geser kamera | Berpindah > 1 m |",
              "|---|---|---|---|---|---|---|---|"]
        uk = {u["frame"]: u for u in rana["ukur"]}
        for c in sorted(pot):
            for fr in (c - 1, c):
                if fr in uk:
                    u = uk[fr]
                    L.append(f"| {c} | {fr} | {u['kamera']} | {u['posisi']} | {u['waktu'][0]}–{u['waktu'][2]} | "
                             f"{u['subjek']} px | {u['latar']} px | {', '.join(u['loncat'][:3]) or '-'} |")
        L.append("")
        if not rana["temuan"]:
            L += ["Tidak ada frame yang ditandai.", ""]
        else:
            L += ["Frame yang ditandai:", "", "| Shot | Potongan | Frame | Alasan |", "|---|---|---|---|"]
            for t in rana["temuan"]:
                L.append(f"| {shot_untuk(t['frame']).nama} | {t['segmen']} | {t['frame']} | {t['alasan']} |")
            L.append("")
        if rana.get("banding"):
            b = rana["banding"]
            L += [f"Dibandingkan dengan `{info.get('banding', 'versi lain')}`: {len(b['beda'])} frame berubah di dalam "
                  "rana (daftar di render_ulang.txt). Di versi itu "
                  f"{len(b['temuan'])} frame ditandai.", ""]

    if lompatan is not None:
        tem, ring, _ = lompatan
        L += ["## Lompatan gambar", "",
              "Beda rata-rata piksel (skala abu-abu 0-255, video diperkecil ke 192x108) antara setiap frame "
              f"dan frame sebelumnya. Ditandai bila lebih dari {KALI_LOMPATAN:.0f}x rata-rata potongan kamera itu "
              "(seluruh gambar, atau salah satu dari 48 bagian gambar). Frame pertama setiap potongan kamera "
              "adalah pergantian shot dan tidak ditandai.", "",
              "| Potongan | Frame | Rata-rata beda | Beda terbesar (frame) | Beda di pergantian |", "|---|---|---|---|---|"]
        for r in ring:
            L.append(f"| {r['segmen']} | {r['awal']}–{r['akhir']} | {r['rata']} | {r['maks']} ({r['frame_maks']}) | "
                     f"{r['potong'] if r['potong'] is not None else '-'} |")
        L.append("")
        if not tem:
            L += ["Tidak ada frame yang ditandai.", ""]
        else:
            L += [f"{len(tem)} frame ditandai, disatukan bila berturutan:", "",
                  "| Shot | Potongan | Frame | Beda terbesar (frame) | Alasan di frame terbesar |", "|---|---|---|---|---|"]
            kel = []
            for t in tem:
                if kel and t["frame"] - kel[-1][-1]["frame"] <= 1 and t["segmen"] == kel[-1][0]["segmen"]:
                    kel[-1].append(t)
                else:
                    kel.append([t])
            for k in kel:
                m = max(k, key=lambda t: t["beda"])
                fr = f"{k[0]['frame']}" + (f"–{k[-1]['frame']}" if len(k) > 1 else "")
                L.append(f"| {shot_untuk(m['frame']).nama} | {m['segmen']} | {fr} | {m['beda']} ({m['frame']}) | {m['alasan']} |")
            L.append("")

    if lembar is not None:
        L += ["## Lembar kontak", "", f"Satu gambar setiap {JARAK_LEMBAR} frame, dimulai dari frame pertama shot; "
              "nomor frame tertulis di pojok kiri atas setiap gambar.", ""]
        for s, j, n in lembar:
            L.append(f"- {s.nama} ({s.judul}), frame {s.frame_mulai}–{s.frame_selesai}, {n} gambar: "
                     f"[{os.path.relpath(j, os.path.dirname(jalur))}]({os.path.relpath(j, os.path.dirname(jalur))})")
        L.append("")
    with open(jalur, "w") as f:
        f.write("\n".join(L))
    log(f"laporan: {jalur}")


# ---------------------------------------------------------------- utama

def main():
    arg = argumen()
    pilih = set(arg["hanya"] or ("tembus", "roda", "rana", "lompatan", "lembar"))
    os.makedirs(arg["keluar"], exist_ok=True)
    if os.path.abspath(bpy.data.filepath or "") != arg["blend"]:
        bpy.ops.wm.open_mainfile(filepath=arg["blend"])
    scene = bpy.context.scene
    potong = potongan_kamera(scene)
    a, b = arg["frame"] or (waktu.FRAME_AWAL, waktu.FRAME_AKHIR)
    info = {"blend": arg["blend"]}
    tembus = roda = lompatan = lembar = rana = None
    if arg["dari_json"]:  # tulis ulang laporan dari hasil sebelumnya, tanpa menghitung
        with open(os.path.join(arg["keluar"], "periksa.json")) as f:
            j = json.load(f)
        tembus, roda, rana = j["tembus"], j["roda"], j.get("rana")
        lompatan = (j["lompatan"][0], j["lompatan"][1], np.array(j["lompatan"][2])) if j["lompatan"] else None
        pilih = set()
    if "roda" in pilih:
        roda = periksa_roda(scene, range(a, b + 1))
        log(f"roda: {len(roda[0])} frame-roda ditandai")
    if "rana" in pilih:
        tem, ukur, biasa, sampel = periksa_rana(scene, list(range(a, b + 1)))
        rana = {"temuan": tem, "ukur": ukur, "biasa": biasa, "banding": None}
        log(f"rana: {len(tem)} frame ditandai")
        if arg["banding"]:
            # Bandingkan dengan versi lain (mis. film.blend sebelum perbaikan): frame yang
            # isinya di dalam rana berubah harus dirender ulang.
            info["banding"] = arg["banding"]
            bpy.ops.wm.open_mainfile(filepath=arg["banding"])
            scene_b = bpy.context.scene
            tem_b, ukur_b, biasa_b, sampel_b = periksa_rana(scene_b, list(range(a, b + 1)))
            rana["banding"] = {"beda": banding_rana(sampel_b, sampel), "temuan": tem_b}
            with open(os.path.join(arg["keluar"], "render_ulang.txt"), "w") as f:
                f.write("".join(f"{fr}\n" for fr, _ in rana["banding"]["beda"]))
            log(f"render ulang: {len(rana['banding']['beda'])} frame -> {arg['keluar']}/render_ulang.txt")
            bpy.ops.wm.open_mainfile(filepath=arg["blend"])
            scene = bpy.context.scene
    if "tembus" in pilih:
        tembus = periksa_tembus(scene, list(range(a, b + 1, LANGKAH_TEMBUS)))
    if {"lompatan", "lembar"} & pilih:
        if not os.path.exists(arg["video"]):
            log(f"video {arg['video']} tidak ada, lompatan dan lembar kontak dilewati")
        else:
            info["video"] = arg["video"]
            if "lompatan" in pilih:
                lompatan = periksa_lompatan(arg["video"], segmen_kamera(scene))
            if "lembar" in pilih:
                lembar = lembar_kontak(arg["video"], os.path.join(arg["keluar"], "lembar_kontak"))
    if arg["dari_json"]:
        folder = os.path.join(arg["keluar"], "lembar_kontak")
        ada = [(s, os.path.join(folder, f"{s.nama}.png")) for s in waktu.SHOTS]
        if lompatan is not None:
            info["video"] = arg["video"]
        if all(os.path.exists(j) for _, j in ada):
            lembar = [(s, j, len(range(s.frame_mulai, s.frame_selesai + 1, JARAK_LEMBAR))) for s, j in ada]
    else:
        with open(os.path.join(arg["keluar"], "periksa.json"), "w") as f:
            json.dump({"tembus": tembus, "roda": list(roda) if roda else None, "rana": rana,
                       "lompatan": [lompatan[0], lompatan[1], lompatan[2].round(3).tolist()] if lompatan else None},
                      f)
    tulis_laporan(os.path.join(arg["keluar"], "laporan.md"), info, tembus, roda, lompatan, lembar, potong, rana)


main()
