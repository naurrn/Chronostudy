"""
hasil_analisis.py
==================
Jalanin setelah data_responden_FINAL_bersih.csv ada (hasil dari
analisis_final.py / export terbaru sistem 50x10).

    python hasil_analisis.py

Beda dengan analisis_final.py (yang mulai dari data mentah + dedup + buang
dummy), script ini mulai dari data yang SUDAH bersih -- jadi tinggal:
    1. Pisah feasible (fitness > 0) vs infeasible (fitness = 0 di keduanya)
    2. Hitung statistik lengkap (rata-rata, std, menang/seri/kalah)
    3. Bikin 4 chart (boxplot fitness, boxplot durasi, fitness per
       kronotipe, kemenangan algoritma)

Perlu: pip install pandas matplotlib
"""

import pandas as pd
import matplotlib.pyplot as plt

INPUT_CSV = "data_responden_EXPORT.csv"


def buat_boxplot_fitness(feasible):
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.boxplot(
        [feasible["fit_pygad"], feasible["fit_deap"]],
        tick_labels=["PyGAD", "DEAP"],
        patch_artist=True,
        boxprops=dict(facecolor="#C8B8FF"),
        medianprops=dict(color="#1C1917", linewidth=2),
    )
    ax.set_ylabel("Fitness")
    ax.set_title("Sebaran Fitness: PyGAD vs DEAP (50 gen x 10 pengulangan)")
    ax.grid(axis="y", alpha=.3)
    fig.tight_layout()
    fig.savefig("boxplot_fitness.png", dpi=150)
    plt.close(fig)


def buat_boxplot_durasi(feasible):
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.boxplot(
        [feasible["dur_pygad"], feasible["dur_deap"]],
        tick_labels=["PyGAD", "DEAP"],
        patch_artist=True,
        boxprops=dict(facecolor="#E8D5B0"),
        medianprops=dict(color="#1C1917", linewidth=2),
    )
    ax.set_ylabel("Durasi rata-rata per run (detik)")
    ax.set_title("Sebaran Waktu Komputasi: PyGAD vs DEAP")
    ax.grid(axis="y", alpha=.3)
    fig.tight_layout()
    fig.savefig("boxplot_durasi.png", dpi=150)
    plt.close(fig)


def buat_fitness_per_kronotipe(ringkasan):
    kategori = sorted(ringkasan["kategori"].unique())
    x = range(len(kategori))
    width = 0.35

    pygad_vals = [ringkasan[(ringkasan.kategori == k) & (ringkasan.library == "PyGAD")]["fitness_rata2"].values[0] for k in kategori]
    deap_vals  = [ringkasan[(ringkasan.kategori == k) & (ringkasan.library == "DEAP")]["fitness_rata2"].values[0] for k in kategori]

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar([i - width/2 for i in x], pygad_vals, width, label="PyGAD", color="#7C5CFC")
    ax.bar([i + width/2 for i in x], deap_vals, width, label="DEAP", color="#C8B8FF")
    ax.set_xticks(list(x))
    ax.set_xticklabels(kategori)
    ax.set_ylabel("Fitness rata-rata")
    ax.set_title("Fitness Rata-rata per Kronotipe")
    ax.legend()
    ax.grid(axis="y", alpha=.3)
    fig.tight_layout()
    fig.savefig("fitness_per_kronotipe.png", dpi=150)
    plt.close(fig)


def buat_kemenangan_algoritma(feasible):
    pygad_win = int((feasible.fit_pygad > feasible.fit_deap).sum())
    deap_win  = int((feasible.fit_deap > feasible.fit_pygad).sum())
    tie       = int((feasible.fit_pygad == feasible.fit_deap).sum())

    labels = ["PyGAD menang", "DEAP menang", "Seri"]
    values = [pygad_win, deap_win, tie]
    colors = ["#7C5CFC", "#E8D5B0", "#D9D3C7"]

    fig, ax = plt.subplots(figsize=(6, 5))
    bars = ax.bar(labels, values, color=colors)
    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, v + 0.1, str(v), ha="center", fontweight="bold")
    ax.set_ylabel("Jumlah responden")
    ax.set_title(f"Perbandingan Kemenangan Algoritma (n={len(feasible)})")
    ax.grid(axis="y", alpha=.3)
    fig.tight_layout()
    fig.savefig("kemenangan_algoritma.png", dpi=150)
    plt.close(fig)


