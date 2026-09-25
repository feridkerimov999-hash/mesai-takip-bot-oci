import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import httpx

try:
    from .config import BOT_TOKEN, DEFAULT_COMPANIES, WORKERS
    from .db import (
        init_db,
        add_shift,
        delete_shift,
        reset_all_data,
        get_last_shift,
        get_shifts_by_month,
        get_all_shifts,
        get_recent_shifts,
        get_companies,
        set_company_cutoff_day,
        get_shifts_for_company_between,
        set_user_mapping,
        get_worker_by_telegram_id,
        get_active_session,
        get_active_sessions_for_user,
        get_active_session_by_company,
        start_session,
        start_break,
        end_break,
        finish_session,
        start_break_for_user,
        end_break_for_user,
        finish_all_sessions_for_user,
        get_shifts_by_date,
        get_shifts_between_dates
    )
    from .parser import parse_shift_message, parse_hours_and_date, parse_date_range
    from .calculator import calculate_monthly_summary, get_company_period_dates
    from .reporter import format_summary_report, format_shift_added, format_pay_period_report, generate_excel_csv, generate_excel_export
except ImportError:
    from config import BOT_TOKEN, DEFAULT_COMPANIES, WORKERS
    from db import (
        init_db,
        add_shift,
        delete_shift,
        reset_all_data,
        get_last_shift,
        get_shifts_by_month,
        get_all_shifts,
        get_recent_shifts,
        get_companies,
        set_company_cutoff_day,
        get_shifts_for_company_between,
        set_user_mapping,
        get_worker_by_telegram_id,
        get_active_session,
        get_active_sessions_for_user,
        get_active_session_by_company,
        start_session,
        start_break,
        end_break,
        finish_session,
        start_break_for_user,
        end_break_for_user,
        finish_all_sessions_for_user,
        get_shifts_by_date,
        get_shifts_between_dates
    )
    from parser import parse_shift_message, parse_hours_and_date, parse_date_range
    from calculator import calculate_monthly_summary, get_company_period_dates
    from reporter import format_summary_report, format_shift_added, format_pay_period_report, generate_excel_csv, generate_excel_export

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("mesai_bot")

