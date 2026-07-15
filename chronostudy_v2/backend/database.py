import sqlite3
import hashlib
import json
from contextlib import contextmanager

DB_PATH = "chronostudy.db"


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=5000;")  # tunggu max 5 detik kalau lagi dikunci, drpd langsung error
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nama        TEXT NOT NULL,
                email       TEXT UNIQUE NOT NULL,
                password    TEXT NOT NULL,
                skor_meq    INTEGER DEFAULT NULL,
                kronotipe   TEXT DEFAULT NULL,
                created     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS hasil (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                skor_meq    INTEGER,
                kronotipe   TEXT,
                jadwal_json TEXT,
                input_json  TEXT,
                fit_pygad   REAL,
                fit_deap    REAL,
                dur_pygad   REAL,
                dur_deap    REAL,
                riwayat_pygad TEXT,
                riwayat_deap  TEXT,
                pemenang    TEXT,
                created     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token       TEXT PRIMARY KEY,
                user_id     INTEGER NOT NULL,
                created     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        """)


def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


# ── USERS ────────────────────────────────────────────────
def register_user(nama: str, email: str, pw: str):
    with get_conn() as conn:
        try:
            c = conn.cursor()
            c.execute(
                "INSERT INTO users (nama, email, password) VALUES (?, ?, ?)",
                (nama, email, hash_pw(pw))
            )
            return True, "Akun berhasil dibuat."
        except sqlite3.IntegrityError:
            return False, "Email sudah terdaftar."


def get_user_by_email(email: str):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE email=?", (email,))
        row = c.fetchone()
        return dict(row) if row else None


def get_user_by_id(user_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE id=?", (user_id,))
        row = c.fetchone()
        return dict(row) if row else None


def verify_login(email: str, pw: str):
    user = get_user_by_email(email)
    if user and user["password"] == hash_pw(pw):
        return user
    return None


def update_meq(user_id: int, skor: int, kronotipe: str | None):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute(
            "UPDATE users SET skor_meq=?, kronotipe=? WHERE id=?",
            (skor, kronotipe, user_id)
        )


# ── SESSIONS (simple token auth) ────────────────────────────
def create_session(token: str, user_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))


def get_user_by_token(token: str):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT u.* FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ?
        """, (token,))
        row = c.fetchone()
        return dict(row) if row else None


def delete_session(token: str):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("DELETE FROM sessions WHERE token=?", (token,))


# ── HASIL / JADWAL ───────────────────────────────────────────
def simpan_hasil(user_id, skor_meq, kronotipe, jadwal, input_data,
                  fit_p, fit_d, dur_p, dur_d, riwayat_p, riwayat_d, pemenang):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO hasil
            (user_id, skor_meq, kronotipe, jadwal_json, input_json,
             fit_pygad, fit_deap, dur_pygad, dur_deap,
             riwayat_pygad, riwayat_deap, pemenang)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, skor_meq, kronotipe, json.dumps(jadwal), json.dumps(input_data),
              fit_p, fit_d, dur_p, dur_d,
              json.dumps(riwayat_p), json.dumps(riwayat_d), pemenang))
        return c.lastrowid


def ambil_hasil_terakhir(user_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT * FROM hasil WHERE user_id=? ORDER BY created DESC LIMIT 1
        """, (user_id,))
        row = c.fetchone()
        return dict(row) if row else None


def ambil_hasil_by_id(hasil_id: int, user_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM hasil WHERE id=? AND user_id=?", (hasil_id, user_id))
        row = c.fetchone()
        return dict(row) if row else None


def ambil_riwayat(user_id: int):
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT id, skor_meq, kronotipe, fit_pygad, fit_deap, pemenang, created
            FROM hasil WHERE user_id=? ORDER BY created DESC
        """, (user_id,))
        return [dict(r) for r in c.fetchall()]


# ── ADMIN ────────────────────────────────────────────────────
def ambil_semua_hasil():
    with get_conn() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT u.nama, u.email, h.skor_meq, h.kronotipe,
                   h.fit_pygad, h.fit_deap, h.dur_pygad, h.dur_deap,
                   h.pemenang, h.created
            FROM hasil h JOIN users u ON h.user_id = u.id
            ORDER BY h.created DESC
        """)
        return [dict(r) for r in c.fetchall()]
