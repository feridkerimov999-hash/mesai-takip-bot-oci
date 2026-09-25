import io
import csv
from datetime import datetime
from typing import Dict, Any, List

def format_hours_nice(hours: float) -> str:
    """Küsüratları net ve anlaşılır gösterir. Örn: 8.25 Saat (8 sa 15 dk) veya 8 Saat"""
    total_mins = int(round(hours * 60))
    h = total_mins // 60
    m = total_mins % 60
    if m == 0:
        return f"{h} Saat"
    elif h == 0:
        return f"{m} dk ({hours:.2f} Saat)"
    else:
        return f"{h} sa {m} dk ({hours:.2f} Saat)"

def format_summary_report(data: Dict[str, Any], period_label: str) -> str:
    worker_totals = data["worker_totals"]
    worker_by_comp = data["worker_by_company"]
    company_totals = data["company_totals"]

    lines = []
    lines.append(f"📊 <b>ÇALIŞMA SAATLERİ RAPORU</b> ({period_label})")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    for w in ["erkan", "mirza"]:
        tot = worker_totals.get(w, 0.0)
        lines.append(f"👤 <b>{w.upper()}:</b> <b>{format_hours_nice(tot)}</b>")
        comps = worker_by_comp.get(w, {})
        for c_key in ["medobet", "mito", "panter"]:
            c_hrs = comps.get(c_key, 0.0)
            c_name = c_key.capitalize()
            lines.append(f"   • {c_name}: <b>{format_hours_nice(c_hrs)}</b>")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("🏢 <b>FİRMA BAZLI TOPLAMLAR:</b>")
    for c_key in ["medobet", "mito", "panter"]:
        tot_c = company_totals.get(c_key, 0.0)
        e_hrs = worker_by_comp.get("erkan", {}).get(c_key, 0.0)
        m_hrs = worker_by_comp.get("mirza", {}).get(c_key, 0.0)
        lines.append(f"• <b>{c_key.capitalize()}:</b> <b>{format_hours_nice(tot_c)}</b> (Erkan: {e_hrs:.2f} sa | Mirza: {m_hrs:.2f} sa)")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"📝 <i>Toplam {data['total_shifts']} kayıt | Genel Toplam: {format_hours_nice(data['total_hours'])}</i>")
    return "\n".join(lines)

def format_shift_added(worker: str, company: str, hours: float, date_str: str) -> str:
    return (
        f"✅ <b>Mesai Kaydedildi!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>Çalışan:</b> {worker.upper()}\n"
        f"🏢 <b>Firma:</b> {company}\n"
        f"⏱️ <b>Süre:</b> <b>{format_hours_nice(hours)}</b>\n"
        f"📅 <b>Tarih:</b> {date_str}"
    )

TURKISH_DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]

def get_day_name(date_str: str) -> str:
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        return TURKISH_DAYS[dt.weekday()]
    except Exception:
        return ""

def format_pay_period_report(companies_data: List[Dict[str, Any]], period_type: str = "current") -> str:
    period_title = "AKTİF MAAŞ VE HESAP DÖNEMİ" if period_type == "current" else "ÖNCEKİ MAAŞ VE HESAP DÖNEMİ"
    lines = []
    lines.append(f"💳 <b>{period_title} RAPORU</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━\n")

    grand_total = 0.0
    worker_grand = {"erkan": 0.0, "mirza": 0.0}

    for comp in companies_data:
        c_name = comp["display_name"]
        p_label = comp["period_label"]
        tot = comp["total_hours"]
        grand_total += tot
        e_hrs = comp["worker_hours"].get("erkan", 0.0)
        m_hrs = comp["worker_hours"].get("mirza", 0.0)
        worker_grand["erkan"] += e_hrs
        worker_grand["mirza"] += m_hrs

        lines.append(f"🏢 <b>{c_name.upper()}</b> <i>({p_label})</i>")
        lines.append(f"   • Firma Toplamı: <b>{format_hours_nice(tot)}</b>")
        lines.append(f"   • Erkan: <b>{format_hours_nice(e_hrs)}</b> | Mirza: <b>{format_hours_nice(m_hrs)}</b>")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("👥 <b>DÖNEMLİK KİŞİ TOPLAMLARI:</b>")
    lines.append(f"👤 <b>ERKAN:</b> <b>{format_hours_nice(worker_grand['erkan'])}</b>")
    lines.append(f"👤 <b>MIRZA:</b> <b>{format_hours_nice(worker_grand['mirza'])}</b>")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━")
    lines.append(f"⏱️ <b>Genel Dönem Toplamı:</b> <b>{format_hours_nice(grand_total)}</b>")
    return "\n".join(lines)

