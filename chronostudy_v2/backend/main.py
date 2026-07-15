from fastapi import FastAPI, HTTPException, Depends, Response, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

import os
import database as db
from models import RegisterRequest, LoginRequest, MEQSubmit, JadwalRequest, ChatMessage, AdminLogin
from auth import generate_token, get_current_user
from constants import HARI, MEQ_QUESTIONS, BLOOM_OPTIONS, JAM_OPTIONS
from algorithm.scheduler import bangun_kurva, run_pygad_terbaik, run_deap_terbaik, susun_jadwal
from chatbot import get_bot_reply
from pdf_export import generate_schedule_pdf
from jadwal_service import buat_dan_simpan_jadwal, JadwalInfeasibleError
from ai_chat_input import proses_pesan, reset_percakapan
from dotenv import load_dotenv

load_dotenv()

ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")  

app = FastAPI(title="ChronoStudy API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    db.init_db()


# ──────────────────────────────────────────────────────────
# AUTH
# ──────────────────────────────────────────────────────────

@app.post("/api/auth/register")
def register(payload: RegisterRequest):
    ok, msg = db.register_user(payload.nama, payload.email, payload.password)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"message": msg}


@app.post("/api/auth/login")
def login(payload: LoginRequest):
    user = db.verify_login(payload.email, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Email atau password salah.")

    token = generate_token()
    db.create_session(token, user["id"])

    return {
        "token": token,
        "user": {
            "id": user["id"],
            "nama": user["nama"],
            "email": user["email"],
            "skor_meq": user["skor_meq"],
            "kronotipe": user["kronotipe"],
        }
    }


@app.post("/api/auth/logout")
def logout(authorization: str | None = None, user=Depends(get_current_user)):
    # token diambil ulang dari header di get_current_user; untuk hapus sesi simpel:
    return {"message": "Logout berhasil. Hapus token di sisi client."}


@app.get("/api/auth/me")
def me(user=Depends(get_current_user)):
    return {
        "id": user["id"],
        "nama": user["nama"],
        "email": user["email"],
        "skor_meq": user["skor_meq"],
        "kronotipe": user["kronotipe"],
    }


# ──────────────────────────────────────────────────────────
# MEQ
# ──────────────────────────────────────────────────────────

@app.get("/api/meq/questions")
def get_meq_questions():
    return [
        {"kode": kode, "pertanyaan": teks, "opsi": opsi}
        for kode, teks, opsi, _ in MEQ_QUESTIONS
    ]


@app.post("/api/meq/submit")
def submit_meq(payload: MEQSubmit, user=Depends(get_current_user)):
    skor_map = {kode: skor_list for kode, _, _, skor_list in MEQ_QUESTIONS}

    if len(payload.jawaban) != len(MEQ_QUESTIONS):
        raise HTTPException(status_code=400, detail="Semua pertanyaan harus dijawab.")

    total = 0
    for jwb in payload.jawaban:
        if jwb.kode not in skor_map:
            raise HTTPException(status_code=400, detail=f"Kode pertanyaan tidak valid: {jwb.kode}")
        opsi_list = skor_map[jwb.kode]
        if jwb.jawaban_index < 0 or jwb.jawaban_index >= len(opsi_list):
            raise HTTPException(status_code=400, detail="Index jawaban tidak valid.")
        total += opsi_list[jwb.jawaban_index]

    _, tipe, _, _ = bangun_kurva(total)
    db.update_meq(user["id"], total, tipe)

    return {"skor_meq": total, "kronotipe": tipe}


@app.post("/api/meq/reset")
def reset_meq(user=Depends(get_current_user)):
    db.update_meq(user["id"], None, None)
    return {"message": "MEQ direset, silakan isi ulang."}


# ──────────────────────────────────────────────────────────
# JADWAL
# ──────────────────────────────────────────────────────────

@app.get("/api/jadwal/options")
def get_jadwal_options():
    return {
        "hari": HARI,
        "bloom_options": BLOOM_OPTIONS,
        "jam_options": {k: v for k, v in JAM_OPTIONS.items()},
    }


@app.post("/api/jadwal/generate")
def generate_jadwal(payload: JadwalRequest, user=Depends(get_current_user)):
    if not user["skor_meq"]:
        raise HTTPException(status_code=400, detail="Isi kuesioner MEQ terlebih dahulu.")

    if not payload.hari or not payload.jam_ranges:
        raise HTTPException(status_code=400, detail="Pilih minimal 1 hari dan 1 rentang jam.")
    if not payload.matkul:
        raise HTTPException(status_code=400, detail="Isi minimal 1 mata kuliah.")

    skor = user["skor_meq"]
    kurva, tipe, kelas, emoji = bangun_kurva(skor)

    hari_idx_map = {h: i for i, h in enumerate(HARI)}
    jam_list = sorted(set(
        j for r in payload.jam_ranges for j in JAM_OPTIONS.get(r, [])
    ))
    if not jam_list:
        raise HTTPException(status_code=400, detail="Rentang jam tidak valid.")

    ketersediaan = {hari_idx_map[h]: jam_list for h in payload.hari if h in hari_idx_map}
    slots = [(h, j) for h, jl in ketersediaan.items() for j in jl]

    bobot = {m.nama: m.bloom / 6.0 for m in payload.matkul}
    sesi = [m.nama for m in payload.matkul for _ in range(m.sesi)]

    if len(sesi) > len(slots):
        raise HTTPException(
            status_code=400,
            detail="Jumlah sesi melebihi slot waktu yang tersedia. Tambah hari/jam atau kurangi sesi."
        )

    # Setiap library dijalankan 10 kali (masing-masing 50 generasi) dan
    # diambil hasil dengan fitness terbaik, supaya hasil di produksi tidak
    # bergantung pada satu kali run yang bisa saja terjebak local optimum
    # (lihat subbab 3.8.3 poin ketiga soal sensitivitas DEAP terhadap
    # inisialisasi acak).
    sol_p, fit_p, dur_p, riwayat_p = run_pygad_terbaik(sesi, slots, kurva, bobot, gen=50, pengulangan=10)
    sol_d, fit_d, dur_d, riwayat_d = run_deap_terbaik(sesi, slots, kurva, bobot, gen=50, pengulangan=10)

    pemenang = "PyGAD" if fit_p >= fit_d else "DEAP"
    best_sol = sol_p if fit_p >= fit_d else sol_d

    jadwal = susun_jadwal(best_sol, sesi, slots, kurva, bobot, HARI)
    
    input_data = {
        "hari": payload.hari,
        "jam_ranges": payload.jam_ranges,
        "matkul": [m.dict() for m in payload.matkul],
    }

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
    }


