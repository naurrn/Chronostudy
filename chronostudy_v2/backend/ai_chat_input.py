"""
ai_chat_input.py  (versi GEMINI)
=================================
Chatbot berbasis Gemini API (Google) yang mengumpulkan data jadwal belajar
(mata kuliah + tingkat kesulitan + jumlah sesi + hari/jam tersedia) lewat
percakapan bahasa natural, lalu otomatis memicu pembuatan jadwal begitu
semua data terkumpul DAN feasible (jumlah sesi <= slot waktu tersedia).

SETUP:
    1. pip install google-genai
       (SDK resmi terbaru Google per 2026 -- BUKAN google-generativeai yang lama,
       itu sudah digantikan)
    2. Set environment variable GEMINI_API_KEY sebelum menjalankan server:
           export GEMINI_API_KEY="AIza..."
       (dapatkan API key gratis di aistudio.google.com/apikey)

CATATAN DESAIN:
    - Riwayat percakapan disimpan in-memory per user_id (_riwayat_chat).
      Cukup untuk skripsi/demo; untuk produksi sungguhan sebaiknya dipindah
      ke database/redis supaya tidak hilang saat server restart.
    - Kelayakan jadwal (jumlah sesi vs slot) TETAP divalidasi ulang di sisi
      server (lewat jadwal_service.buat_dan_simpan_jadwal), bukan cuma
      dipercayakan ke perhitungan model.
    - Model Gemini 2.5 menyisipkan bagian "thought" (penalaran internal) di
      response.parts -- ini SENGAJA di-skip saat ekstraksi teks/tool call,
      karena bukan bagian dari balasan yang mau ditampilkan ke pengguna.
"""

import os

from google import genai
from google.genai import types

from constants import HARI, JAM_OPTIONS
from jadwal_service import buat_dan_simpan_jadwal, JadwalInfeasibleError

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

# Pakai alias "gemini-flash-latest" -- ini otomatis nunjuk ke versi Flash
# terbaru yang stabil (saat ini Gemini 3.5 Flash), dan Google kasih notice
# 2 minggu sebelum alias ini dialihkan ke model baru. Ini lebih aman buat
# proyek jangka panjang dibanding nulis nama model spesifik yang bisa
# pensiun sewaktu-waktu (kayak gemini-2.5-flash yang sudah tidak tersedia
# buat user baru per Juli 2026). Kalau mau lebih hemat kuota/biaya, bisa
# ganti ke "gemini-3.1-flash-lite".
MODEL = "gemini-3.1-flash-lite"

_riwayat_chat: dict[int, list] = {}  # user_id -> list[types.Content]

JAM_LABELS = list(JAM_OPTIONS.keys())

SYSTEM_PROMPT = f"""Kamu adalah asisten ChronoStudy yang membantu mahasiswa membuat jadwal
belajar mingguan lewat percakapan santai berbahasa Indonesia.

Tugasmu mengumpulkan 3 hal berikut dari pengguna, SATU PER SATU (jangan borong semua
pertanyaan sekaligus, biar terasa natural seperti ngobrol beneran):

1. DAFTAR MATA KULIAH yang mau dijadwalkan. Untuk TIAP mata kuliah, tanyakan:
   a. Tingkat kesulitan -- JANGAN tanya "levelnya berapa (1-6)" atau sebut istilah
      "taksonomi Bloom" ke pengguna. Tanyakan dengan bahasa natural, contoh:
      "Untuk mata kuliah ini, kamu paling banyak dituntut buat apa sih biar bisa lulus
      dengan baik? (a) menghafal istilah/rumus/definisi, (b) menjelaskan ulang konsep
      pakai bahasa sendiri, (c) menerapkan rumus/prosedur ke soal atau kasus baru,
      (d) membandingkan/mengurai beberapa konsep sekaligus, (e) menilai atau
      mengkritisi suatu pendekatan/argumen, atau (f) membuat karya/desain/proyek
      orisinal?"
      Lalu petakan jawabannya ke angka sesuai kamus berikut (JANGAN tampilkan kamus
      atau angka ini ke pengguna, ini cuma referensi internalmu):
        (a) menghafal / definisi dasar             -> bloom = 2
        (b) menjelaskan ulang dengan kata sendiri   -> bloom = 2
        (c) menerapkan ke soal/kasus baru           -> bloom = 3
        (d) membandingkan/mengurai konsep           -> bloom = 4
        (e) menilai/mengkritisi                     -> bloom = 5
        (f) membuat karya/proyek orisinal            -> bloom = 6
   b. Berapa kali per minggu mata kuliah itu perlu dijadwalkan (jumlah sesi, wajar 1-5x).

2. HARI apa saja pengguna punya waktu luang untuk belajar. Pilihan valid HANYA:
   {HARI}

3. JAM berapa saja pengguna biasanya bisa belajar di hari-hari itu. Pilihan valid HANYA
   kategori berikut (boleh pilih lebih dari satu):
   {JAM_LABELS}

ATURAN PENTING SOAL KELAYAKAN JADWAL:
- Sebelum menyimpulkan percakapan, HITUNG dulu total jumlah sesi yang diminta (sesi dari
  semua mata kuliah dijumlahkan) dan bandingkan dengan kapasitas slot yang tersedia
  (jumlah hari terpilih x jumlah jam unik dari kategori jam yang dipilih).
- Kalau jumlah sesi lebih besar dari slot tersedia, JANGAN panggil tool
  submit_jadwal_input. Beri tahu pengguna secara ramah bahwa permintaannya belum bisa
  dijadwalkan tanpa bentrok, sebutkan angka pastinya (butuh berapa sesi vs tersedia
  berapa slot), lalu tanya apakah mau menambah hari/jam atau mengurangi sesi.
- Kalau ragu sudah menghitung dengan benar, lebih baik tanya ulang ke pengguna daripada
  memanggil tool dengan data yang mungkin infeasible.

Begitu SEMUA data (mata kuliah+bloom+sesi, hari, jam) sudah terkumpul, feasible, dan
sudah dikonfirmasi ulang ke pengguna (ringkas singkat lalu tanya "sudah benar semua?"),
barulah panggil tool `submit_jadwal_input` dengan data lengkapnya.

Gunakan bahasa Indonesia yang santai, ramah, dan singkat -- ini obrolan chat, bukan esai.
"""

