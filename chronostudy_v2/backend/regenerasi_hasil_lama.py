"""
regenerasi_hasil_lama.py
========================
Menjalankan ULANG seluruh data hasil yang sudah ada di database (chronostudy.db)
menggunakan algoritma produksi yang BARU (run_pygad_terbaik / run_deap_terbaik,
50 generasi x 10 pengulangan, diambil hasil terbaik) -- menggantikan hasil lama
yang dihitung dengan versi single-run (50 generasi x 1 pengulangan).

Kenapa ini aman dilakukan:
    - Data masukan asli tiap responden (hari, jam_ranges, matkul) sudah
      tersimpan lengkap di kolom `input_json`, jadi tidak perlu minta
      responden mengisi ulang formulir.
    - Skor MEQ & kronotipe tidak berubah, jadi cukup hitung ulang bagian
      fitness/durasi/riwayat/pemenang/jadwal-nya saja.

CARA PAKAI:
    1. Jalankan dari folder backend/ (yang berisi chronostudy.db):
         cd backend
         python regenerasi_hasil_lama.py
    2. Script akan bikin BACKUP dulu (chronostudy_SEBELUM_REGENERASI.db)
       sebelum menimpa data apa pun.
    3. Setelah selesai, export ulang CSV lewat panel admin seperti biasa
       (atau lihat fungsi export_csv di bagian bawah file ini).
"""

import json
import shutil
import sqlite3
from pathlib import Path

from constants import HARI, HARI_IDX, JAM_OPTIONS
from algorithm.scheduler import (
    bangun_kurva, run_pygad_terbaik, run_deap_terbaik, susun_jadwal,
)

DB_PATH = str(Path(__file__).resolve().parent / "chronostudy.db")
BACKUP_PATH = str(Path(__file__).resolve().parent / "chronostudy_SEBELUM_REGENERASI.db")


def bangun_slots(hari_list, jam_ranges):
    jam_list = sorted(set(j for r in jam_ranges for j in JAM_OPTIONS.get(r, [])))
    ketersediaan = {HARI_IDX[h]: jam_list for h in hari_list if h in HARI_IDX}
    return [(h, j) for h, jl in ketersediaan.items() for j in jl]


def main():
    # 1. Backup dulu sebelum apa pun ditimpa
    if not Path(BACKUP_PATH).exists():
        shutil.copy(DB_PATH, BACKUP_PATH)
        print(f"Backup dibuat: {BACKUP_PATH}")
    else:
        print(f"Backup sudah ada sebelumnya di: {BACKUP_PATH} (tidak ditimpa ulang)")

    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    cur.execute("SELECT id, skor_meq, kronotipe, input_json FROM hasil ORDER BY id")
    rows = cur.fetchall()
    print(f"Total {len(rows)} baris hasil akan dihitung ulang...\n")

    for i, row in enumerate(rows, start=1):
        hasil_id = row["id"]
        skor_meq = row["skor_meq"]
        input_data = json.loads(row["input_json"])

        hari_list = input_data["hari"]
        jam_ranges = input_data["jam_ranges"]
        matkul = input_data["matkul"]

        kurva, tipe, _, _ = bangun_kurva(skor_meq)
        slots = bangun_slots(hari_list, jam_ranges)
        bobot = {m["nama"]: m["bloom"] / 6.0 for m in matkul}
        sesi = [m["nama"] for m in matkul for _ in range(m["sesi"])]

        if len(sesi) > len(slots):
            print(f"  [{i}/{len(rows)}] id={hasil_id}: DILEWATI (sesi={len(sesi)} > slot={len(slots)}, "
                  f"data lama ini sebenarnya sudah tidak feasible)")
            continue

        sol_p, fit_p, dur_p, riwayat_p = run_pygad_terbaik(sesi, slots, kurva, bobot, gen=50, pengulangan=10)
        sol_d, fit_d, dur_d, riwayat_d = run_deap_terbaik(sesi, slots, kurva, bobot, gen=50, pengulangan=10)

        pemenang = "PyGAD" if fit_p >= fit_d else "DEAP"
        best_sol = sol_p if fit_p >= fit_d else sol_d
        jadwal = susun_jadwal(best_sol, sesi, slots, kurva, bobot, HARI)

        cur.execute("""
            UPDATE hasil
            SET jadwal_json=?, fit_pygad=?, fit_deap=?, dur_pygad=?, dur_deap=?,
                riwayat_pygad=?, riwayat_deap=?, pemenang=?
            WHERE id=?
        """, (
            json.dumps(jadwal), fit_p, fit_d, dur_p, dur_d,
            json.dumps(riwayat_p), json.dumps(riwayat_d), pemenang, hasil_id,
        ))

        print(f"  [{i}/{len(rows)}] id={hasil_id} ({tipe}): "
              f"PyGAD={fit_p:.2f} ({dur_p:.2f}s)  DEAP={fit_d:.2f} ({dur_d:.2f}s)  -> {pemenang}")

    con.commit()
    con.close()
    print("\nSelesai! Semua hasil sudah dihitung ulang memakai algoritma 50x10 yang baru.")
    print("Sekarang export ulang CSV lewat panel admin untuk dipakai di analisis_data_real.py.")


if __name__ == "__main__":
    main()
