import os
from dotenv import load_dotenv
load_dotenv()

from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ.get("GEMINI_API_KEY"))

SYSTEM_PROMPT = """Kamu adalah ChronoBot, asisten virtual untuk aplikasi ChronoStudy —
sistem penjadwalan belajar berbasis ritme sirkadian dan algoritma genetika.

Bantu pengguna memahami:
- Kronotipe dan kuesioner MEQ (Morningness-Eveningness Questionnaire)
- Ritme sirkadian dan pengaruhnya terhadap performa belajar
- Taksonomi Bloom dan bagaimana sistem memakainya untuk menyusun jadwal
- Cara memakai aplikasi ChronoStudy (daftar, isi kuesioner, buat jadwal, Pomodoro, ekspor jadwal, dsb.)

Jawab singkat (maksimal 3-4 kalimat), ramah, dan pakai Bahasa Indonesia santai.
Kalau ditanya di luar topik ChronoStudy, arahkan pengguna kembali dengan sopan."""

def get_bot_reply(pesan: str) -> str:
    try:
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=pesan,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=300,
            ),
        )
        return response.text
    except Exception as e:
        print("ERROR CHATBOT:", e)
        return "Maaf, ChronoBot lagi ada gangguan sebentar. Coba tanya lagi beberapa saat lagi ya!"