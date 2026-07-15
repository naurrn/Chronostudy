import numpy as np
import random
import time
import pygad
from deap import base, creator, tools, algorithms
import warnings
warnings.filterwarnings("ignore")


# ── KURVA KOGNITIF ─────────────────────────────────────────
def bangun_kurva(skor_meq: int):
    pagi = np.array([
        0.10,0.10,0.10,0.10,0.15,0.30,
        0.55,0.80,0.95,1.00,0.95,0.85,
        0.70,0.55,0.50,0.55,0.50,0.40,
        0.30,0.25,0.20,0.15,0.10,0.10])
    inter = np.array([
        0.10,0.10,0.10,0.10,0.10,0.20,
        0.35,0.55,0.75,0.90,1.00,0.95,
        0.80,0.65,0.60,0.70,0.75,0.65,
        0.55,0.45,0.35,0.25,0.15,0.10])
    malam = np.array([
        0.15,0.10,0.10,0.10,0.10,0.10,
        0.15,0.25,0.40,0.55,0.65,0.70,
        0.65,0.60,0.65,0.75,0.85,0.90,
        0.95,1.00,0.95,0.85,0.65,0.40])
    if skor_meq >= 59:
        return pagi,  "Tipe Pagi",   "krono-pagi",  "🌅"
    elif skor_meq >= 42:
        return inter, "Intermediate","krono-inter", "⚖️"
    else:
        return malam, "Tipe Malam",  "krono-malam", "🌙"


# ── FUNGSI FITNESS ─────────────────────────────────────────
def hitung_fitness(kromosom, sesi, slots, kurva, bobot):
    total, penalti = 0.0, 0.0
    jadwal_harian = {}

    for i, idx in enumerate(kromosom):
        if idx >= len(slots):
            penalti += 999
            continue
        hari, jam = slots[idx]
        total += kurva[jam] * bobot[sesi[i]] * 10
        jadwal_harian.setdefault(hari, []).append((jam, sesi[i]))

    # Penalti slot duplikat
    for i in range(len(kromosom)):
        for j in range(i + 1, len(kromosom)):
            if kromosom[i] == kromosom[j]:
                penalti += 9999

    # Penalti matkul berat di jam energi rendah
    for i, idx in enumerate(kromosom):
        if idx < len(slots):
            _, jam = slots[idx]
            if bobot[sesi[i]] >= 4/6 and kurva[jam] < 0.5:
                penalti += 200

    # Penalti >3 sesi per hari
    for h, s in jadwal_harian.items():
        if len(s) > 3:
            penalti += 300 * (len(s) - 3)

    # Penalti jeda terlalu dekat
    for h, s in jadwal_harian.items():
        jams = sorted(x[0] for x in s)
        for k in range(len(jams) - 1):
            if jams[k+1] - jams[k] < 2:
                penalti += 100

    return max(0.0, total - penalti)


# ── PYGAD ──────────────────────────────────────────────────
def run_pygad(sesi, slots, kurva, bobot, gen=50):
    riwayat = []

    def ff(ga, sol, idx):
        return hitung_fitness(list(sol.astype(int)), sesi, slots, kurva, bobot)

    def og(ga):
        riwayat.append(ga.best_solution()[1])

    ga = pygad.GA(
        num_generations       = gen,
        num_parents_mating    = 10,
        fitness_func          = ff,
        sol_per_pop           = 50,
        num_genes             = len(sesi),
        gene_type             = int,
        gene_space            = list(range(len(slots))),
        parent_selection_type = "tournament",
        crossover_type        = "two_points",
        mutation_type         = "random",
        mutation_percent_genes= 15,
        keep_elitism          = 2,
        on_generation         = og,
        suppress_warnings     = True,
    )

    t = time.time()
    ga.run()
    dur = time.time() - t
    sol, fit, _ = ga.best_solution()
    return list(sol.astype(int)), fit, dur, riwayat


