import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

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
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": pesan}
            ],
            max_tokens=300,
            temperature=0.5
        )
        return response.choices[0].message.content
    except Exception as e:
        print("❌ ERROR CHATBOT:", e)
        return "Maaf, ChronoBot lagi ada gangguan sebentar. Coba tanya lagi beberapa saat lagi ya!"
