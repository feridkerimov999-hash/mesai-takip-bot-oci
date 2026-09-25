import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple

try:
    from .config import DEFAULT_COMPANIES, WORKERS
except ImportError:
    from config import DEFAULT_COMPANIES, WORKERS

def parse_time_range(range_str: str) -> Optional[float]:
    parts = re.split(r'[-–—]', range_str)
    if len(parts) != 2:
        return None
    
    def to_minutes(t_str: str) -> Optional[int]:
        t_str = t_str.strip().replace(".", ":")
        if ":" in t_str:
            h, m = t_str.split(":", 1)
            if h.isdigit() and m.isdigit():
                return int(h) * 60 + int(m)
        elif t_str.isdigit():
            return int(t_str) * 60
        return None

    m1 = to_minutes(parts[0])
    m2 = to_minutes(parts[1])
    if m1 is None or m2 is None:
        return None

    if m2 < m1:
        diff = (24 * 60 - m1) + m2
    else:
        diff = m2 - m1

    return round(diff / 60.0, 2)

def parse_hours_and_date(text: str) -> Tuple[Optional[float], str]:
    raw = text.lower().strip()
    shift_date = datetime.now().date()

    if "dün" in raw or "dun" in raw:
        shift_date = shift_date - timedelta(days=1)
        raw = raw.replace("dün", "").replace("dun", "").strip()

    date_match = re.search(r'\b(\d{1,2})[./](\d{1,2})\b', raw)
    if date_match:
        try:
            day = int(date_match.group(1))
            month = int(date_match.group(2))
            shift_date = shift_date.replace(month=month, day=day)
            raw = raw.replace(date_match.group(0), "").strip()
        except ValueError:
            pass

    date_str = shift_date.strftime("%Y-%m-%d")

    range_match = re.search(r'\b(\d{1,2}(?::\d{2})?\s*[-–—]\s*\d{1,2}(?::\d{2})?)\b', raw)
    if range_match:
        calc_dur = parse_time_range(range_match.group(1))
        if calc_dur and calc_dur > 0:
            return calc_dur, date_str

    hm_match = re.search(r'(\d+)\s*(?:saat|sa|s)\s*(\d+)\s*(?:dakika|dak|dk|d)\b', raw)
    if hm_match:
        h = int(hm_match.group(1))
        m = int(hm_match.group(2))
        return round(h + (m / 60.0), 2), date_str

    m_only = re.search(r'\b(\d+)\s*(?:dakika|dak|dk)\b', raw)
    if m_only:
        m = int(m_only.group(1))
        return round(m / 60.0, 2), date_str

    num_match = re.search(r'\b(\d+(?:[.,]\d+)?)\b', raw)
    if num_match:
        try:
            val = float(num_match.group(1).replace(",", "."))
            if 0 < val <= 24:
                return round(val, 2), date_str
        except ValueError:
            pass

    return None, date_str

