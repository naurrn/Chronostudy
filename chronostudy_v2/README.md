# ChronoStudy v2 — FastAPI + Tailwind

## Struktur
```
backend/   → FastAPI (GA, auth, DB, PDF)
frontend/  → HTML + Tailwind CSS + Vanilla JS
```

## Cara Menjalankan

### 1. Backend
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000
```
API docs: http://localhost:8000/docs

### 2. Frontend
Buka langsung di browser (double-click `frontend/index.html`)
atau serve dengan:
```bash
cd frontend
python -m http.server 3000
# Buka http://localhost:3000
```

## Halaman
- `index.html`  → Landing + chatbot
- `auth.html`   → Login / Daftar
- `meq.html`    → Kuesioner kronotipe (sekali isi)
- `input.html`  → Input hari, jam, mata kuliah
- `result.html` → Rekomendasi jadwal (mingguan + harian + download PDF)
- `admin.html`  → Panel admin (data komparasi PyGAD vs DEAP)

