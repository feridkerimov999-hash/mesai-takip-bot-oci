import sqlite3
from datetime import datetime
from typing import List, Dict, Optional, Any

try:
    from .config import DB_PATH, DEFAULT_COMPANIES
except ImportError:
    from config import DB_PATH, DEFAULT_COMPANIES

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Mesai Kayıtları Tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS shifts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                worker_name TEXT NOT NULL,
                company_key TEXT NOT NULL,
                shift_date TEXT NOT NULL,
                duration_hours REAL NOT NULL,
                raw_text TEXT,
                telegram_user_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. Firmalar Tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS companies (
                key TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                cutoff_day INTEGER DEFAULT 1
            )
        """)
        cursor.execute("PRAGMA table_info(companies)")
        cols = [r[1] for r in cursor.fetchall()]
        if "cutoff_day" not in cols:
            cursor.execute("ALTER TABLE companies ADD COLUMN cutoff_day INTEGER DEFAULT 1")

        # 3. Telegram Kullanıcı Eşleştirme
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_mappings (
                telegram_id INTEGER PRIMARY KEY,
                worker_name TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 4. Canlı Mesai Takip Tablosu
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS active_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER NOT NULL,
                worker_name TEXT NOT NULL,
                company_key TEXT NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT,
                break_start TEXT,
                total_break_seconds INTEGER DEFAULT 0,
                status TEXT DEFAULT 'working'
            )
        """)
        
        for comp_key, info in DEFAULT_COMPANIES.items():
            cursor.execute("""
                INSERT INTO companies (key, display_name, cutoff_day)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    display_name = excluded.display_name,
                    cutoff_day = COALESCE(companies.cutoff_day, excluded.cutoff_day)
            """, (comp_key, info["display_name"], info.get("cutoff_day", 1)))
            
        conn.commit()

def add_shift(worker_name: str, company_key: str, shift_date: str, duration_hours: float, raw_text: str = "", telegram_user_id: Optional[int] = None) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO shifts (worker_name, company_key, shift_date, duration_hours, raw_text, telegram_user_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (worker_name.lower().strip(), company_key.lower().strip(), shift_date, duration_hours, raw_text, telegram_user_id))
        conn.commit()
        return cursor.lastrowid

def delete_shift(shift_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM shifts WHERE id = ?", (shift_id,))
        conn.commit()
        return cursor.rowcount > 0

def reset_all_data() -> Dict[str, int]:
    """Tüm mesai kayıtlarını ve aktif canlı oturumları kalıcı olarak temizler."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM shifts")
        shift_count = cursor.fetchone()[0]
        
        cursor.execute("DELETE FROM shifts")
        cursor.execute("DELETE FROM active_sessions")
        try:
            cursor.execute("DELETE FROM sqlite_sequence WHERE name IN ('shifts', 'active_sessions')")
        except Exception:
            pass
        conn.commit()
        return {"shifts_deleted": shift_count}

def get_last_shift(worker_name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if worker_name:
            cursor.execute("SELECT * FROM shifts WHERE worker_name = ? ORDER BY id DESC LIMIT 1", (worker_name.lower(),))
        else:
            cursor.execute("SELECT * FROM shifts ORDER BY id DESC LIMIT 1")
        row = cursor.fetchone()
        return dict(row) if row else None

def get_shifts_by_month(year_month: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, c.display_name as company_display
            FROM shifts s
            LEFT JOIN companies c ON s.company_key = c.key
            WHERE s.shift_date LIKE ?
            ORDER BY s.shift_date ASC, s.id ASC
        """, (f"{year_month}%",))
        return [dict(row) for row in cursor.fetchall()]

def get_all_shifts() -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, c.display_name as company_display
            FROM shifts s
            LEFT JOIN companies c ON s.company_key = c.key
            ORDER BY s.shift_date ASC, s.id ASC
        """)
        return [dict(row) for row in cursor.fetchall()]

def get_recent_shifts(limit: int = 10) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, c.display_name as company_display
            FROM shifts s
            LEFT JOIN companies c ON s.company_key = c.key
            ORDER BY s.id DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

def set_user_mapping(telegram_id: int, worker_name: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_mappings (telegram_id, worker_name, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(telegram_id) DO UPDATE SET worker_name = excluded.worker_name, updated_at = CURRENT_TIMESTAMP
        """, (telegram_id, worker_name.lower()))
        conn.commit()

def get_worker_by_telegram_id(telegram_id: int) -> Optional[str]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT worker_name FROM user_mappings WHERE telegram_id = ?", (telegram_id,))
        row = cursor.fetchone()
        return row["worker_name"] if row else None