@app.get("/api/jadwal/terakhir")
def jadwal_terakhir(user=Depends(get_current_user)):
    hasil = db.ambil_hasil_terakhir(user["id"])
    if not hasil:
        raise HTTPException(status_code=404, detail="Belum ada jadwal yang dibuat.")

    import json
    jadwal = json.loads(hasil["jadwal_json"])
    kurva, tipe, _, _ = bangun_kurva(hasil["skor_meq"])

    return {
        "hasil_id": hasil["id"],
        "kronotipe": hasil["kronotipe"],
        "skor_meq": hasil["skor_meq"],
        "jadwal": jadwal,
        "kurva": kurva.tolist(),
        "hari_order": HARI,
        "created": hasil["created"],
    }


@app.get("/api/jadwal/riwayat")
def jadwal_riwayat(user=Depends(get_current_user)):
    """Daftar ringkas semua jadwal yang pernah dibuat user ini, terbaru duluan."""
    return db.ambil_riwayat(user["id"])


@app.get("/api/jadwal/riwayat/{hasil_id}")
def jadwal_riwayat_detail(hasil_id: int, user=Depends(get_current_user)):
    """Detail lengkap 1 jadwal dari riwayat -- formatnya sama persis dengan
    /api/jadwal/terakhir, supaya bisa dipakai ulang oleh result.html."""
    hasil = db.ambil_hasil_by_id(hasil_id, user["id"])  # sudah scoped ke user_id, aman dari orang lain nebak ID
    if not hasil:
        raise HTTPException(status_code=404, detail="Jadwal tidak ditemukan.")

    import json
    jadwal = json.loads(hasil["jadwal_json"])
    kurva, tipe, _, _ = bangun_kurva(hasil["skor_meq"])

    return {
        "hasil_id": hasil["id"],
        "kronotipe": hasil["kronotipe"],
        "skor_meq": hasil["skor_meq"],
        "jadwal": jadwal,
        "kurva": kurva.tolist(),
        "hari_order": HARI,
        "created": hasil["created"],
    }


