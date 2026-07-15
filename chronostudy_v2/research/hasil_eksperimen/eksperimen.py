"""
eksperimen.py
=================================================================
Skrip pengujian TERPISAH dari aplikasi utama ChronoStudy.
Tujuannya: mengumpulkan data untuk Bab 4 (analisis hasil optimasi),
dengan menjalankan PyGAD dan DEAP beberapa kali pengulangan pada
beberapa profil kronotipe, lalu membandingkannya dengan baseline
penjadwalan acak.

Cara pakai:
    1. Taruh file ini di dalam folder backend/ (sejajar dengan main.py),
       supaya bisa import dari algorithm/scheduler.py
    2. Pastikan pandas & matplotlib sudah terinstal:
           pip install pandas matplotlib
    3. Jalankan:
           python eksperimen.py
    4. Hasilnya akan muncul di folder ./hasil_eksperimen/:
           - raw_results.csv        -> tiap baris = 1 kali run algoritma
           - ringkasan.csv          -> rata-rata & std per profil x library
           - konvergensi_<profil>.png -> grafik konvergensi PyGAD vs DEAP
=================================================================
"""

import os
import time
import statistics
import pandas as pd
import matplotlib.pyplot as plt

from backend.algorithm.scheduler import (
    bangun_kurva,
    run_pygad,
    run_deap,
    generate_baseline
)

# ── KONFIGURASI EKSPERIMEN ──────
JUMLAH_GENERASI   = 100   
JUMLAH_PENGULANGAN = 10   
OUTPUT_DIR        = "hasil_eksperimen"

# Profil kronotipe yang diuji mewakili 3 kategori (skor MEQ representatif)
PROFIL_UJI = [
    {"nama_profil": "Tipe Pagi",    "skor_meq": 70},
    {"nama_profil": "Intermediate", "skor_meq": 50},
    {"nama_profil": "Tipe Malam",   "skor_meq": 25},
]

# Daftar mata kuliah contoh
MATKUL_UJI = [
    {"nama": "Kalkulus",        "bloom": 5, "sesi": 3},
    {"nama": "Pemrograman",     "bloom": 6, "sesi": 3},
    {"nama": "Bahasa Inggris",  "bloom": 2, "sesi": 2},
    {"nama": "Desain",          "bloom": 4, "sesi": 2},
    {"nama": "Statistika",      "bloom": 4, "sesi": 2},
]

# Ketersediaan waktu 
HARI_TERSEDIA = list(range(5))
JAM_TERSEDIA  = list(range(7, 22))