def get_companies() -> Dict[str, Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM companies")
        rows = cursor.fetchall()
        result = {}
        for r in rows:
            result[r["key"]] = {
                "display_name": r["display_name"],
                "cutoff_day": r["cutoff_day"] if "cutoff_day" in r.keys() else 1
            }
        return result

def set_company_cutoff_day(company_key: str, cutoff_day: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE companies SET cutoff_day = ? WHERE key = ?", (cutoff_day, company_key.lower().strip()))
        conn.commit()
        return cursor.rowcount > 0

def get_shifts_for_company_between(company_key: str, start_date_str: str, end_date_str: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, c.display_name as company_display
            FROM shifts s
            LEFT JOIN companies c ON s.company_key = c.key
            WHERE s.company_key = ? AND s.shift_date >= ? AND s.shift_date <= ?
            ORDER BY s.shift_date ASC, s.id ASC
        """, (company_key.lower().strip(), start_date_str, end_date_str))
        return [dict(row) for row in cursor.fetchall()]

def get_active_session(telegram_user_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, c.display_name as company_display
            FROM active_sessions s
            LEFT JOIN companies c ON s.company_key = c.key
            WHERE s.telegram_user_id = ? AND s.status IN ('working', 'break')
            ORDER BY s.id DESC LIMIT 1
        """, (telegram_user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_active_sessions_for_user(telegram_user_id: int) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, c.display_name as company_display
            FROM active_sessions s
            LEFT JOIN companies c ON s.company_key = c.key
            WHERE s.telegram_user_id = ? AND s.status IN ('working', 'break')
            ORDER BY s.id ASC
        """, (telegram_user_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_active_session_by_company(telegram_user_id: int, company_key: str) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, c.display_name as company_display
            FROM active_sessions s
            LEFT JOIN companies c ON s.company_key = c.key
            WHERE s.telegram_user_id = ? AND s.company_key = ? AND s.status IN ('working', 'break')
            ORDER BY s.id DESC LIMIT 1
        """, (telegram_user_id, company_key.lower().strip()))
        row = cursor.fetchone()
        return dict(row) if row else None

def start_break_for_user(telegram_user_id: int) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            UPDATE active_sessions 
            SET status = 'break', break_start = ?
            WHERE telegram_user_id = ? AND status = 'working'
        """, (now_str, telegram_user_id))
        conn.commit()
        return cursor.rowcount

def end_break_for_user(telegram_user_id: int) -> int:
    sessions = get_active_sessions_for_user(telegram_user_id)
    count = 0
    for s in sessions:
        if s["status"] == "break":
            end_break(s["id"])
            count += 1
    return count

def finish_all_sessions_for_user(telegram_user_id: int) -> List[Dict[str, Any]]:
    sessions = get_active_sessions_for_user(telegram_user_id)
    finished_list = []
    for s in sessions:
        fin = finish_session(s["id"])
        if fin:
            finished_list.append(fin)
    return finished_list

def start_session(telegram_user_id: int, worker_name: str, company_key: str) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            INSERT INTO active_sessions (telegram_user_id, worker_name, company_key, start_time, status)
            VALUES (?, ?, ?, ?, 'working')
        """, (telegram_user_id, worker_name.lower().strip(), company_key.lower().strip(), now_str))
        conn.commit()
        return cursor.lastrowid

def start_break(session_id: int) -> bool:
    with get_connection() as conn:
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            UPDATE active_sessions 
            SET status = 'break', break_start = ?
            WHERE id = ? AND status = 'working'
        """, (now_str, session_id))
        conn.commit()
        return cursor.rowcount > 0

def end_break(session_id: int) -> Optional[int]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT break_start, total_break_seconds FROM active_sessions WHERE id = ? AND status = 'break'", (session_id,))
        row = cursor.fetchone()
        if not row or not row["break_start"]:
            return None
        
        now = datetime.now()
        b_start = datetime.strptime(row["break_start"], "%Y-%m-%d %H:%M:%S")
        added_break = int((now - b_start).total_seconds())
        new_total = (row["total_break_seconds"] or 0) + added_break
        
        cursor.execute("""
            UPDATE active_sessions
            SET status = 'working', break_start = NULL, total_break_seconds = ?
            WHERE id = ?
        """, (new_total, session_id))
        conn.commit()
        return added_break

def finish_session(session_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, c.display_name as company_display
            FROM active_sessions s
            LEFT JOIN companies c ON s.company_key = c.key
            WHERE s.id = ? AND s.status IN ('working', 'break')
        """, (session_id,))
        row = cursor.fetchone()
        if not row:
            return None
        
        session = dict(row)
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        
        start_dt = datetime.strptime(session["start_time"], "%Y-%m-%d %H:%M:%S")
        gross_seconds = (now - start_dt).total_seconds()
        duration_hours = round(gross_seconds / 3600.0, 2)
        if duration_hours < 0.05 and gross_seconds >= 30:
            duration_hours = 0.05
        
        shift_date = start_dt.strftime("%Y-%m-%d")
        raw_text = f"Canlı: {start_dt.strftime('%H:%M')} - {now.strftime('%H:%M')}"
        
        cursor.execute("""
            INSERT INTO shifts (worker_name, company_key, shift_date, duration_hours, raw_text, telegram_user_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session["worker_name"], session["company_key"], shift_date, duration_hours, raw_text, session["telegram_user_id"]))
        new_shift_id = cursor.lastrowid
        
        total_break = session.get("total_break_seconds", 0) or 0
        cursor.execute("""
            UPDATE active_sessions
            SET status = 'finished', end_time = ?, total_break_seconds = ?
            WHERE id = ?
        """, (now_str, total_break, session_id))
        conn.commit()

        session["end_time"] = now_str
        session["duration_hours"] = duration_hours
        session["total_break_seconds"] = total_break
        session["shift_id"] = new_shift_id
        session["shift_date"] = shift_date
        return session

def get_shifts_by_date(date_str: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, c.display_name as company_display
            FROM shifts s
            LEFT JOIN companies c ON s.company_key = c.key
            WHERE s.shift_date = ?
            ORDER BY s.id ASC
        """, (date_str,))
        return [dict(row) for row in cursor.fetchall()]

def get_shifts_between_dates(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, c.display_name as company_display
            FROM shifts s
            LEFT JOIN companies c ON s.company_key = c.key
            WHERE s.shift_date >= ? AND s.shift_date <= ?
            ORDER BY s.shift_date ASC, s.id ASC
        """, (start_date, end_date))
        return [dict(row) for row in cursor.fetchall()]
