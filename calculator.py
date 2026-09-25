from datetime import date, datetime, timedelta
import calendar
from typing import List, Dict, Any, Tuple, Optional

try:
    from .config import DEFAULT_COMPANIES, WORKERS
except ImportError:
    from config import DEFAULT_COMPANIES, WORKERS

TURKISH_MONTHS_SHORT = ["", "Oca", "Şub", "Mar", "Nis", "May", "Haz", "Tem", "Ağu", "Eyl", "Eki", "Kas", "Ara"]
TURKISH_MONTHS_FULL = ["", "Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

def get_company_period_dates(cutoff_day: int, target_period: str = "current", ref_date: Optional[date] = None) -> Tuple[date, date, str]:
    """
    Belirli bir firmanın hesap kesim gününe göre aktif veya önceki dönem tarih aralığını hesaplar.
    """
    if ref_date is None:
        ref_date = datetime.now().date()
        
    cutoff_day = max(1, min(28, cutoff_day))

    # 1. Normal Takvim Ayı (Kesim günü 1 ise)
    if cutoff_day == 1:
        if target_period == "current":
            year = ref_date.year
            month = ref_date.month
        else: # previous
            if ref_date.month == 1:
                year = ref_date.year - 1
                month = 12
            else:
                year = ref_date.year
                month = ref_date.month - 1
        
        last_day = calendar.monthrange(year, month)[1]
        start_d = date(year, month, 1)
        end_d = date(year, month, last_day)
        label = f"1 - {last_day} {TURKISH_MONTHS_FULL[month]} {year}"
        return start_d, end_d, label

    # 2. Ayın Ortasındaki Kesim Günü (örn: 15 veya 20)
    if ref_date.day >= cutoff_day:
        curr_start_year = ref_date.year
        curr_start_month = ref_date.month
    else:
        if ref_date.month == 1:
            curr_start_year = ref_date.year - 1
            curr_start_month = 12
        else:
            curr_start_year = ref_date.year
            curr_start_month = ref_date.month - 1

    if target_period == "current":
        start_year = curr_start_year
        start_month = curr_start_month
    else: # previous
        if curr_start_month == 1:
            start_year = curr_start_year - 1
            start_month = 12
        else:
            start_year = curr_start_year
            start_month = curr_start_month - 1

    start_d = date(start_year, start_month, cutoff_day)

    # Bitiş tarihi: bir sonraki ayın (cutoff_day - 1)'i
    if start_month == 12:
        end_year = start_year + 1
        end_month = 1
    else:
        end_year = start_year
        end_month = start_month + 1

    end_d = date(end_year, end_month, cutoff_day - 1)
    
    label = f"{start_d.day} {TURKISH_MONTHS_SHORT[start_d.month]} - {end_d.day} {TURKISH_MONTHS_SHORT[end_d.month]} {end_d.year}"
    return start_d, end_d, label

def calculate_monthly_summary(shifts: List[Dict[str, Any]], companies: Dict[str, Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Sadece çalışma saatlerini kişi ve firma bazında toplar.
    Maaş veya ücret hesabı yapmaz.
    """
    if companies is None:
        companies = DEFAULT_COMPANIES

    worker_totals = {w: 0.0 for w in WORKERS}
    worker_by_company = {w: {c: 0.0 for c in companies} for w in WORKERS}
    company_totals = {c: 0.0 for c in companies}

    for s in shifts:
        w = s["worker_name"].lower()
        c = s["company_key"].lower()
        hrs = float(s["duration_hours"])

        if w not in worker_totals:
            worker_totals[w] = 0.0
            worker_by_company[w] = {comp: 0.0 for comp in companies}

        if c not in company_totals:
            company_totals[c] = 0.0
            for wrk in worker_by_company:
                worker_by_company[wrk][c] = 0.0

        worker_totals[w] += hrs
        worker_by_company[w][c] += hrs
        company_totals[c] += hrs

    return {
        "worker_totals": worker_totals,
        "worker_by_company": worker_by_company,
        "company_totals": company_totals,
        "total_shifts": len(shifts),
        "total_hours": sum(worker_totals.values())
    }