def bangun_input():
    """Membentuk slots, sesi, dan bobot dari MATKUL_UJI & ketersediaan waktu."""
    slots = [(h, j) for h in HARI_TERSEDIA for j in JAM_TERSEDIA]
    bobot = {m["nama"]: m["bloom"] / 6.0 for m in MATKUL_UJI}
    sesi = [m["nama"] for m in MATKUL_UJI for _ in range(m["sesi"])]
    return slots, sesi, bobot


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    slots, sesi, bobot = bangun_input()

    raw_rows = []          # tiap baris = satu kali run
    ringkasan_rows = []     # satu baris per profil x library 

    for profil in PROFIL_UJI:
        nama_profil = profil["nama_profil"]
        kurva, tipe, _, _ = bangun_kurva(profil["skor_meq"])
        print(f"\n=== Profil: {nama_profil} (skor MEQ={profil['skor_meq']}, kronotipe={tipe}) ===")

        riwayat_pygad_semua = []  
        riwayat_deap_semua  = []
        fitness_pygad, fitness_deap, durasi_pygad, durasi_deap = [], [], [], []

        for run_ke in range(1, JUMLAH_PENGULANGAN + 1):
            print(f"  Run {run_ke}/{JUMLAH_PENGULANGAN} ...")

            # ── PyGAD ──
            t0 = time.time()
            _, fit_p, dur_p, riwayat_p = run_pygad(sesi, slots, kurva, bobot, gen=JUMLAH_GENERASI)
            fitness_pygad.append(fit_p)
            durasi_pygad.append(dur_p)
            riwayat_pygad_semua.append(riwayat_p)
            raw_rows.append({
                "profil": nama_profil, "library": "PyGAD", "run_ke": run_ke,
                "fitness": fit_p, "durasi_detik": dur_p,
            })

            # ── DEAP ──
            _, fit_d, dur_d, riwayat_d = run_deap(sesi, slots, kurva, bobot, gen=JUMLAH_GENERASI)
            fitness_deap.append(fit_d)
            durasi_deap.append(dur_d)
            riwayat_deap_semua.append(riwayat_d)
            raw_rows.append({
                "profil": nama_profil, "library": "DEAP", "run_ke": run_ke,
                "fitness": fit_d, "durasi_detik": dur_d,
            })

        # ── Baseline (penjadwalan acak, tanpa evolusi) ──
        baseline = generate_baseline(sesi, slots, kurva, bobot, n_run=30)

        # ── Ringkasan statistik per profil x library ──
        ringkasan_rows.append({
            "profil": nama_profil, "library": "PyGAD",
            "fitness_rata2": statistics.mean(fitness_pygad),
            "fitness_std": statistics.stdev(fitness_pygad),
            "fitness_terbaik": max(fitness_pygad),
            "durasi_rata2_detik": statistics.mean(durasi_pygad),
        })
        ringkasan_rows.append({
            "profil": nama_profil, "library": "DEAP",
            "fitness_rata2": statistics.mean(fitness_deap),
            "fitness_std": statistics.stdev(fitness_deap),
            "fitness_terbaik": max(fitness_deap),
            "durasi_rata2_detik": statistics.mean(durasi_deap),
        })
        ringkasan_rows.append({
            "profil": nama_profil, "library": "Baseline (acak)",
            "fitness_rata2": baseline["rata_rata"],
            "fitness_std": baseline["std"],
            "fitness_terbaik": baseline["terbaik"],
            "durasi_rata2_detik": None,
        })

        # ── Grafik konvergensi (rata-rata tiap generasi dari semua run) ──
        rata_riwayat_pygad = [statistics.mean(gen_vals) for gen_vals in zip(*riwayat_pygad_semua)]
        rata_riwayat_deap  = [statistics.mean(gen_vals) for gen_vals in zip(*riwayat_deap_semua)]

        plt.figure(figsize=(8, 5))
        plt.plot(rata_riwayat_pygad, label="PyGAD")
        plt.plot(rata_riwayat_deap, label="DEAP")
        plt.axhline(baseline["rata_rata"], color="gray", linestyle="--",
                    label="Baseline (rata-rata acak)")
        plt.xlabel("Generasi")
        plt.ylabel("Nilai Fitness")
        plt.title(f"Grafik Konvergensi Fitness — {nama_profil}")
        plt.legend()
        plt.tight_layout()
        plt.savefig(os.path.join(OUTPUT_DIR, f"konvergensi_{nama_profil.replace(' ', '_')}.png"))
        plt.close()

    # ── Simpan CSV ──
    pd.DataFrame(raw_rows).to_csv(os.path.join(OUTPUT_DIR, "raw_results.csv"), index=False)
    pd.DataFrame(ringkasan_rows).to_csv(os.path.join(OUTPUT_DIR, "ringkasan.csv"), index=False)

    print(f"\nSelesai! Hasil tersimpan di folder '{OUTPUT_DIR}/':")
    print("  - raw_results.csv       (data tiap run, buat lampiran/analisis lanjutan)")
    print("  - ringkasan.csv         (rata-rata & std per profil x library, siap ditaro jadi tabel di Bab 4)")
    print("  - konvergensi_<profil>.png  (grafik konvergensi per profil kronotipe)")


if __name__ == "__main__":
    main()