# ── DEAP ───────────────────────────────────────────────────
def run_deap(sesi, slots, kurva, bobot, gen=50):
    n = len(slots)

    for a in ["FitnessMax", "Individual"]:
        if hasattr(creator, a):
            delattr(creator, a)

    creator.create("FitnessMax", base.Fitness, weights=(1.0,))
    creator.create("Individual", list, fitness=creator.FitnessMax)

    tb = base.Toolbox()
    tb.register("attr",       random.randint, 0, n - 1)
    tb.register("individual", tools.initRepeat, creator.Individual, tb.attr, n=len(sesi))
    tb.register("population", tools.initRepeat, list, tb.individual)
    tb.register("evaluate",   lambda ind: (hitung_fitness(ind, sesi, slots, kurva, bobot),))
    tb.register("select",     tools.selTournament, tournsize=3)
    tb.register("mate",       tools.cxTwoPoint)
    tb.register("mutate",     tools.mutUniformInt, low=0, up=n - 1, indpb=0.15)

    pop = tb.population(n=30)
    hof = tools.HallOfFame(1)
    for ind in pop:
        ind.fitness.values = tb.evaluate(ind)

    riwayat = []
    t = time.time()

    for _ in range(gen):
        off = algorithms.varAnd(pop, tb, cxpb=0.7, mutpb=0.2)
        for ind in off:
            if not ind.fitness.valid:
                ind.fitness.values = tb.evaluate(ind)
        pop = tb.select(off + pop, k=len(pop))
        hof.update(pop)
        riwayat.append(max(i.fitness.values[0] for i in pop if i.fitness.valid))

    dur = time.time() - t
    return list(hof[0]), hof[0].fitness.values[0], dur, riwayat


# ── BEST-OF-N (dipakai di produksi, main.py) ────────────────
# Menjalankan run_pygad/run_deap sebanyak `pengulangan` kali dengan
# `gen` generasi masing-masing, lalu mengambil hasil dengan fitness
# tertinggi. Durasi yang dikembalikan adalah TOTAL waktu komputasi dari
# seluruh pengulangan (bukan cuma run pemenang), karena itu yang benar-benar
# dirasakan pengguna sebagai waktu tunggu.
def run_pygad_terbaik(sesi, slots, kurva, bobot, gen=50, pengulangan=10):
    terbaik = None
    total_dur = 0.0
    for _ in range(pengulangan):
        sol, fit, dur, riwayat = run_pygad(sesi, slots, kurva, bobot, gen=gen)
        total_dur += dur
        if terbaik is None or fit > terbaik[1]:
            terbaik = (sol, fit, riwayat)
    sol, fit, riwayat = terbaik
    return sol, fit, total_dur, riwayat


def run_deap_terbaik(sesi, slots, kurva, bobot, gen=50, pengulangan=10):
    terbaik = None
    total_dur = 0.0
    for _ in range(pengulangan):
        sol, fit, dur, riwayat = run_deap(sesi, slots, kurva, bobot, gen=gen)
        total_dur += dur
        if terbaik is None or fit > terbaik[1]:
            terbaik = (sol, fit, riwayat)
    sol, fit, riwayat = terbaik
    return sol, fit, total_dur, riwayat


# ── BASELINE ───────────────────────────────────────────────
def generate_baseline(sesi, slots, kurva, bobot, n_run=30):
    fitness_list = []
    for _ in range(n_run):
        kromosom = [random.randint(0, len(slots) - 1) for _ in sesi]
        fitness_list.append(hitung_fitness(kromosom, sesi, slots, kurva, bobot))
    return {
        "fitness_list" : fitness_list,
        "rata_rata"    : float(np.mean(fitness_list)),
        "std"          : float(np.std(fitness_list)),
        "terbaik"      : float(np.max(fitness_list)),
    }


# ── HELPER ─────────────────────────────────────────────────
def susun_jadwal(kromosom, sesi, slots, kurva, bobot, hari_names):
    jadwal = {}
    for i, idx in enumerate(kromosom):
        if idx >= len(slots):
            continue
        hari, jam = slots[idx]
        en = round(kurva[jam] * 100)
        bl = round(bobot[sesi[i]] * 6)
        jadwal.setdefault(hari_names[hari], []).append((jam, sesi[i], en, bl))
    return jadwal


def en_color(pct: int) -> str:
    if pct >= 70:  return "#34D399"
    elif pct >= 40: return "#FBBF24"
    return "#F472B6"