@app.get("/api/jadwal/harian/{hari}")
def jadwal_harian(hari: str, user=Depends(get_current_user)):
    hasil = db.ambil_hasil_terakhir(user["id"])
    if not hasil:
        raise HTTPException(status_code=404, detail="Belum ada jadwal yang dibuat.")

    import json
    jadwal = json.loads(hasil["jadwal_json"])

    if hari not in jadwal:
        return {"hari": hari, "sesi": []}

    sesi_list = sorted(jadwal[hari])
    return {
        "hari": hari,
        "sesi": [
            {"jam": j, "matkul": mk, "energi": en, "bloom": bl}
            for j, mk, en, bl in sesi_list
        ]
    }


@app.get("/api/jadwal/pdf")
def download_pdf(user=Depends(get_current_user)):
    hasil = db.ambil_hasil_terakhir(user["id"])
    if not hasil:
        raise HTTPException(status_code=404, detail="Belum ada jadwal yang dibuat.")

    import json
    jadwal = json.loads(hasil["jadwal_json"])

    pdf_bytes = generate_schedule_pdf(
        nama=user["nama"],
        kronotipe=hasil["kronotipe"],
        skor_meq=hasil["skor_meq"],
        jadwal=jadwal,
        hari_order=HARI,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=jadwal_chronostudy.pdf"}
    )


# ──────────────────────────────────────────────────────────
# CHATBOT
# ──────────────────────────────────────────────────────────

@app.post("/api/chat")
def chat(payload: ChatMessage):
    reply = get_bot_reply(payload.message)
    return {"reply": reply}


@app.post("/api/chat/ai-input")
def chat_ai_input(payload: ChatMessage, user=Depends(get_current_user)):
    """
    Chatbot AI (Claude API) buat membuat jadwal lewat percakapan bahasa natural.
    Beda dari /api/chat (rule-based, cuma FAQ) -- endpoint ini mengumpulkan
    data mata kuliah + hari + jam lewat obrolan, lalu langsung generate jadwal
    begitu semua data lengkap dan feasible.
    """
    if not user["skor_meq"]:
        raise HTTPException(status_code=400, detail="Isi kuesioner MEQ terlebih dahulu.")
    try:
        return proses_pesan(user, payload.message)
    except Exception as e:
        import traceback
        traceback.print_exc()  # cetak traceback lengkap ke terminal server buat debug
        raise HTTPException(status_code=500, detail=f"Gagal memproses pesan: {e}")


@app.post("/api/chat/ai-input/reset")
def chat_ai_input_reset(user=Depends(get_current_user)):
    reset_percakapan(user["id"])
    return {"message": "Percakapan direset, mulai obrolan baru."}


# ──────────────────────────────────────────────────────────
# ADMIN
# ──────────────────────────────────────────────────────────

_admin_tokens: set[str] = set()


@app.post("/api/admin/login")
def admin_login(payload: AdminLogin):
    if payload.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Password admin salah.")
    token = generate_token()
    _admin_tokens.add(token)
    return {"admin_token": token}


@app.get("/api/admin/hasil")
def admin_hasil(x_admin_token: str | None = Header(default=None)):
    if not x_admin_token or x_admin_token not in _admin_tokens:
        raise HTTPException(status_code=401, detail="Tidak terautentikasi sebagai admin.")
    return db.ambil_semua_hasil()