def main():
    df = pd.read_csv(INPUT_CSV)
    print(f"Total responden: {len(df)}")

    is_infeasible = (df.fit_pygad == 0) & (df.fit_deap == 0)
    feasible = df[~is_infeasible].reset_index(drop=True)
    infeasible = df[is_infeasible].reset_index(drop=True)

    feasible.to_csv("data_feasible_bab4.csv", index=False)
    infeasible.to_csv("data_infeasible_temuan.csv", index=False)

    print(f"Feasible: {len(feasible)} | Infeasible: {len(infeasible)}")
    print("\nDistribusi kronotipe -- FEASIBLE:")
    print(feasible["kronotipe"].value_counts())
    print("\nDistribusi kronotipe -- INFEASIBLE:")
    print(infeasible["kronotipe"].value_counts())

    print(f"\n=== STATISTIK KESELURUHAN (n={len(feasible)} responden feasible) ===")
    for lib, col_fit, col_dur in [("PyGAD", "fit_pygad", "dur_pygad"), ("DEAP", "fit_deap", "dur_deap")]:
        print(f"\n{lib}:")
        print(f"  Fitness rata-rata : {feasible[col_fit].mean():.3f}")
        print(f"  Fitness std       : {feasible[col_fit].std():.3f}")
        print(f"  Fitness min/max   : {feasible[col_fit].min():.2f} / {feasible[col_fit].max():.2f}")
        print(f"  Durasi rata-rata  : {feasible[col_dur].mean():.4f} detik")
        print(f"  Durasi std        : {feasible[col_dur].std():.4f} detik")

    print("\n=== PER KATEGORI KRONOTIPE ===")
    ringkasan_rows = []
    for krono, g in feasible.groupby("kronotipe"):
        for lib, col_fit, col_dur in [("PyGAD", "fit_pygad", "dur_pygad"), ("DEAP", "fit_deap", "dur_deap")]:
            ringkasan_rows.append({
                "kategori": krono, "library": lib, "n": len(g),
                "fitness_rata2": g[col_fit].mean(),
                "fitness_std": g[col_fit].std(),
                "durasi_rata2_detik": g[col_dur].mean(),
            })
    ringkasan = pd.DataFrame(ringkasan_rows)
    print(ringkasan.to_string(index=False))
    ringkasan.to_csv("ringkasan_bab4.csv", index=False)

    print("\n=== MENANG / SERI / KALAH (PyGAD vs DEAP) ===")
    pygad_win = (feasible.fit_pygad > feasible.fit_deap).sum()
    deap_win = (feasible.fit_deap > feasible.fit_pygad).sum()
    tie = (feasible.fit_pygad == feasible.fit_deap).sum()
    n = len(feasible)
    print(f"PyGAD menang murni : {pygad_win} ({pygad_win/n*100:.1f}%)")
    print(f"DEAP menang murni  : {deap_win} ({deap_win/n*100:.1f}%)")
    print(f"Seri               : {tie} ({tie/n*100:.1f}%)")

    speedup = (feasible.dur_pygad / feasible.dur_deap).mean()
    print(f"\nDEAP rata-rata {speedup:.2f}x lebih cepat dari PyGAD")

    buat_boxplot_fitness(feasible)
    buat_boxplot_durasi(feasible)
    buat_fitness_per_kronotipe(ringkasan)
    buat_kemenangan_algoritma(feasible)

    print("\nSelesai! File yang dihasilkan:")
    print("  - data_feasible_bab4.csv, data_infeasible_temuan.csv, ringkasan_bab4.csv")
    print("  - boxplot_fitness.png, boxplot_durasi.png")
    print("  - fitness_per_kronotipe.png, kemenangan_algoritma.png")


if __name__ == "__main__":
    main()