class MesaiTelegramBot:
    def __init__(self, token: str):
        self.token = token
        self.api_url = f"https://api.telegram.org/bot{token}"
        self.client = httpx.AsyncClient(timeout=30.0)
        self.offset = 0
        self.is_running = False

    # ==============================================================================
    # BUTON KLAVYELERİ (ReplyKeyboardMarkup - Alttaki Büyük Butonlar)
    # ==============================================================================

    def get_main_reply_keyboard(self) -> Dict[str, Any]:
        """Sadeleştirilmiş ana ekran klavyesi (Maaş dönemi butonlu)"""
        return {
            "keyboard": [
                [{"text": "🟢 Mesaiye Başla"}, {"text": "🔴 Mesaiyi Bitir"}],
                [{"text": "📍 Anlık Durum"}],
                [{"text": "💳 Maaş Dönemi"}, {"text": "📊 Bugün"}, {"text": "📅 Bu Hafta"}],
                [{"text": "📥 Excel İndir"}, {"text": "📊 Raporlar"}]
            ],
            "resize_keyboard": True,
            "is_persistent": True
        }

    def get_site_reply_keyboard(self) -> Dict[str, Any]:
        """Mesaiye başlarken açılan site seçim klavyesi"""
        return {
            "keyboard": [
                [{"text": "🏢 Medobet"}, {"text": "🏢 Mito"}],
                [{"text": "🐆 Panter"}, {"text": "🔙 Ana Menü"}]
            ],
            "resize_keyboard": True,
            "is_persistent": True
        }

    def get_finish_reply_keyboard(self, active_sessions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Birden fazla aktif mesai varken hangisinin bitirileceğini seçtiren klavye"""
        rows = []
        comp_buttons = []
        for s in active_sessions:
            c_name = s.get("company_display") or s["company_key"].capitalize()
            comp_buttons.append({"text": f"🛑 {c_name}'i Bitir"})
            if len(comp_buttons) == 2:
                rows.append(comp_buttons)
                comp_buttons = []
        if comp_buttons:
            rows.append(comp_buttons)
        
        rows.append([{"text": "💥 Hepsini Bitir"}, {"text": "🔙 Ana Menü"}])
        return {
            "keyboard": rows,
            "resize_keyboard": True,
            "is_persistent": True
        }

    def get_profile_reply_keyboard(self) -> Dict[str, Any]:
        """Profil seçimi için klavye"""
        return {
            "keyboard": [
                [{"text": "👤 Ben Erkan'ım"}, {"text": "👤 Ben Mirza'yım"}],
                [{"text": "🔙 Ana Menü"}]
            ],
            "resize_keyboard": True,
            "is_persistent": True
        }

    def get_reports_reply_keyboard(self) -> Dict[str, Any]:
        """Raporlar tıklandığında açılan alt menü klavyesi"""
        return {
            "keyboard": [
                [{"text": "💳 Aktif Dönem"}, {"text": "⏮️ Önceki Dönem"}],
                [{"text": "📅 Bu Ay"}, {"text": "📋 Son Mesailer"}],
                [{"text": "⚙️ Kesim Tarihleri"}, {"text": "📥 Excel İndir"}],
                [{"text": "🧹 Test Kayıtlarını Sil"}],
                [{"text": "🔙 Ana Menü"}]
            ],
            "resize_keyboard": True,
            "is_persistent": True
        }

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML",
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        try:
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": parse_mode
            }
            if reply_markup is not None:
                payload["reply_markup"] = reply_markup
            else:
                payload["reply_markup"] = self.get_main_reply_keyboard()

            resp = await self.client.post(f"{self.api_url}/sendMessage", json=payload)
            return resp.json()
        except Exception as e:
            logger.error(f"Mesaj gönderme hatası: {e}")
            return None

    async def send_document(
        self,
        chat_id: int,
        document_bytes: bytes,
        filename: str,
        caption: str = "",
        mime_type: str = "application/octet-stream"
    ) -> Optional[Dict[str, Any]]:
        try:
            files = {"document": (filename, document_bytes, mime_type)}
            data = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
            resp = await self.client.post(f"{self.api_url}/sendDocument", data=data, files=files)
            return resp.json()
        except Exception as e:
            logger.error(f"Dosya gönderme hatası: {e}")
            return None

    async def answer_callback(self, cb_id: str, text: str = ""):
        try:
            await self.client.post(f"{self.api_url}/answerCallbackQuery", json={
                "callback_query_id": cb_id,
                "text": text
            })
        except Exception:
            pass

    # ==============================================================================
    # KOMUT VE BUTON AKSİYONLARI (Aynı Anda Birden Fazla Mesai Destekli)
    # ==============================================================================

    async def handle_start(self, chat_id: int, user: Dict[str, Any]):
        user_id = user.get("id")
        worker = get_worker_by_telegram_id(user_id) if user_id else None

        if not worker:
            msg = (
                "👋 <b>Çalışma Saati & Mesai Takip Botuna Hoş Geldiniz!</b>\n\n"
                "Lütfen aşağıdaki butonlardan kim olduğunuzu seçin:"
            )
            await self.send_message(chat_id, msg, reply_markup=self.get_profile_reply_keyboard())
            return

        active_list = get_active_sessions_for_user(user_id) if user_id else []
        active_txt = ""
        if active_list:
            c_names = [s.get("company_display") or s["company_key"].capitalize() for s in active_list]
            active_txt = f"\n\n🟢 <b>Şu an devam eden mesaileriniz:</b> {', '.join(c_names)}"

        msg = (
            f"👋 <b>Mesai Takip Sistemi</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Aktif Çalışan: <b>{worker.upper()}</b>{active_txt}\n\n"
            f"Aşağıdaki menü butonlarını kullanarak mesainizi başlatabilir, mola verebilir veya raporlarınızı inceleyebilirsiniz.\n"
            f"<i>(Aynı anda birden fazla sitede mesai başlatabilirsiniz).</i>"
        )
        await self.send_message(chat_id, msg, reply_markup=self.get_main_reply_keyboard())

    async def handle_live_start_prompt(self, chat_id: int, user: Dict[str, Any]):
        user_id = user.get("id")
        worker = get_worker_by_telegram_id(user_id) if user_id else None

        if not worker:
            await self.send_message(
                chat_id,
                "👤 Lütfen önce kim olduğunuzu seçin:",
                reply_markup=self.get_profile_reply_keyboard()
            )
            return

        # Devam eden mesailer varsa kullanıcıyı engellemiyoruz; bilgi verip yeni site seçtiriyoruz
        active_list = get_active_sessions_for_user(user_id) if user_id else []
        info_txt = ""
        if active_list:
            c_names = [s.get("company_display") or s["company_key"].capitalize() for s in active_list]
            info_txt = f"\n\n🟢 <i>Şu an açık olan mesaileriniz: <b>{', '.join(c_names)}</b>\nAynı anda başka bir sitenin mesaisini de başlatabilirsiniz:</i>"

        await self.send_message(
            chat_id,
            f"🏢 <b>Hangi sitede mesaiye başlıyorsunuz?</b>{info_txt}\n\nLütfen aşağıdaki butonlardan seçin:",
            reply_markup=self.get_site_reply_keyboard()
        )

    async def handle_site_picked_for_live(self, chat_id: int, user: Dict[str, Any], company_key: str):
        user_id = user.get("id")
        worker = get_worker_by_telegram_id(user_id) or "erkan"

        # Sadece aynı firmanın mesaisi zaten açıksa uyar
        existing = get_active_session_by_company(user_id, company_key)
        if existing:
            c_name = existing.get("company_display") or company_key.capitalize()
            start_time = existing["start_time"].split()[1] if " " in existing["start_time"] else existing["start_time"]
            await self.send_message(
                chat_id,
                f"⚠️ <b>{c_name}</b> mesainiz zaten açık ve devam ediyor!\n⏰ Başlangıç Saati: <b>{start_time}</b>\n\nFarklı bir site başlatabilir veya ana menüye dönebilirsiniz.",
                reply_markup=self.get_main_reply_keyboard()
            )
            return

        start_session(user_id, worker, company_key)
        comps = get_companies()
        c_name = comps.get(company_key, {}).get("display_name", company_key.capitalize())
        now_time = datetime.now().strftime("%H:%M:%S")

        active_list = get_active_sessions_for_user(user_id)
        other_txt = ""
        if len(active_list) > 1:
            all_c = [s.get("company_display") or s["company_key"].capitalize() for s in active_list]
            other_txt = f"\n\n🔥 <i>Aynı anda aktif mesaileriniz: <b>{', '.join(all_c)}</b></i>"

        msg = (
            f"🟢 <b>Mesai başlangıcı kaydedildi.</b>\n"
            f"Saat: <b>{now_time}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"🏢 Firma: <b>{c_name}</b>\n"
            f"👤 Çalışan: <b>{worker.upper()}</b>"
            f"{other_txt}\n\n"
            f"<i>İyi çalışmalar! Mesaiyi bitirmek için aşağıdaki <b>🔴 Mesaiyi Bitir</b> butonunu kullanabilirsiniz.</i>"
        )
        await self.send_message(chat_id, msg, reply_markup=self.get_main_reply_keyboard())

    async def handle_live_stop(self, chat_id: int, user: Dict[str, Any]):
        user_id = user.get("id")
        active_list = get_active_sessions_for_user(user_id) if user_id else []

        if not active_list:
            await self.send_message(
                chat_id,
                "⚠️ <i>Şu anda aktif bir mesai kaydınız bulunmuyor.</i>\n\n"
                "Mesaiye başlamak için aşağıdaki <b>🟢 Mesaiye Başla</b> butonuna basabilirsiniz.",
                reply_markup=self.get_main_reply_keyboard()
            )
            return

        # Sadece 1 aktif mesai varsa direkt bitir (ekstra sormadan hızlıca)
        if len(active_list) == 1:
            await self._finish_single_session_and_notify(chat_id, active_list[0])
            return

        # Birden fazla aktif mesai varsa hangisini bitirmek istediğini butonlarla sor
        c_names = [s.get("company_display") or s["company_key"].capitalize() for s in active_list]
        await self.send_message(
            chat_id,
            f"🔴 <b>Şu anda {len(active_list)} aktif mesainiz devam ediyor:</b> ({', '.join(c_names)})\n\nHangisini bitirmek istiyorsunuz?",
            reply_markup=self.get_finish_reply_keyboard(active_list)
        )

    async def _finish_single_session_and_notify(self, chat_id: int, session: Dict[str, Any]):
        finished = finish_session(session["id"])
        if not finished:
            await self.send_message(chat_id, "❌ <i>Mesai sonlandırılırken bir hata oluştu.</i>", reply_markup=self.get_main_reply_keyboard())
            return

        now_time = datetime.now().strftime("%H:%M:%S")
        w_name = finished["worker_name"].upper()
        c_name = finished.get("company_display") or finished["company_key"].upper()
        hrs = finished["duration_hours"]
        start_time_short = finished["start_time"].split()[1] if " " in finished["start_time"] else finished["start_time"]

        mins = int(round(hrs * 60))
        h_part = mins // 60
        m_part = mins % 60
        if m_part != 0 and h_part > 0:
            dur_label = f"<b>{h_part} sa {m_part} dk</b> ({hrs:.2f} Saat)"
        elif h_part == 0:
            dur_label = f"<b>{m_part} dk</b> ({hrs:.2f} Saat)"
        else:
            dur_label = f"<b>{h_part} Saat</b> ({hrs:.2f} Saat)"

        msg = (
            f"🔴 <b>Mesai bitişi kaydedildi.</b>\n"
            f"Saat: <b>{now_time}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Çalışan: <b>{w_name}</b>\n"
            f"🏢 Firma: <b>{c_name}</b>\n"
            f"⏰ Başlangıç: <b>{start_time_short}</b> | Bitiş: <b>{now_time}</b>\n"
            f"⏱️ Çalışılan Süre: {dur_label}\n\n"
            f"✅ <i>Mesai sisteme kaydedildi ve Excel raporuna eklendi!</i>"
        )
        await self.send_message(chat_id, msg, reply_markup=self.get_main_reply_keyboard())

    async def handle_finish_all_sessions(self, chat_id: int, user: Dict[str, Any]):
        user_id = user.get("id")
        finished_list = finish_all_sessions_for_user(user_id) if user_id else []

        if not finished_list:
            await self.send_message(
                chat_id,
                "⚠️ <i>Şu anda aktif bir mesai kaydınız bulunmuyor.</i>",
                reply_markup=self.get_main_reply_keyboard()
            )
            return

        now_time = datetime.now().strftime("%H:%M:%S")
        lines = [
            "🔴 <b>Tüm Aktif Mesailer Bitti ve Kaydedildi!</b>",
            f"Saat: <b>{now_time}</b>",
            "━━━━━━━━━━━━━━━━━━━"
        ]

        total_h = 0.0
        for f in finished_list:
            c_name = f.get("company_display") or f["company_key"].upper()
            hrs = f["duration_hours"]
            total_h += hrs
            start_short = f["start_time"].split()[1] if " " in f["start_time"] else f["start_time"]
            mins = int(round(hrs * 60))
            h_part = mins // 60
            m_part = mins % 60
            if m_part != 0 and h_part > 0:
                d_str = f"{h_part} sa {m_part} dk ({hrs:.2f} sa)"
            elif h_part == 0:
                d_str = f"{m_part} dk ({hrs:.2f} sa)"
            else:
                d_str = f"{h_part} Saat ({hrs:.2f} sa)"
            lines.append(f"• <b>{c_name}:</b> {d_str} (Başlangıç: {start_short})")

        tot_mins = int(round(total_h * 60))
        tot_h = tot_mins // 60
        tot_m = tot_mins % 60
        if tot_m != 0 and tot_h > 0:
            tot_str = f"{tot_h} sa {tot_m} dk ({total_h:.2f} Saat)"
        else:
            tot_str = f"{tot_h} Saat ({total_h:.2f} Saat)"

        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append(f"⏱️ <b>Toplam Süre:</b> <b>{tot_str}</b>")
        lines.append("\n✅ <i>Tüm kayıtlar Excel dökümüne eklendi!</i>")

        await self.send_message(chat_id, "\n".join(lines), reply_markup=self.get_main_reply_keyboard())

    async def handle_live_break_start(self, chat_id: int, user: Dict[str, Any]):
        user_id = user.get("id")
        active_list = get_active_sessions_for_user(user_id) if user_id else []

        if not active_list:
            await self.send_message(
                chat_id,
                "⚠️ <i>Aktif bir mesainiz bulunmuyor. Önce '🟢 Mesaiye Başla' butonuna basın.</i>",
                reply_markup=self.get_main_reply_keyboard()
            )
            return

        count = start_break_for_user(user_id)
        now_time = datetime.now().strftime("%H:%M:%S")
        if count > 0:
            msg = (
                f"☕ <b>Mola başlangıcı kaydedildi.</b>\n"
                f"Saat: <b>{now_time}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"<i>(Aktif olan {count} mesainizin tamamı molaya alındı). Dinlenmenize bakın! Molanız bittiğinde aşağıdaki <b>▶️ Molayı Bitir</b> butonuna basmayı unutmayın.</i>"
            )
        else:
            msg = "☕ <i>Mesaileriniz zaten molada görünüyor.</i>"
        await self.send_message(chat_id, msg, reply_markup=self.get_main_reply_keyboard())

    async def handle_live_break_end(self, chat_id: int, user: Dict[str, Any]):
        user_id = user.get("id")
        active_list = get_active_sessions_for_user(user_id) if user_id else []

        if not active_list:
            await self.send_message(
                chat_id,
                "⚠️ <i>Şu anda aktif bir mesai veya mola bulunmuyor.</i>",
                reply_markup=self.get_main_reply_keyboard()
            )
            return

        count = end_break_for_user(user_id)
        now_time = datetime.now().strftime("%H:%M:%S")
        if count > 0:
            msg = (
                f"▶️ <b>Mola bitişi kaydedildi.</b>\n"
                f"Saat: <b>{now_time}</b>\n"
                f"━━━━━━━━━━━━━━━━━━━\n"
                f"<i>Mesailere devam ediliyor, iyi çalışmalar!</i>"
            )
        else:
            msg = "ℹ️ <i>Şu anda molada olan mesainiz bulunmuyor.</i>"
        await self.send_message(chat_id, msg, reply_markup=self.get_main_reply_keyboard())

    async def handle_live_status(self, chat_id: int, user: Dict[str, Any]):
        user_id = user.get("id")
        active_list = get_active_sessions_for_user(user_id) if user_id else []

        if not active_list:
            await self.send_message(
                chat_id,
                "📍 <b>ANLIK MESAİ DURUMU</b>\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "⚪ <i>Şu an aktif bir mesai kaydınız bulunmuyor.</i>\n\n"
                "Mesaiye başlamak için aşağıdaki <b>🟢 Mesaiye Başla</b> butonuna basabilirsiniz.",
                reply_markup=self.get_main_reply_keyboard()
            )
            return

        lines = ["📍 <b>ANLIK MESAİ DURUMU</b>", "━━━━━━━━━━━━━━━━━━━"]
        now = datetime.now()

        for s in active_list:
            start_dt = datetime.strptime(s["start_time"], "%Y-%m-%d %H:%M:%S")
            gross_secs = int((now - start_dt).total_seconds())
            net_hours = gross_secs // 3600
            net_mins = (gross_secs % 3600) // 60
            decimal_hrs = round(gross_secs / 3600.0, 2)

            c_name = s.get("company_display") or s["company_key"].upper()
            start_time_str = s["start_time"].split()[1] if " " in s["start_time"] else s["start_time"]

            lines.append(f"🏢 <b>{c_name}:</b> 🟢 Çalışıyor")
            lines.append(f"   • Başlangıç Saati: <b>{start_time_str}</b>")
            lines.append(f"   • Geçen Süre: <b>{net_hours} sa {net_mins} dk</b> ({decimal_hrs:.2f} Saat)")
            lines.append("")

        worker = active_list[0]["worker_name"].upper()
        lines.append("━━━━━━━━━━━━━━━━━━━")
        lines.append(f"👤 Çalışan: <b>{worker}</b> | Toplam <b>{len(active_list)}</b> aktif mesai.")
        await self.send_message(chat_id, "\n".join(lines), reply_markup=self.get_main_reply_keyboard())

    async def handle_report_today(self, chat_id: int):
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_label = datetime.now().strftime("%d.%m.%Y")
        shifts = get_shifts_by_date(today_str)
        companies = get_companies()
        summary = calculate_monthly_summary(shifts, companies)
        report_text = format_summary_report(summary, f"Bugün - {today_label}")
        await self.send_message(chat_id, report_text, reply_markup=self.get_main_reply_keyboard())

    async def handle_report_this_week(self, chat_id: int):
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        shifts = get_shifts_between_dates(start_of_week.strftime("%Y-%m-%d"), end_of_week.strftime("%Y-%m-%d"))
        companies = get_companies()
        summary = calculate_monthly_summary(shifts, companies)
        week_label = f"Bu Hafta ({start_of_week.strftime('%d.%m')} - {end_of_week.strftime('%d.%m.%Y')})"
        report_text = format_summary_report(summary, week_label)
        await self.send_message(chat_id, report_text, reply_markup=self.get_main_reply_keyboard())

    async def handle_report(self, chat_id: int, year_month: Optional[str] = None):
        if not year_month:
            year_month = datetime.now().strftime("%Y-%m")
            
        period_label = datetime.strptime(year_month, "%Y-%m").strftime("%B %Y")
        shifts = get_shifts_by_month(year_month)
        companies = get_companies()
        
        summary_data = calculate_monthly_summary(shifts, companies)
        report_text = format_summary_report(summary_data, period_label)
        
        await self.send_message(chat_id, report_text, reply_markup=self.get_reports_reply_keyboard())

    async def handle_export_excel(self, chat_id: int):
        current_ym = datetime.now().strftime("%Y-%m")
        period_label = datetime.strptime(current_ym, "%Y-%m").strftime("%B %Y")
        shifts = get_shifts_by_month(current_ym)
        
        if not shifts:
            shifts = get_all_shifts()
            if shifts:
                period_label = "Tüm Kayıtlar"

        if not shifts:
            await self.send_message(chat_id, "ℹ️ <i>Henüz dışa aktarılacak kayıtlı mesai verisi yok.</i>", reply_markup=self.get_main_reply_keyboard())
            return

        file_bytes, filename, mime_type = generate_excel_export(shifts, period_label)
        caption = (
            f"📊 <b>{period_label} Çalışma Saati Detay Dökümü</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 <i>Microsoft Excel, Apple Numbers veya Google E-Tablolar ile açabilirsiniz.</i>"
        )
        await self.send_document(
            chat_id=chat_id,
            document_bytes=file_bytes,
            filename=filename,
            caption=caption,
            mime_type=mime_type
        )

    async def handle_pay_period_report(self, chat_id: int, period_type: str = "current"):
        companies = get_companies()
        companies_data = []

        for c_key, c_info in companies.items():
            cutoff_day = c_info.get("cutoff_day", 1)
            start_d, end_d, p_label = get_company_period_dates(cutoff_day, period_type)
            s_start = start_d.strftime("%Y-%m-%d")
            s_end = end_d.strftime("%Y-%m-%d")
            c_shifts = get_shifts_for_company_between(c_key, s_start, s_end)

            c_worker_hours = {"erkan": 0.0, "mirza": 0.0}
            c_total = 0.0
            for cs in c_shifts:
                w = cs["worker_name"].lower()
                h = float(cs["duration_hours"])
                c_total += h
                if w in c_worker_hours:
                    c_worker_hours[w] += h
                else:
                    c_worker_hours[w] = h

            companies_data.append({
                "key": c_key,
                "display_name": c_info.get("display_name", c_key.capitalize()),
                "period_label": p_label,
                "total_hours": c_total,
                "worker_hours": c_worker_hours,
                "shifts_count": len(c_shifts)
            })

        report_text = format_pay_period_report(companies_data, period_type)

        inline_buttons = []
        excel_label = "📥 Bu Dönemin Excel'ini İndir" if period_type == "current" else "📥 Önceki Dönemin Excel'ini İndir"
        inline_buttons.append([{"text": excel_label, "callback_data": f"export_period_{period_type}"}])
        
        if period_type == "current":
            inline_buttons.append([{"text": "⏮️ Önceki Döneme Bak", "callback_data": "period_previous"}])
        else:
            inline_buttons.append([{"text": "⏭️ Aktif Döneme Dön", "callback_data": "period_current"}])

        inline_buttons.append([{"text": "⚙️ Kesim Günlerini Gör / Ayarla", "callback_data": "show_cutoffs"}])

        await self.send_message(
            chat_id,
            report_text,
            reply_markup={"inline_keyboard": inline_buttons}
        )

    async def handle_export_period_excel(self, chat_id: int, period_type: str = "current"):
        companies = get_companies()
        all_period_shifts = []

        for c_key, c_info in companies.items():
            cutoff_day = c_info.get("cutoff_day", 1)
            start_d, end_d, _ = get_company_period_dates(cutoff_day, period_type)
            s_start = start_d.strftime("%Y-%m-%d")
            s_end = end_d.strftime("%Y-%m-%d")
            c_shifts = get_shifts_for_company_between(c_key, s_start, s_end)
            all_period_shifts.extend(c_shifts)

        if not all_period_shifts:
            await self.send_message(chat_id, "ℹ️ <i>Bu dönem için kayıtlı mesai bulunamadı.</i>", reply_markup=self.get_main_reply_keyboard())
            return

        all_period_shifts.sort(key=lambda x: (x.get("shift_date", ""), x.get("id", 0)))
        title = "Aktif Maaş Dönemi" if period_type == "current" else "Önceki Maaş Dönemi"

        file_bytes, filename, mime_type = generate_excel_export(all_period_shifts, title)
        caption = (
            f"💳 <b>{title} Çalışma Saatleri Excel Dökümü</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📁 <i>Her firmanın hesap kesim tarihine göre filtrelenmiştir.</i>"
        )
        await self.send_document(
            chat_id=chat_id,
            document_bytes=file_bytes,
            filename=filename,
            caption=caption,
            mime_type=mime_type
        )

    async def handle_show_cutoffs(self, chat_id: int):
        companies = get_companies()
        lines = [
            "⚙️ <b>FİRMA HESAP KESİM GÜNLERİ</b>",
            "━━━━━━━━━━━━━━━━━━━━━\n",
            "Bot her firmanın mesaisini kendi kesim gününe göre otomatik diğer aya devreder:\n"
        ]

        for c_key, c_info in companies.items():
            c_name = c_info.get("display_name", c_key.capitalize())
            cutoff = c_info.get("cutoff_day", 1)
            _, _, p_label = get_company_period_dates(cutoff, "current")
            lines.append(f"• <b>{c_name}:</b> Her ayın <b>{cutoff}</b>'i ➔ <i>(Aktif Dönem: {p_label})</i>")

        lines.append("\n━━━━━━━━━━━━━━━━━━━━━")
        lines.append("✏️ <b>Kesim Gününü Değiştirmek İçin:</b>")
        lines.append("Aşağıdaki gibi mesaj gönderebilirsiniz:")
        lines.append("• <code>/kesim medobet 15</code>")
        lines.append("• <code>/kesim mito 20</code>")
        lines.append("• <code>/kesim panter 1</code>")

        await self.send_message(chat_id, "\n".join(lines), reply_markup=self.get_main_reply_keyboard())

    async def handle_set_cutoff_command(self, chat_id: int, text: str):
        cleaned = text.replace("/kesim", "").replace("kesim", "").strip()
        parts = cleaned.split()
        if len(parts) < 2:
            await self.send_message(
                chat_id,
                "⚠️ <b>Kullanım:</b> <code>/kesim &lt;firma&gt; &lt;gün&gt;</code>\n"
                "Örnek: <code>/kesim medobet 15</code> veya <code>/kesim mito 20</code>",
                reply_markup=self.get_main_reply_keyboard()
            )
            return

        c_target = parts[0].lower().strip()
        day_str = parts[1].strip()

        companies = get_companies()
        matching_key = None
        for k in companies:
            if c_target in k or k in c_target:
                matching_key = k
                break

        if not matching_key:
            await self.send_message(chat_id, f"❌ <b>'{c_target}'</b> adında bir firma bulunamadı. Mevcut firmalar: Medobet, Mito, Panter", reply_markup=self.get_main_reply_keyboard())
            return

        if not day_str.isdigit():
            await self.send_message(chat_id, "❌ Lütfen 1 ile 28 arasında geçerli bir gün sayısı girin.", reply_markup=self.get_main_reply_keyboard())
            return

        day = int(day_str)
        if day < 1 or day > 28:
            await self.send_message(chat_id, "❌ Kesim günü 1 ile 28 arasında olmalıdır.", reply_markup=self.get_main_reply_keyboard())
            return

        set_company_cutoff_day(matching_key, day)
        c_name = companies[matching_key].get("display_name", matching_key.capitalize())
        _, _, p_label = get_company_period_dates(day, "current")

        await self.send_message(
            chat_id,
            f"✅ <b>{c_name}</b> hesap kesim günü her ayın <b>{day}</b>'i olarak güncellendi!\n"
            f"📅 Yeni Aktif Dönem: <b>{p_label}</b>",
            reply_markup=self.get_main_reply_keyboard()
        )

    async def handle_custom_date_range(self, chat_id: int, start_d: str, end_d: str, label: str, want_excel: bool = False):
        shifts = get_shifts_between_dates(start_d, end_d)
        if not shifts:
            await self.send_message(
                chat_id,
                f"ℹ️ <b>{label}</b> tarihleri arasında kayıtlı mesai bulunamadı.",
                reply_markup=self.get_main_reply_keyboard()
            )
            return

        companies = get_companies()
        summary = calculate_monthly_summary(shifts, companies)
        report_text = format_summary_report(summary, label)

        if want_excel:
            file_bytes, filename, mime_type = generate_excel_export(shifts, label)
            caption = f"📊 <b>{label} Özel Tarihli Excel Dökümü</b>"
            await self.send_document(
                chat_id=chat_id,
                document_bytes=file_bytes,
                filename=filename,
                caption=caption,
                mime_type=mime_type
            )
        else:
            inline_btn = [[{"text": "📥 Bu Tarihlerin Excel'ini İndir", "callback_data": f"excel_range_{start_d}_{end_d}"}]]
            await self.send_message(chat_id, report_text, reply_markup={"inline_keyboard": inline_btn})

    async def handle_recent_shifts(self, chat_id: int):
        shifts = get_recent_shifts(8)
        if not shifts:
            await self.send_message(chat_id, "ℹ️ <i>Henüz kayıtlı mesai bulunmuyor.</i>", reply_markup=self.get_reports_reply_keyboard())
            return

        msg = ["📋 <b>SON GİRİLEN MESAİLER:</b>\n━━━━━━━━━━━━━━━━━━━━"]
        buttons = []
        for s in shifts:
            s_id = s["id"]
            w_name = s["worker_name"].upper()
            comp = s.get("company_display") or s["company_key"].upper()
            d_str = s["shift_date"]
            hrs = s["duration_hours"]
            msg.append(f"• <b>[#{s_id}]</b> {d_str} | <b>{w_name}</b> ➔ {comp} (<b>{hrs:.1f} sa</b>)")
            buttons.append([{"text": f"❌ #{s_id} Sil ({w_name} - {comp} {hrs:.0f}s)", "callback_data": f"delete_{s_id}"}])

        await self.send_message(chat_id, "\n".join(msg), reply_markup={"inline_keyboard": buttons})

    async def handle_reset_prompt(self, chat_id: int):
        inline_buttons = [
            [{"text": "🧹 Evet, Test Kayıtlarını Sil", "callback_data": "confirm_reset_all_data"}],
            [{"text": "❌ Vazgeç", "callback_data": "cancel_reset_all_data"}]
        ]
        msg = (
            "🧹 <b>Test Mesailerini & Saatleri Sil</b>\n"
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "Test ve deneme amacıyla girilen tüm mesai saatleri ve kayıtlar silinip sıfırlanacaktır.\n\n"
            "ℹ️ <i>Kullanıcı profilleriniz (Erkan/Mirza) ve firma kesim tarihleriniz korunur. Sadece hesaplanan mesai saatleri temizlenir.</i>\n\n"
            "Test kayıtlarını silmek istiyor musunuz?"
        )
        await self.send_message(chat_id, msg, reply_markup={"inline_keyboard": inline_buttons})

    # ==============================================================================
    # MESAJ İŞLEYİCİ (handle_message)
    # ==============================================================================

    async def handle_message(self, message: Dict[str, Any]):
        chat_id = message.get("chat", {}).get("id")
        user = message.get("from", {})
        text = message.get("text", "").strip()

        if not text or not chat_id:
            return

        user_id = user.get("id")
        registered_worker = get_worker_by_telegram_id(user_id) if user_id else None

        # 0. SIFIRLAMA / TEST VERİLERİNİ TEMİZLEME KOMUTU / BUTONU
        t_lower = text.lower().strip()
        if (
            text in ["🧹 Test Kayıtlarını Sil", "🧹 Kayıtları Temizle", "🗑️ Tüm Verileri Sıfırla"]
            or t_lower in [
                "test kayıtlarını sil", "test kayitlarini sil", "testleri sil", "testleri temizle",
                "hesaplananları sil", "hesaplananlari sil", "mesaileri sil", "saatleri sil",
                "kayıtları temizle", "kayitlari temizle", "temizle", "/temizle",
                "sıfırla", "sifirla", "/sifirla", "reset", "/reset"
            ]
        ):
            await self.handle_reset_prompt(chat_id)
            return

        if text in ["/sil", "sil", "mesai sil"]:
            await self.handle_recent_shifts(chat_id)
            return

        # 1. CANLI MESAİ REPLY KEYBOARD BUTONLARI (Görseldeki Tam Tasarım)
        if text in ["🟢 Mesaiye Başla", "mesaiye başla", "mesaiye basla", "/basla"]:
            await self.handle_live_start_prompt(chat_id, user)
            return

        if text in ["🔴 Mesaiyi Bitir", "mesaiyi bitir", "/bitir"]:
            await self.handle_live_stop(chat_id, user)
            return

        if text in ["☕ Mola Başlat", "mola başlat", "mola baslat", "/mola", "▶️ Molayı Bitir", "molayı bitir", "molayi bitir", "/devam"]:
            await self.send_message(
                chat_id,
                "ℹ️ <i>Mola sistemi kaldırılmıştır. Çalışma süreleriniz kesintisiz olarak ve tüm küsüratlarıyla hesaplanmaktadır.</i>",
                reply_markup=self.get_main_reply_keyboard()
            )
            return

        if text in ["📍 Anlık Durum", "anlık durum", "anlik durum", "/durum"]:
            await self.handle_live_status(chat_id, user)
            return

        if text in ["📊 Bugün", "bugün", "bugun", "/bugun"]:
            await self.handle_report_today(chat_id)
            return

        if text in ["📅 Bu Hafta", "bu hafta", "/hafta"]:
            await self.handle_report_this_week(chat_id)
            return

        if text in ["💳 Maaş Dönemi", "maaş dönemi", "maas donemi", "💳 Aktif Dönem", "/donem", "/maas"]:
            await self.handle_pay_period_report(chat_id, "current")
            return

        if text in ["⏮️ Önceki Dönem", "önceki dönem", "onceki donem"]:
            await self.handle_pay_period_report(chat_id, "previous")
            return

        if text in ["⚙️ Kesim Tarihleri", "kesim tarihleri", "/kesimler"]:
            await self.handle_show_cutoffs(chat_id)
            return

        if text.startswith("/kesim") or text.startswith("kesim "):
            await self.handle_set_cutoff_command(chat_id, text)
            return

        if text in ["📅 Bu Ay", "bu ay", "/ay"]:
            await self.handle_report(chat_id)
            return

        if text in ["📊 Raporlar", "raporlar"]:
            await self.handle_report(chat_id)
            return

        # Serbest Tarih Aralığı kontrolü (Örn: 15.09 - 14.10 veya 15 eylül - 14 ekim)
        range_parsed = parse_date_range(text)
        if range_parsed:
            s_d, e_d, r_label = range_parsed
            want_excel = "excel" in text.lower() or "indir" in text.lower()
            await self.handle_custom_date_range(chat_id, s_d, e_d, r_label, want_excel)
            return

        # 2. ÇOKLU MESAİ BİTİRME BUTONLARI (Tek tek veya hepsi)
        if text.startswith("🛑 ") and "Bitir" in text:
            # Örn: "🛑 Medobet'i Bitir"
            comp_target = None
            if "medobet" in text.lower():
                comp_target = "medobet"
            elif "mito" in text.lower():
                comp_target = "mito"
            elif "panter" in text.lower():
                comp_target = "panter"

            if comp_target:
                session = get_active_session_by_company(user_id, comp_target)
                if session:
                    await self._finish_single_session_and_notify(chat_id, session)
                else:
                    await self.send_message(chat_id, f"⚠️ <b>{comp_target.capitalize()}</b> için aktif mesai bulunamadı.", reply_markup=self.get_main_reply_keyboard())
                return

        if text in ["💥 Hepsini Bitir", "hepsini bitir"]:
            await self.handle_finish_all_sessions(chat_id, user)
            return

        # 3. SİTE SEÇİM BUTONLARI
        if text == "🏢 Medobet":
            await self.handle_site_picked_for_live(chat_id, user, "medobet")
            return

        if text == "🏢 Mito":
            await self.handle_site_picked_for_live(chat_id, user, "mito")
            return

        if text == "🐆 Panter":
            await self.handle_site_picked_for_live(chat_id, user, "panter")
            return

        if text in ["🔙 Ana Menü", "ana menü", "ana menu"]:
            await self.send_message(chat_id, "🏠 <b>Ana Menü</b>", reply_markup=self.get_main_reply_keyboard())
            return

        if text in ["📥 Excel İndir", "/excel", "/csv"]:
            await self.handle_export_excel(chat_id)
            return

        if text in ["📋 Son Mesailer", "/son"]:
            await self.handle_recent_shifts(chat_id)
            return

        if text in ["👤 Profil Değiştir", "👤 Profil Seç"]:
            await self.send_message(chat_id, "👤 <b>Profilinizi Seçin:</b>", reply_markup=self.get_profile_reply_keyboard())
            return

        if text in ["👤 Ben Erkan'ım", "erkan'ım", "erkanim"]:
            set_user_mapping(user_id, "erkan")
            await self.send_message(chat_id, "✅ Profiliniz <b>ERKAN</b> olarak ayarlandı!", reply_markup=self.get_main_reply_keyboard())
            return

        if text in ["👤 Ben Mirza'yım", "mirza'yım", "mirzayim"]:
            set_user_mapping(user_id, "mirza")
            await self.send_message(chat_id, "✅ Profiliniz <b>MİRZA</b> olarak ayarlandı!", reply_markup=self.get_main_reply_keyboard())
            return

        # 4. STANDART KOMUTLAR
        if text.startswith("/start") or text.startswith("/help") or text.startswith("/yardim"):
            await self.handle_start(chat_id, user)
            return

        if text.startswith("/rapor") or text.startswith("/ozet"):
            await self.handle_report(chat_id)
            return

        if text.startswith("/ben"):
            parts = text.split()
            if len(parts) > 1 and parts[1].lower() in WORKERS:
                w_name = parts[1].lower()
                set_user_mapping(user_id, w_name)
                await self.send_message(chat_id, f"✅ Profiliniz <b>{w_name.upper()}</b> olarak kaydedildi!", reply_markup=self.get_main_reply_keyboard())
            else:
                await self.send_message(chat_id, "⚠️ Lütfen belirtin: <code>/ben erkan</code> veya <code>/ben mirza</code>")
            return

        # 5. MANUEL METİNLE MESAİ GİRİŞİ (Yedek Kolaylık)
        parsed = parse_shift_message(text, default_worker=registered_worker)
        if parsed:
            shift_id = add_shift(
                worker_name=parsed["worker_name"],
                company_key=parsed["company_key"],
                shift_date=parsed["shift_date"],
                duration_hours=parsed["duration_hours"],
                raw_text=text,
                telegram_user_id=user_id
            )
            comps = get_companies()
            c_name = comps.get(parsed["company_key"], {}).get("display_name", parsed["company_key"].capitalize())
            confirm = format_shift_added(parsed["worker_name"], c_name, parsed["duration_hours"], parsed["shift_date"])
            await self.send_message(chat_id, confirm, reply_markup=self.get_main_reply_keyboard())
        else:
            await self.send_message(
                chat_id,
                "ℹ️ <i>Lütfen aşağıdaki butonları kullanın:</i>",
                reply_markup=self.get_main_reply_keyboard()
            )

    # ==============================================================================
    # CALLBACK İŞLEYİCİ (Silme butonları vb.)
    # ==============================================================================

    async def handle_callback_query(self, cb: Dict[str, Any]):
        cb_id = cb.get("id")
        data = cb.get("data", "")
        message = cb.get("message", {})
        chat_id = message.get("chat", {}).get("id")

        if not chat_id or not cb_id:
            return

        if data.startswith("delete_"):
            s_id_str = data.replace("delete_", "")
            if s_id_str.isdigit():
                s_id = int(s_id_str)
                success = delete_shift(s_id)
                if success:
                    await self.answer_callback(cb_id, f"#{s_id} Silindi ✅")
                    await self.send_message(chat_id, f"🗑️ <b>#{s_id} numaralı mesai kaydı silindi.</b>", reply_markup=self.get_main_reply_keyboard())
                else:
                    await self.answer_callback(cb_id, "Kayıt bulunamadı!")
            return

        if data == "period_previous":
            await self.answer_callback(cb_id, "Önceki dönem yükleniyor...")
            await self.handle_pay_period_report(chat_id, "previous")
            return

        if data == "period_current":
            await self.answer_callback(cb_id, "Aktif dönem yükleniyor...")
            await self.handle_pay_period_report(chat_id, "current")
            return

        if data.startswith("export_period_"):
            p_type = data.replace("export_period_", "")
            await self.answer_callback(cb_id, "Excel hazırlanıyor...")
            await self.handle_export_period_excel(chat_id, p_type)
            return

        if data == "show_cutoffs":
            await self.answer_callback(cb_id, "Kesim günleri listeleniyor...")
            await self.handle_show_cutoffs(chat_id)
            return

        if data.startswith("excel_range_"):
            parts = data.replace("excel_range_", "").split("_")
            if len(parts) == 2:
                s_d, e_d = parts
                await self.answer_callback(cb_id, "Excel hazırlanıyor...")
                await self.handle_custom_date_range(chat_id, s_d, e_d, f"{s_d} - {e_d}", want_excel=True)
            return

        if data == "confirm_reset_all_data":
            res = reset_all_data()
            count = res.get("shifts_deleted", 0)
            await self.answer_callback(cb_id, "Test kayıtları silindi!")
            msg = (
                "🧹 <b>Test Kayıtları Temizlendi!</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ Test için girilmiş olan <b>{count}</b> adet mesai kaydı silindi.\n\n"
                "Tüm saatler ve raporlar sıfırlandı. Yeni mesailerinizi girmeye hazırsınız!"
            )
            await self.send_message(chat_id, msg, reply_markup=self.get_main_reply_keyboard())
            return

        if data == "cancel_reset_all_data":
            await self.answer_callback(cb_id, "İptal edildi.")
            await self.send_message(chat_id, "✅ <i>İşlem iptal edildi, kayıtlarınız korundu.</i>", reply_markup=self.get_main_reply_keyboard())
            return

    # ==============================================================================
    # BOT DÖNGÜSÜ (Polling)
    # ==============================================================================

    async def run(self):
        init_db()
        logger.info("Çoklu Mesai Destekli Telegram Botu başlatılıyor...")
        self.is_running = True

        while self.is_running:
            try:
                resp = await self.client.get(
                    f"{self.api_url}/getUpdates",
                    params={"offset": self.offset, "timeout": 20}
                )
                data = resp.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        self.offset = update["update_id"] + 1
                        if "message" in update:
                            await self.handle_message(update["message"])
                        elif "callback_query" in update:
                            await self.handle_callback_query(update["callback_query"])
                elif data.get("error_code") == 409:
                    logger.warning("⚠️ 409 ÇAKIŞMA: Başka bir bot kopyası açık!")
                    await asyncio.sleep(5)
            except httpx.RequestError as e:
                logger.error(f"Ağ hatası: {e}")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Hata: {e}")
                await asyncio.sleep(2)

async def main():
    bot = MesaiTelegramBot(BOT_TOKEN)
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
