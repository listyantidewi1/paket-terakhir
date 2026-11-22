"""Daftar shot dari STORYBOARD.md, dalam detik dan frame (24 fps).

Frame pertama film adalah 1. Shot yang berlangsung dari detik a sampai b
memakai frame a*FPS+1 sampai b*FPS, jadi shot tidak pernah tumpang tindih.
"""

FPS = 24

# (nomor, detik mulai, detik selesai, judul singkat)
_STORYBOARD = [
    (1, 0, 7, "Kota Senja hujan"),
    (2, 7, 20, "GPS: belok kanan ke kali"),
    (3, 20, 33, "Kucing di lampu merah"),
    (4, 33, 40, "Gang Melati, pagar hijau"),
    (5, 40, 48, "Label: Penerima: Ayah"),
    (6, 48, 54, "Mengetuk pintu"),
    (7, 54, 66, "Siluet anak dan kue"),
    (8, 66, 75, "Pintu menutup, judul"),
]


class Shot:
    def __init__(self, nomor, detik_mulai, detik_selesai, judul):
        self.nomor = nomor
        self.detik_mulai = detik_mulai
        self.detik_selesai = detik_selesai
        self.judul = judul

    @property
    def nama(self):
        return f"S{self.nomor:02d}"

    @property
    def frame_mulai(self):
        return self.detik_mulai * FPS + 1

    @property
    def frame_selesai(self):
        return self.detik_selesai * FPS

    @property
    def frame_tengah(self):
        return (self.frame_mulai + self.frame_selesai) // 2

    def __repr__(self):
        return (f"{self.nama} {self.detik_mulai}-{self.detik_selesai}s "
                f"frame {self.frame_mulai}-{self.frame_selesai} {self.judul}")


SHOTS = [Shot(*baris) for baris in _STORYBOARD]
FRAME_AWAL = SHOTS[0].frame_mulai
FRAME_AKHIR = SHOTS[-1].frame_selesai


def periksa():
    """Pastikan shot berurutan, tanpa celah, dan total 75 detik."""
    for a, b in zip(SHOTS, SHOTS[1:]):
        assert a.detik_selesai == b.detik_mulai, f"celah antara {a.nama} dan {b.nama}"
    assert SHOTS[0].detik_mulai == 0
    assert SHOTS[-1].detik_selesai == 75, "total film harus 75 detik"
    assert len(SHOTS) == 8


periksa()
