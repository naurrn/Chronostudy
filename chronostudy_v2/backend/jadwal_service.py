"""
jadwal_service.py
==================
Logika inti pembuatan & penyimpanan jadwal, dipisah dari main.py supaya
bisa dipakai ulang baik oleh endpoint form biasa (/api/jadwal/generate)
maupun endpoint chatbot AI (/api/chat/ai-input). Satu sumber kebenaran
untuk pengecekan kelayakan (jumlah sesi vs slot waktu tersedia).
"""

from fastapi import HTTPException

from constants import HARI, JAM_OPTIONS
from algorithm.scheduler import bangun_kurva, run_pygad_terbaik, run_deap_terbaik, susun_jadwal
import database as db


class JadwalInfeasibleError(Exception):
    """Dilempar kalau jumlah sesi yang diminta melebihi slot waktu yang tersedia."""

    def __init__(self, jumlah_sesi: int, jumlah_slot: int):
        self.jumlah_sesi = jumlah_sesi
        self.jumlah_slot = jumlah_slot
        super().__init__(
            f"Jumlah sesi ({jumlah_sesi}) melebihi slot waktu tersedia ({jumlah_slot})."
        )


def hitung_slot_tersedia(hari: list[str], jam_ranges: list[str]) -> tuple[list, list]:
    """Kembalikan (slots, jam_list) dari daftar hari & rentang jam yang dipilih."""
    hari_idx_map = {h: i for i, h in enumerate(HARI)}
    jam_list = sorted(set(j for r in jam_ranges for j in JAM_OPTIONS.get(r, [])))
    ketersediaan = {hari_idx_map[h]: jam_list for h in hari if h in hari_idx_map}
    slots = [(h, j) for h, jl in ketersediaan.items() for j in jl]
    return slots, jam_list


def buat_dan_simpan_jadwal(
    user: dict, hari: list[str], jam_ranges: list[str], matkul: list[dict]
) -> dict:
    """
    Fungsi inti: bangun kurva energi, cek kelayakan, jalankan PyGAD & DEAP,
    simpan hasil ke DB, dan kembalikan payload jadwal.

    `matkul` = list of dict {"nama": str, "bloom": int(1-6), "sesi": int}

    Melempar:
      - HTTPException(400) untuk input yang jelas tidak valid (MEQ kosong, dll)
      - JadwalInfeasibleError kalau jumlah sesi > slot tersedia
    """
    if not user.get("skor_meq"):
        raise HTTPException(status_code=400, detail="Isi kuesioner MEQ terlebih dahulu.")
    if not hari or not jam_ranges:
        raise HTTPException(status_code=400, detail="Pilih minimal 1 hari dan 1 rentang jam.")
    if not matkul:
        raise HTTPException(status_code=400, detail="Isi minimal 1 mata kuliah.")

    skor = user["skor_meq"]
    kurva, tipe, kelas, emoji = bangun_kurva(skor)

    slots, jam_list = hitung_slot_tersedia(hari, jam_ranges)
    if not jam_list:
        raise HTTPException(status_code=400, detail="Rentang jam tidak valid.")

    bobot = {m["nama"]: m["bloom"] / 6.0 for m in matkul}
    sesi = [m["nama"] for m in matkul for _ in range(m["sesi"])]

    if len(sesi) > len(slots):
        raise JadwalInfeasibleError(len(sesi), len(slots))

    # Sama seperti endpoint form manual (/api/jadwal/generate di main.py):
    # tiap library dijalankan 10 kali (50 generasi/run) dan diambil hasil
    # dengan fitness terbaik, supaya jadwal yang dihasilkan lewat chatbot
    # tidak berbeda kualitasnya dari yang dihasilkan lewat form manual.
    sol_p, fit_p, dur_p, riwayat_p = run_pygad_terbaik(sesi, slots, kurva, bobot, gen=50, pengulangan=10)
    sol_d, fit_d, dur_d, riwayat_d = run_deap_terbaik(sesi, slots, kurva, bobot, gen=50, pengulangan=10)

    pemenang = "PyGAD" if fit_p >= fit_d else "DEAP"
    best_sol = sol_p if fit_p >= fit_d else sol_d

    jadwal = susun_jadwal(best_sol, sesi, slots, kurva, bobot, HARI)

    input_data = {"hari": hari, "jam_ranges": jam_ranges, "matkul": matkul}

    hasil_id = db.simpan_hasil(
        user["id"], skor, tipe, jadwal, input_data,
        fit_p, fit_d, dur_p, dur_d, riwayat_p, riwayat_d, pemenang
    )

    return {
        "hasil_id": hasil_id,
        "kronotipe": tipe,
        "skor_meq": skor,
        "jadwal": jadwal,
        "kurva": kurva.tolist(),
        "hari_order": HARI,
        "input_data": input_data,
    }