def generate_excel_export(shifts: List[Dict[str, Any]], period_label: str = "") -> tuple:
    clean_period = period_label.replace(" ", "_").lower() if period_label else "rapor"
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Mesai Kayıtları"

        title_font = Font(name="Calibri", size=14, bold=True, color="1F4E79")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
        summary_header_fill = PatternFill(start_color="2F5597", end_color="2F5597", fill_type="solid")
        summary_fill = PatternFill(start_color="D9E1F2", end_color="D9E1F2", fill_type="solid")
        bold_font = Font(name="Calibri", size=11, bold=True)
        center_align = Alignment(horizontal="center", vertical="center")
        right_align = Alignment(horizontal="right", vertical="center")
        left_align = Alignment(horizontal="left", vertical="center")

        thin_border = Border(
            left=Side(style='thin', color='D9D9D9'),
            right=Side(style='thin', color='D9D9D9'),
            top=Side(style='thin', color='D9D9D9'),
            bottom=Side(style='thin', color='D9D9D9')
        )
        double_bottom_border = Border(
            top=Side(style='thin', color='000000'),
            bottom=Side(style='double', color='000000')
        )

        ws.merge_cells("A1:H1")
        title_cell = ws["A1"]
        title_cell.value = f"📊 MESAİ VE ÇALIŞMA SAATLERİ DÖKÜMÜ ({period_label if period_label else 'Tüm Kayıtlar'})"
        title_cell.font = title_font
        title_cell.alignment = Alignment(horizontal="left", vertical="center")
        ws.row_dimensions[1].height = 28

        headers = [
            "Kayıt No", "Tarih", "Gün", "Çalışan", "Site / Firma", "Çalışılan Süre (Saat)", "Giriş Notu / Detay", "Kayıt Zamanı"
        ]
        
        ws.row_dimensions[3].height = 24
        for col_idx, h in enumerate(headers, 1):
            cell = ws.cell(row=3, column=col_idx, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = center_align
            cell.border = thin_border

        row_idx = 4
        total_hours = 0.0
        worker_hours = {"erkan": 0.0, "mirza": 0.0}
        comp_hours = {"medobet": 0.0, "mito": 0.0, "panter": 0.0}
        worker_comp = {
            "erkan": {"medobet": 0.0, "mito": 0.0, "panter": 0.0},
            "mirza": {"medobet": 0.0, "mito": 0.0, "panter": 0.0}
        }

        for s in shifts:
            s_id = s.get("id")
            d_str = s.get("shift_date", "")
            day_name = get_day_name(d_str)
            w_raw = s.get("worker_name", "").lower()
            w_name = w_raw.upper()
            c_key = s.get("company_key", "").lower()
            comp_name = s.get("company_display") or c_key.capitalize()
            hrs = float(s.get("duration_hours", 0.0))
            raw_text = s.get("raw_text", "")
            created_at = str(s.get("created_at", ""))

            total_hours += hrs
            if w_raw in worker_hours:
                worker_hours[w_raw] += hrs
            if c_key in comp_hours:
                comp_hours[c_key] += hrs
            if w_raw in worker_comp and c_key in worker_comp[w_raw]:
                worker_comp[w_raw][c_key] += hrs

            row_data = [f"#{s_id}", d_str, day_name, w_name, comp_name, hrs, raw_text, created_at]

            ws.row_dimensions[row_idx].height = 20
            for col_idx, val in enumerate(row_data, 1):
                cell = ws.cell(row=row_idx, column=col_idx, value=val)
                cell.border = thin_border
                if col_idx in [1, 2, 3, 4, 5]:
                    cell.alignment = center_align
                elif col_idx == 6:
                    cell.alignment = right_align
                    cell.number_format = '0.00'
                else:
                    cell.alignment = left_align
            row_idx += 1

        total_row = row_idx
        ws.row_dimensions[total_row].height = 22
        ws.cell(row=total_row, column=1, value="GENEL TOPLAM").font = bold_font
        ws.merge_cells(start_row=total_row, start_column=1, end_row=total_row, end_column=5)
        for c in range(1, 6):
            ws.cell(row=total_row, column=c).fill = summary_fill
            ws.cell(row=total_row, column=c).border = double_bottom_border
        
        tot_cell = ws.cell(row=total_row, column=6, value=total_hours)
        tot_cell.font = bold_font
        tot_cell.fill = summary_fill
        tot_cell.alignment = right_align
        tot_cell.number_format = '0.00'
        tot_cell.border = double_bottom_border

        for c in range(7, 9):
            ws.cell(row=total_row, column=c).fill = summary_fill
            ws.cell(row=total_row, column=c).border = double_bottom_border
        
        summary_start = total_row + 3
        ws.cell(row=summary_start, column=1, value="📌 ÇALIŞAN & FİRMA ÖZET DAĞILIMI").font = bold_font
        ws.merge_cells(start_row=summary_start, start_column=1, end_row=summary_start, end_column=4)

        sum_headers = ["Kişi / Firma", "Medobet", "Mito", "Panter", "Toplam Saat"]
        sum_hdr_row = summary_start + 1
        ws.row_dimensions[sum_hdr_row].height = 22
        for i, sh in enumerate(sum_headers, 1):
            sc = ws.cell(row=sum_hdr_row, column=i, value=sh)
            sc.font = header_font
            sc.fill = summary_header_fill
            sc.alignment = center_align
            sc.border = thin_border

        curr_r = sum_hdr_row + 1
        for w in ["erkan", "mirza"]:
            w_disp = w.upper()
            m_hrs = worker_comp.get(w, {}).get("medobet", 0.0)
            mi_hrs = worker_comp.get(w, {}).get("mito", 0.0)
            p_hrs = worker_comp.get(w, {}).get("panter", 0.0)
            w_tot = worker_hours.get(w, 0.0)

            ws.cell(row=curr_r, column=1, value=w_disp).font = bold_font
            ws.cell(row=curr_r, column=1).alignment = center_align
            ws.cell(row=curr_r, column=2, value=m_hrs).number_format = '0.00'
            ws.cell(row=curr_r, column=3, value=mi_hrs).number_format = '0.00'
            ws.cell(row=curr_r, column=4, value=p_hrs).number_format = '0.00'
            tot_c = ws.cell(row=curr_r, column=5, value=w_tot)
            tot_c.font = bold_font
            tot_c.number_format = '0.00'

            for col_i in range(1, 6):
                ws.cell(row=curr_r, column=col_i).border = thin_border
                if col_i > 1:
                    ws.cell(row=curr_r, column=col_i).alignment = right_align
            curr_r += 1

        ws.cell(row=curr_r, column=1, value="FİRMA TOPLAMLARI").font = bold_font
        ws.cell(row=curr_r, column=1).alignment = center_align
        ws.cell(row=curr_r, column=2, value=comp_hours["medobet"]).font = bold_font
        ws.cell(row=curr_r, column=2).number_format = '0.00'
        ws.cell(row=curr_r, column=3, value=comp_hours["mito"]).font = bold_font
        ws.cell(row=curr_r, column=3).number_format = '0.00'
        ws.cell(row=curr_r, column=4, value=comp_hours["panter"]).font = bold_font
        ws.cell(row=curr_r, column=4).number_format = '0.00'
        grand_tot = ws.cell(row=curr_r, column=5, value=total_hours)
        grand_tot.font = bold_font
        grand_tot.number_format = '0.00'

        for col_i in range(1, 6):
            c_cell = ws.cell(row=curr_r, column=col_i)
            c_cell.fill = summary_fill
            c_cell.border = double_bottom_border
            if col_i > 1:
                c_cell.alignment = right_align

        for col in ws.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                if cell.row == 1:
                    continue
                if cell.value:
                    val_str = str(cell.value)
                    if len(val_str) > max_len:
                        max_len = len(val_str)
            ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

        mem = io.BytesIO()
        wb.save(mem)
        mem.seek(0)
        filename = f"mesai_detay_{clean_period}.xlsx"
        return mem.getvalue(), filename, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    except ImportError:
        csv_bytes = generate_excel_csv(shifts, period_label).getvalue()
        filename = f"mesai_detay_{clean_period}.csv"
        return csv_bytes, filename, "text/csv"

def generate_excel_csv(shifts: List[Dict[str, Any]], period_label: str = "") -> io.BytesIO:
    output = io.StringIO()
    output.write('\ufeff')
    writer = csv.writer(output, delimiter=';')

    writer.writerow([
        "Kayıt No", "Tarih", "Gün", "Çalışan", "Site / Firma", "Çalışılan Süre (Saat)", "Giriş Notu / Detay", "Kayıt Zamanı"
    ])

    total_hours = 0.0
    worker_hours = {"erkan": 0.0, "mirza": 0.0}
    comp_hours = {"medobet": 0.0, "mito": 0.0, "panter": 0.0}

    for s in shifts:
        s_id = s.get("id")
        d_str = s.get("shift_date", "")
        day_name = get_day_name(d_str)
        w_raw = s.get("worker_name", "").lower()
        w_name = w_raw.upper()
        c_key = s.get("company_key", "").lower()
        comp = s.get("company_display") or c_key.capitalize()
        hrs = float(s.get("duration_hours", 0.0))
        created = str(s.get("created_at", ""))
        raw = s.get("raw_text", "")

        total_hours += hrs
        if w_raw in worker_hours:
            worker_hours[w_raw] += hrs
        if c_key in comp_hours:
            comp_hours[c_key] += hrs

        writer.writerow([
            f"#{s_id}", d_str, day_name, w_name, comp, f"{hrs:.2f}".replace(".", ","), raw, created
        ])

    writer.writerow([])
    writer.writerow(["--- ÖZET VE TOPLAMLAR ---", "", "", "", "", "", "", ""])
    writer.writerow(["GENEL TOPLAM ÇALIŞMA", "", "", "", "", f"{total_hours:.2f}".replace(".", ","), f"Toplam {len(shifts)} Kayıt", ""])
    writer.writerow(["ERKAN TOPLAM SAAT", "", "", "ERKAN", "", f"{worker_hours['erkan']:.2f}".replace(".", ","), "", ""])
    writer.writerow(["MIRZA TOPLAM SAAT", "", "", "MIRZA", "", f"{worker_hours['mirza']:.2f}".replace(".", ","), "", ""])
    writer.writerow([])
    writer.writerow(["--- FİRMA BAZLI TOPLAMLAR ---", "", "", "", "", "", "", ""])
    writer.writerow(["MEDOBET TOPLAM", "", "", "", "Medobet", f"{comp_hours['medobet']:.2f}".replace(".", ","), "", ""])
    writer.writerow(["MITO TOPLAM", "", "", "", "Mito", f"{comp_hours['mito']:.2f}".replace(".", ","), "", ""])
    writer.writerow(["PANTER TOPLAM", "", "", "", "Panter", f"{comp_hours['panter']:.2f}".replace(".", ","), "", ""])

    mem = io.BytesIO()
    mem.write(output.getvalue().encode('utf-8-sig'))
    mem.seek(0)
    return mem