def parse_shift_message(text: str, default_worker: Optional[str] = None) -> Optional[Dict[str, Any]]:
    raw_cleaned = text.lower().strip()
    words = raw_cleaned.split()
    if not words:
        return None

    shift_date = datetime.now().date()
    if "dün" in raw_cleaned or "dun" in raw_cleaned:
        shift_date = shift_date - timedelta(days=1)
        raw_cleaned = raw_cleaned.replace("dün", "").replace("dun", "").strip()
    
    date_match = re.search(r'\b(\d{1,2})[./](\d{1,2})\b', raw_cleaned)
    if date_match:
        day = int(date_match.group(1))
        month = int(date_match.group(2))
        try:
            shift_date = shift_date.replace(month=month, day=day)
            raw_cleaned = raw_cleaned.replace(date_match.group(0), "").strip()
        except ValueError:
            pass

    date_str = shift_date.strftime("%Y-%m-%d")

    detected_worker = None
    if "erkan" in raw_cleaned:
        detected_worker = "erkan"
    elif "mirza" in raw_cleaned:
        detected_worker = "mirza"
    elif default_worker and default_worker.lower() in WORKERS:
        detected_worker = default_worker.lower()

    if not detected_worker:
        return None

    duration = None

    range_match = re.search(r'\b(\d{1,2}(?::\d{2})?\s*[-–—]\s*\d{1,2}(?::\d{2})?)\b', raw_cleaned)
    if range_match:
        calc_dur = parse_time_range(range_match.group(1))
        if calc_dur and calc_dur > 0:
            duration = calc_dur
            raw_cleaned = raw_cleaned.replace(range_match.group(0), "").strip()

    if duration is None:
        hm_match = re.search(r'(\d+)\s*(?:saat|sa|s)\s*(\d+)\s*(?:dakika|dak|dk|d)\b', raw_cleaned)
        if hm_match:
            h = int(hm_match.group(1))
            m = int(hm_match.group(2))
            duration = round(h + (m / 60.0), 2)
            raw_cleaned = raw_cleaned.replace(hm_match.group(0), "").strip()

    if duration is None:
        m_only = re.search(r'\b(\d+)\s*(?:dakika|dak|dk)\b', raw_cleaned)
        if m_only:
            m = int(m_only.group(1))
            duration = round(m / 60.0, 2)
            raw_cleaned = raw_cleaned.replace(m_only.group(0), "").strip()

    if duration is None:
        hour_match = re.search(r'\b(\d+(?:[.,]\d+)?)\s*(?:saat|sa|h)?\b', raw_cleaned)
        if hour_match:
            try:
                num_str = hour_match.group(1).replace(",", ".")
                duration = round(float(num_str), 2)
            except ValueError:
                pass

    if not duration or duration <= 0 or duration > 24:
        return None

    company_key = None
    if "panter" in raw_cleaned:
        company_key = "panter"
    elif "medo" in raw_cleaned or "medobet" in raw_cleaned:
        company_key = "medobet"
    elif "mito" in raw_cleaned or "mitobet" in raw_cleaned:
        company_key = "mito"

    if not company_key:
        return None

    return {
        "worker_name": detected_worker,
        "company_key": company_key,
        "shift_date": date_str,
        "duration_hours": duration,
        "raw_text": text
    }

TURKISH_MONTH_NAMES = {
    "ocak": 1, "şubat": 2, "subat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "mayis": 5,
    "haziran": 6, "temmuz": 7, "ağustos": 8, "agustos": 8, "eylül": 9, "eylul": 9,
    "ekim": 10, "kasım": 11, "kasim": 11, "aralık": 12, "aralik": 12
}

def parse_date_range(text: str) -> Optional[Tuple[str, str, str]]:
    raw = text.lower().strip()
    
    m1 = re.search(r'(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?\s*[-–—]\s*(\d{1,2})[./](\d{1,2})(?:[./](\d{2,4}))?', raw)
    if m1:
        d1, m1_m, y1_raw, d2, m2_m, y2_raw = m1.groups()
        current_year = datetime.now().year
        y1 = int(y1_raw) if y1_raw else current_year
        y2 = int(y2_raw) if y2_raw else current_year
        if y1 < 100: y1 += 2000
        if y2 < 100: y2 += 2000

        try:
            start_dt = datetime(y1, int(m1_m), int(d1)).date()
            end_dt = datetime(y2, int(m2_m), int(d2)).date()
            if start_dt > end_dt and not y2_raw:
                end_dt = datetime(y1 + 1, int(m2_m), int(d2)).date()
            label = f"{start_dt.strftime('%d.%m.%Y')} - {end_dt.strftime('%d.%m.%Y')}"
            return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"), label
        except ValueError:
            pass

    m2 = re.search(r'(\d{1,2})\s*([a-zçğıöşü]+)\s*[-–—]\s*(\d{1,2})\s*([a-zçğıöşü]+)', raw)
    if m2:
        d1, mon1, d2, mon2 = m2.groups()
        if mon1 in TURKISH_MONTH_NAMES and mon2 in TURKISH_MONTH_NAMES:
            current_year = datetime.now().year
            try:
                start_dt = datetime(current_year, TURKISH_MONTH_NAMES[mon1], int(d1)).date()
                end_year = current_year
                if TURKISH_MONTH_NAMES[mon2] < TURKISH_MONTH_NAMES[mon1]:
                    end_year += 1
                end_dt = datetime(end_year, TURKISH_MONTH_NAMES[mon2], int(d2)).date()
                label = f"{start_dt.strftime('%d.%m.%Y')} - {end_dt.strftime('%d.%m.%Y')}"
                return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d"), label
            except ValueError:
                pass

    return None
