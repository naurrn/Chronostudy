"""
ai_chat_input.py
================
Chatbot berbasis Groq (Llama 3.3 70B) yang mengumpulkan data jadwal belajar
(mata kuliah + tingkat kesulitan + jumlah sesi + hari/jam tersedia) lewat
percakapan bahasa natural, lalu otomatis memicu pembuatan jadwal begitu
semua data terkumpul DAN feasible (jumlah sesi <= slot waktu tersedia).

SETUP:
    1. pip install groq python-dotenv
    2. Buat file .env yang berisi: GROQ_API_KEY=gsk_...
"""

import os
import json
from groq import Groq
from dotenv import load_dotenv
from constants import HARI, JAM_OPTIONS
from jadwal_service import buat_dan_simpan_jadwal, JadwalInfeasibleError

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))
MODEL = "llama-3.3-70b-versatile"

_riwayat_chat: dict[int, list[dict]] = {}   # user_id -> list[dict]
JAM_LABELS = list(JAM_OPTIONS.keys())

SYSTEM_PROMPT = f"""
Kamu adalah asisten ChronoStudy yang membantu mahasiswa membuat jadwal belajar mingguan.

Gunakan Bahasa Indonesia yang santai, singkat (maksimal 2 kalimat setiap balasan), dan jangan meminta lebih dari SATU informasi dalam satu waktu.

ATURAN PENTING

1. Ikuti urutan percakapan berikut dan JANGAN melompat ke langkah berikutnya sebelum langkah saat ini selesai.

Urutan:
- Mata kuliah
- Bloom
- Jumlah sesi
- Mata kuliah berikutnya (jika ada)
- Hari
- Jam
- Konfirmasi
- Submit

2. Jika pengguna menyebutkan beberapa mata kuliah sekaligus, misalnya:
"Desain, Leadership, AI"

anggap itu sebagai beberapa mata kuliah yang berbeda.

Simpan urutannya, lalu tanyakan informasi SATU PER SATU sesuai urutan.

Contoh:

User:
Desain, Leadership

Assistant:
Baik, ada 2 mata kuliah.

Sekarang untuk mata kuliah Desain,

Tanyakan dengan bahasa natural, dan SELALU format daftar opsinya dengan baris
baru per opsi (jangan digabung jadi satu kalimat panjang), contoh persis
seperti ini:

Buat lulus mata kuliah ini, kamu paling sering:

(a) menghafal istilah/rumus
(b) menjelaskan ulang
(c) menerapkan rumus ke soal baru
(d) membandingkan atau mengurai konsep
(e) menilai atau mengkritisi
(f) membuat karya/proyek

Pilih salah satu huruf.

Setelah pengguna menjawab, tanyakan jumlah sesi untuk Desain.

Setelah Desain selesai, BARU lanjut ke Leadership.

Jangan pernah menanyakan Bloom untuk dua mata kuliah sekaligus.

Jangan pernah menggabungkan dua mata kuliah menjadi satu.

3. Setelah seluruh mata kuliah selesai, baru tanyakan:

"Hari apa saja kamu bisa belajar?"

Pilihan hari:
{HARI}

4. Setelah hari selesai, baru tanyakan jam belajar.

Pilihan jam:
{JAM_LABELS}

5. Setelah semua data lengkap:

- hitung total sesi
- hitung total slot (hari × jumlah jam)

Jika total sesi lebih besar daripada total slot:

beritahu pengguna bahwa jadwal tidak memungkinkan dan minta menambah hari/jam atau mengurangi sesi.

Jangan memanggil submit_jadwal_input.

6. Jika feasible:

Tampilkan ringkasan:

- daftar mata kuliah
- level Bloom
- jumlah sesi
- hari
- jam

Lalu tanyakan:

"Apakah semua data sudah benar?"

HANYA jika pengguna menjawab "ya", "sudah", "benar", atau jawaban setara, panggil submit_jadwal_input.


ATURAN TAMBAHAN

- Jangan mengulang pertanyaan yang sudah dijawab.
- Jangan meminta semua data sekaligus.
- Jangan menebak jawaban pengguna.
- Selalu tunggu jawaban sebelum berpindah ke langkah berikutnya.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
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
                        "description": "Hari-hari yang dipilih pengguna untuk belajar."
                    },
                    "jam_ranges": {
                        "type": "array",
                        "items": {"type": "string", "enum": JAM_LABELS},
                        "description": "Kategori rentang jam yang dipilih pengguna."
                    },
                    "matkul": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "nama": {"type": "string"},
                                "bloom": {"type": "integer"},
                                "sesi": {"type": "integer"}
                            },
                            "required": ["nama", "bloom", "sesi"]
                        }
                    }
                },
                "required": ["hari", "jam_ranges", "matkul"]
            }
        }
    }
]


def reset_percakapan(user_id: int) -> None:
    """Hapus riwayat percakapan dan mulai dengan system prompt baru."""
    _riwayat_chat[user_id] = [{"role": "system", "content": SYSTEM_PROMPT}]


def proses_pesan(user: dict, pesan: str) -> dict:
    """
    Proses satu pesan dari pengguna.
    Return: {"reply": str, "selesai": bool, "jadwal": dict | None}
    """
    user_id = user["id"]

    # Inisialisasi riwayat jika belum ada (termasuk system prompt)
    if user_id not in _riwayat_chat:
        reset_percakapan(user_id)
    riwayat = _riwayat_chat[user_id]

    # Tambahkan pesan pengguna ke riwayat
    riwayat.append({"role": "user", "content": pesan})

    try:
        # Panggil Groq dengan tools
        response = client.chat.completions.create(
            model=MODEL,
            messages=riwayat,
            tools=TOOLS,
            tool_choice="auto",
            temperature=0.3
        )
    except Exception as e:
        print("❌ Groq API error:", e)
        return {
            "reply": "Maaf, ada gangguan teknis nih. Coba ulangi lagi ya.",
            "selesai": False,
            "jadwal": None
        }

    assistant_msg = response.choices[0].message
    # Simpan pesan assistant sebagai dict untuk kompatibilitas riwayat
    riwayat.append(assistant_msg.model_dump(exclude_none=True))

    # Jika model memutuskan memanggil sebuah fungsi (tool)
    if assistant_msg.tool_calls:
        tool_call = assistant_msg.tool_calls[0]
        function_name = tool_call.function.name
        function_args = json.loads(tool_call.function.arguments)

        if function_name == "submit_jadwal_input":
            try:
                hasil = buat_dan_simpan_jadwal(
                    user,
                    function_args["hari"],
                    function_args["jam_ranges"],
                    function_args["matkul"]
                )
                # Sukses
                tool_result = json.dumps({
                    "success": True,
                    "kronotipe": hasil["kronotipe"]
                })
                selesai = True
                jadwal = hasil
            except JadwalInfeasibleError as e:
                # Data tidak feasible
                tool_result = json.dumps({
                    "error": "infeasible",
                    "message": (
                        f"Jumlah sesi ({e.jumlah_sesi}) melebihi "
                        f"slot yang tersedia ({e.jumlah_slot})."
                    )
                })
                selesai = False
                jadwal = None

            # Kirim hasil tool ke model untuk mendapat respons natural
            riwayat.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": tool_result
            })

            try:
                response2 = client.chat.completions.create(
                    model=MODEL,
                    messages=riwayat,
                    temperature=0.3
                )
            except Exception:
                # Fallback jika panggilan kedua gagal
                riwayat.append({"role": "assistant", "content": "Jadwal berhasil dibuat! Cek tab jadwal ya."})
                return {"reply": "Jadwal berhasil dibuat! Cek tab jadwal ya.", "selesai": selesai, "jadwal": jadwal}

            final_msg = response2.choices[0].message.content
            riwayat.append({"role": "assistant", "content": final_msg})

            return {"reply": final_msg, "selesai": selesai, "jadwal": jadwal}

    # Tidak ada tool call → balasan teks biasa
    return {
        "reply": assistant_msg.content,
        "selesai": False,
        "jadwal": None
    }