# Skema tool pakai dict biasa (didukung langsung oleh google-genai lewat
# GenerateContentConfig(tools=[{"function_declarations": [...]}])).
TOOLS_CONFIG = [
    {
        "function_declarations": [
            {
                "name": "submit_jadwal_input",
                "description": (
                    "Kirim data final untuk generate jadwal SETELAH seluruh informasi "
                    "(mata kuliah + bloom + sesi, hari, jam) lengkap, feasible, dan "
                    "sudah dikonfirmasi ulang oleh pengguna."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "hari": {
                            "type": "array",
                            "items": {"type": "string", "enum": HARI},
                            "description": "Hari-hari yang dipilih pengguna untuk belajar.",
                        },
                        "jam_ranges": {
                            "type": "array",
                            "items": {"type": "string", "enum": JAM_LABELS},
                            "description": "Kategori rentang jam yang dipilih pengguna.",
                        },
                        "matkul": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "nama": {"type": "string"},
                                    "bloom": {"type": "integer"},
                                    "sesi": {"type": "integer"},
                                },
                                "required": ["nama", "bloom", "sesi"],
                            },
                        },
                    },
                    "required": ["hari", "jam_ranges", "matkul"],
                },
            }
        ]
    }
]

CONFIG = types.GenerateContentConfig(
    system_instruction=SYSTEM_PROMPT,
    tools=TOOLS_CONFIG,
    # CATATAN: sempat dicoba thinking_level="LOW" untuk mempercepat respons,
    # tapi di beberapa kasus itu bikin model bocorin teks kerangka/scratchpad
    # internalnya (mis. muncul teks aneh kayak "Sentence 3 (Call to Action):")
    # alih-alih jawaban beneran -- kemungkinan reasoning-nya dipangkas
    # kebanyakan sampai keluar jalur. "MEDIUM" jadi titik tengah yang lebih
    # stabil: masih lebih cepat dari default HIGH, tapi nggak se-agresif LOW.
    # Kalau bug serupa masih muncul, coba naikkan ke "HIGH" (default asli,
    # paling stabil tapi paling lambat).
    thinking_config=types.ThinkingConfig(thinking_level="MEDIUM"),
    max_output_tokens=8192,
)


def reset_percakapan(user_id: int) -> None:
    _riwayat_chat[user_id] = []


def _ekstrak_balasan(model_content):
    """Pisahkan function_call vs teks biasa dari satu Content, skip bagian 'thought'."""
    function_call = None
    teks = []
    for part in model_content.parts:
        if getattr(part, "thought", False):
            continue  # bagian penalaran internal Gemini 2.5, bukan buat ditampilkan
        if getattr(part, "function_call", None):
            function_call = part.function_call
        elif getattr(part, "text", None):
            teks.append(part.text)
    return function_call, "\n".join(teks).strip()


def proses_pesan(user: dict, pesan: str) -> dict:
    """
    Proses satu pesan dari pengguna.
    Return: {"reply": str, "selesai": bool, "jadwal": dict | None}
    """
    user_id = user["id"]
    riwayat = _riwayat_chat.setdefault(user_id, [])
    riwayat.append(types.Content(role="user", parts=[types.Part.from_text(text=pesan)]))

    response = client.models.generate_content(
        model=MODEL,
        contents=riwayat,
        config=CONFIG,
    )

    model_content = response.candidates[0].content
    riwayat.append(model_content)

    function_call, reply_text = _ekstrak_balasan(model_content)

    if function_call is None:
        return {"reply": reply_text or "...", "selesai": False, "jadwal": None}

    data = dict(function_call.args)
    try:
        hasil = buat_dan_simpan_jadwal(user, data["hari"], data["jam_ranges"], data["matkul"])
    except JadwalInfeasibleError as e:
        pesan_error = (
            f"Waduh, ternyata jumlah sesi yang diminta ({e.jumlah_sesi}) masih lebih "
            f"banyak dari slot waktu yang tersedia ({e.jumlah_slot}). Mau nambah hari/jam "
            f"dulu, atau kurangi jumlah sesi mata kuliahnya?"
        )
        riwayat.append(types.Content(
            role="user",
            parts=[types.Part.from_function_response(
                name=function_call.name,
                response={"error": pesan_error},
            )],
        ))
        return {"reply": pesan_error, "selesai": False, "jadwal": None}

    riwayat.append(types.Content(
        role="user",
        parts=[types.Part.from_function_response(
            name=function_call.name,
            response={"result": "Jadwal berhasil dibuat dan disimpan."},
        )],
    ))

    konfirmasi = (
        f"{reply_text}\n\nJadwal kamu udah jadi! Kronotipe kamu: {hasil['kronotipe']}. "
        f"Cek tab jadwal buat lihat detailnya ya 😊"
    ).strip()

    return {"reply": konfirmasi, "selesai": True, "jadwal": hasil}