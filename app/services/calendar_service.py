import json
import os
from datetime import datetime, timedelta, date
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode, quote
import urllib.request
import urllib.error

from app.config import settings
from app.models.medical import MedicalAppointment
from app.models.settings import PregnancySettings


class GoogleCalendarService:
    """
    Servicio Dual de Integración con Google Calendar + Sistema de Alertas (1 día antes):
    1. Opción 1 (Directa / Universal):
       - Genera enlaces directos `calendar.google.com/calendar/render` para abrir en el celular.
       - Genera archivos y feeds suscribibles `.ics` (iCalendar RFC 5545) con alarmas VALARM
         automáticas 1 día antes (-P1D / 1440 min) y 2 horas antes (-PT2H / 120 min).
    2. Opción 2 (Sincronización Automática API en Segundo Plano con Auto-Provisión):
       - Si el usuario ya compartió su calendario personal con la cuenta de servicio, escribe ahí.
       - Si devuelve HTTP 404 (porque en el celular Google no muestra el menú de compartir calendario),
         el servidor CREA AUTOMÁTICAMENTE un calendario compartido "🍼 BabyTrack", le otorga permisos
         de edición (ACL writer) al correo Gmail del usuario (ej. darielgameplay@gmail.com) y sincroniza
         todas las citas ahí sin errores.
    """

    TYPE_LABELS = {
        "MEDICO": "🩺 Cita Médica",
        "LABORATORIO": "🔬 Cita Laboratorio",
        "ECO": "👶 Cita Ultrasonido (Eco)",
    }

    @classmethod
    def get_effective_calendar_id(cls, settings_record: Optional[PregnancySettings] = None) -> str:
        """Obtiene el ID de Google Calendar desde la BD o desde la variable de entorno."""
        if settings_record and getattr(settings_record, "google_calendar_id", None):
            cal_id = settings_record.google_calendar_id.strip()
            if cal_id:
                return cal_id
        return (settings.GOOGLE_CALENDAR_ID or "").strip()

    @classmethod
    def build_event_title(cls, appt: MedicalAppointment, baby_nickname: str = "Nuestro Bebé") -> str:
        type_label = cls.TYPE_LABELS.get((appt.appointment_type or "MEDICO").upper(), "🩺 Cita Prenatal")
        return f"{type_label}: {appt.doctor_or_clinic} · {baby_nickname} (Sem {appt.gestational_week}+{appt.gestational_day})"

    @classmethod
    def build_event_description(cls, appt: MedicalAppointment, baby_nickname: str = "Nuestro Bebé") -> str:
        lines = [
            f"🍼 BabyTrack — Control Prenatal de {baby_nickname}",
            f"• Tipo: {cls.TYPE_LABELS.get((appt.appointment_type or 'MEDICO').upper(), 'Cita Prenatal')}",
            f"• Médico / Lugar: {appt.doctor_or_clinic}",
            f"• Especialidad: {appt.specialty or 'Obstetricia'}",
            f"• Edad Gestacional en la cita: Semana {appt.gestational_week}, Día {appt.gestational_day}",
            "• Alerta programada: ⏰ 1 día antes (24 horas) y 2 horas antes de la cita.",
        ]
        if appt.questions_for_doctor:
            header = (
                "📋 Estudios a realizar / Preparación previa (ej. ayuno):"
                if appt.appointment_type == "LABORATORIO"
                else "❓ Preguntas / Notas para la consulta:"
            )
            lines.append("")
            lines.append(header)
            lines.append(appt.questions_for_doctor)

        if appt.doctor_notes_and_diagnosis:
            lines.append("")
            lines.append("📝 Indicaciones / Diagnóstico:")
            lines.append(appt.doctor_notes_and_diagnosis)

        return "\n".join(lines)

    @classmethod
    def build_google_calendar_template_url(
        cls,
        appt: MedicalAppointment,
        baby_nickname: str = "Nuestro Bebé",
    ) -> str:
        """
        Genera el enlace oficial de 1 toque para abrir la app de Google Calendar
        en Android / iPhone / Web con todos los datos de la cita pre-llenados.
        """
        start_dt: datetime = appt.appointment_date
        end_dt: datetime = start_dt + timedelta(hours=1)

        fmt = "%Y%m%dT%H%M%S"
        dates_param = f"{start_dt.strftime(fmt)}/{end_dt.strftime(fmt)}"

        params = {
            "action": "TEMPLATE",
            "text": cls.build_event_title(appt, baby_nickname),
            "dates": dates_param,
            "details": cls.build_event_description(appt, baby_nickname),
            "location": appt.doctor_or_clinic,
            "ctz": settings.TZ or "America/Mexico_City",
        }
        return f"https://calendar.google.com/calendar/render?{urlencode(params)}"

    @staticmethod
    def _escape_ics_text(value: str) -> str:
        if not value:
            return ""
        return (
            value.replace("\\", "\\\\")
            .replace(";", "\\;")
            .replace(",", "\\,")
            .replace("\r\n", "\\n")
            .replace("\n", "\\n")
        )

    @classmethod
    def _appointment_to_ics_vevent(
        cls,
        appt: MedicalAppointment,
        baby_nickname: str = "Nuestro Bebé",
    ) -> List[str]:
        start_dt: datetime = appt.appointment_date
        end_dt: datetime = start_dt + timedelta(hours=1)
        now_str = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        dt_fmt = "%Y%m%dT%H%M%S"

        summary = cls._escape_ics_text(cls.build_event_title(appt, baby_nickname))
        description = cls._escape_ics_text(cls.build_event_description(appt, baby_nickname))
        location = cls._escape_ics_text(appt.doctor_or_clinic)
        status_ics = "CANCELLED" if appt.status == "CANCELLED" else "CONFIRMED"
        reminder_mins = getattr(appt, "reminder_minutes_before", 1440) or 1440

        lines = [
            "BEGIN:VEVENT",
            f"UID:babytrack-appt-{appt.id}@babytrack.app",
            f"DTSTAMP:{now_str}",
            f"DTSTART;TZID={settings.TZ}:{start_dt.strftime(dt_fmt)}",
            f"DTEND;TZID={settings.TZ}:{end_dt.strftime(dt_fmt)}",
            f"SUMMARY:{summary}",
            f"DESCRIPTION:{description}",
            f"LOCATION:{location}",
            f"STATUS:{status_ics}",
            # Alarma principal: 1 día antes (o minutos configurados, por defecto 1440 min = 24 hrs)
            "BEGIN:VALARM",
            f"TRIGGER:-PT{reminder_mins}M",
            "ACTION:DISPLAY",
            f"DESCRIPTION:⏰ Mañana tienes {summary}",
            "END:VALARM",
            # Alarma secundaria preventiva: 2 horas antes (120 min)
            "BEGIN:VALARM",
            "TRIGGER:-PT120M",
            "ACTION:DISPLAY",
            f"DESCRIPTION:🍼 En 2 horas: {summary}",
            "END:VALARM",
            "END:VEVENT",
        ]
        return lines

    @classmethod
    def generate_single_appointment_ics(
        cls,
        appt: MedicalAppointment,
        baby_nickname: str = "Nuestro Bebé",
    ) -> str:
        """Genera un archivo .ics individual para una cita con alerta 1 día antes."""
        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//BabyTrack//Seguimiento Prenatal//ES",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            f"X-WR-CALNAME:BabyTrack - {baby_nickname}",
            f"X-WR-TIMEZONE:{settings.TZ}",
        ]
        lines.extend(cls._appointment_to_ics_vevent(appt, baby_nickname))
        lines.append("END:VCALENDAR")
        return "\r\n".join(lines) + "\r\n"

    @classmethod
    def generate_ics_feed(
        cls,
        appointments: List[MedicalAppointment],
        settings_record: Optional[PregnancySettings] = None,
    ) -> str:
        """
        Genera el calendario completo suscribible (.ics) con todas las citas
        y la Fecha Probable de Parto (FPP), incluyendo alertas de 1 día antes.
        """
        baby_nickname = getattr(settings_record, "baby_nickname", None) or "Nuestro Bebé"
        due_date: date = getattr(settings_record, "due_date", None) or date(2027, 7, 7)
        now_str = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

        lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//BabyTrack//Seguimiento Prenatal//ES",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            f"X-WR-CALNAME:BabyTrack - {cls._escape_ics_text(baby_nickname)}",
            f"X-WR-TIMEZONE:{settings.TZ}",
        ]

        # Evento de Fecha Probable de Parto (FPP) con alerta 1 día antes y 7 días antes
        fpp_start = due_date.strftime("%Y%m%d")
        fpp_end = (due_date + timedelta(days=1)).strftime("%Y%m%d")
        lines.extend(
            [
                "BEGIN:VEVENT",
                "UID:babytrack-fpp-due-date@babytrack.app",
                f"DTSTAMP:{now_str}",
                f"DTSTART;VALUE=DATE:{fpp_start}",
                f"DTEND;VALUE=DATE:{fpp_end}",
                f"SUMMARY:🎉👶 Fecha Probable de Parto (FPP) — {cls._escape_ics_text(baby_nickname)}",
                "DESCRIPTION:¡Llegó el gran día esperado en BabyTrack! Semana 40 de gestación.",
                "BEGIN:VALARM",
                "TRIGGER:-P1D",
                "ACTION:DISPLAY",
                f"DESCRIPTION:⏰ ¡Mañana es la Fecha Probable de Parto de {cls._escape_ics_text(baby_nickname)}!",
                "END:VALARM",
                "BEGIN:VALARM",
                "TRIGGER:-P7D",
                "ACTION:DISPLAY",
                f"DESCRIPTION:🍼 ¡Falta 1 semana para la Fecha Probable de Parto de {cls._escape_ics_text(baby_nickname)}!",
                "END:VALARM",
                "END:VEVENT",
            ]
        )

        for appt in appointments:
            if appt.status != "CANCELLED":
                lines.extend(cls._appointment_to_ics_vevent(appt, baby_nickname))

        lines.append("END:VCALENDAR")
        return "\r\n".join(lines) + "\r\n"

    # ==========================================================================
    # OPCIÓN 2: SINCRONIZACIÓN AUTOMÁTICA VÍA API DE GOOGLE CALENDAR
    # ==========================================================================

    @classmethod
    def _fetch_gcp_access_token(cls) -> Optional[str]:
        """
        Obtiene el token OAuth2 con scope de Google Calendar desde:
        1. Variable de entorno GOOGLE_CALENDAR_ACCESS_TOKEN (útil en pruebas/local).
        2. Servidor de Metadatos de Google Cloud Run (automático en producción).
        """
        env_token = os.getenv("GOOGLE_CALENDAR_ACCESS_TOKEN", "").strip()
        if env_token:
            return env_token

        metadata_url = (
            "http://metadata.google.internal/computeMetadata/v1/instance/"
            "service-accounts/default/token?scopes=https://www.googleapis.com/auth/calendar"
        )
        req = urllib.request.Request(
            metadata_url,
            headers={"Metadata-Flavor": "Google"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("access_token")
        except Exception:
            return None

    @classmethod
    def _api_request(
        cls,
        url: str,
        token: str,
        method: str = "GET",
        body: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {token}"}
        data_bytes = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data_bytes = json.dumps(body).encode("utf-8")

        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}

    @classmethod
    def ensure_accessible_calendar(
        cls,
        user_input_id_or_email: str,
        baby_nickname: str = "Nuestro Bebé",
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Verifica si el `calendar_id` o correo ingresado es accesible directamente.
        Si devuelve HTTP 404 (porque el usuario no ha compartido manualmente su calendario
        personal desde una PC), el servidor CREA o REUTILIZA automáticamente un calendario
        compartido "🍼 BabyTrack" en la cuenta del servidor y le da acceso (ACL writer +
        lectura pública por enlace) al correo Gmail del usuario para que funcione sin fricción.
        """
        clean_input = (user_input_id_or_email or "").strip()
        if not clean_input:
            return {"ok": False, "reason": "ID vacío"}

        access_token = token or cls._fetch_gcp_access_token()
        if not access_token:
            return {"ok": False, "calendarId": clean_input, "reason": "Sin token GCP"}

        # Extraer posibles correos separados por coma (ej. mamá y papá)
        emails = [
            e.strip()
            for e in clean_input.replace(";", ",").split(",")
            if "@" in e and not e.strip().endswith("@group.calendar.google.com")
        ]
        primary_candidate = clean_input.split(",")[0].strip()

        # 1. Probar si el calendario candidato ya es directamente accesible (ej. ya fue compartido o es un group.calendar.google.com)
        encoded_cand = quote(primary_candidate, safe="")
        try:
            cal_meta = cls._api_request(
                f"https://www.googleapis.com/calendar/v3/calendars/{encoded_cand}",
                access_token,
                method="GET",
            )
            if cal_meta.get("id"):
                return {
                    "ok": True,
                    "calendarId": cal_meta["id"],
                    "autoCreated": False,
                    "sharedWith": emails,
                    "addCalendarUrl": f"https://calendar.google.com/calendar/r?cid={quote(cal_meta['id'], safe='')}",
                }
        except urllib.error.HTTPError as e:
            if e.code != 404:
                return {"ok": False, "calendarId": primary_candidate, "reason": f"HTTP {e.code}"}
        except Exception as exc:
            return {"ok": False, "calendarId": primary_candidate, "reason": str(exc)}

        # 2. Si dio 404, buscamos si la cuenta de servicio ya creó previamente un calendario "🍼 BabyTrack"
        target_cal_id = None
        try:
            cal_list = cls._api_request(
                "https://www.googleapis.com/calendar/v3/users/me/calendarList",
                access_token,
                method="GET",
            )
            for item in cal_list.get("items", []):
                if "BabyTrack" in (item.get("summary") or ""):
                    target_cal_id = item.get("id")
                    break
        except Exception:
            pass

        # 3. Si no existe aún, crear el calendario "🍼 BabyTrack - Nuestro Bebé"
        if not target_cal_id:
            try:
                created = cls._api_request(
                    "https://www.googleapis.com/calendar/v3/calendars",
                    access_token,
                    method="POST",
                    body={
                        "summary": f"🍼 BabyTrack — {baby_nickname}",
                        "description": "Calendario automático de Citas Médicas, Laboratorio, Ecos y FPP de BabyTrack.",
                        "timeZone": settings.TZ or "America/Mexico_City",
                    },
                )
                target_cal_id = created.get("id")
            except Exception as exc:
                return {"ok": False, "calendarId": primary_candidate, "reason": f"No se pudo auto-crear calendario: {exc}"}

        if not target_cal_id:
            return {"ok": False, "calendarId": primary_candidate, "reason": "No se obtuvo ID del calendario creado."}

        # 4. Compartir automáticamente (ACL writer) con todos los correos Gmail ingresados
        encoded_target = quote(target_cal_id, safe="")
        shared_ok = []
        for email_addr in emails:
            try:
                cls._api_request(
                    f"https://www.googleapis.com/calendar/v3/calendars/{encoded_target}/acl?sendNotifications=true",
                    access_token,
                    method="POST",
                    body={
                        "role": "writer",
                        "scope": {"type": "user", "value": email_addr},
                    },
                )
                shared_ok.append(email_addr)
            except Exception:
                pass

        return {
            "ok": True,
            "calendarId": target_cal_id,
            "autoCreated": True,
            "sharedWith": shared_ok,
            "addCalendarUrl": f"https://calendar.google.com/calendar/r?cid={quote(target_cal_id, safe='')}",
        }

    @classmethod
    def sync_appointment_to_google_calendar(
        cls,
        appt: MedicalAppointment,
        calendar_id: Optional[str],
        baby_nickname: str = "Nuestro Bebé",
    ) -> Dict[str, Any]:
        """
        Crea o actualiza automáticamente el evento en Google Calendar vía REST API v3,
        configurando recordatorios automáticos 1 día antes (1440 min, popup + email)
        y 2 horas antes (120 min, popup).
        Si el `calendar_id` devuelve 404, auto-provisiona un calendario compartido BabyTrack.
        """
        cal_id = (calendar_id or "").strip()
        if not cal_id:
            return {"synced": False, "reason": "No se ha configurado un ID de Google Calendar."}

        token = cls._fetch_gcp_access_token()
        if not token:
            return {
                "synced": False,
                "reason": "Sin token de servicio GCP (disponible automáticamente al correr en Google Cloud Run).",
            }

        # Si la cita fue cancelada y ya tenía evento en Google Calendar, eliminarlo
        if appt.status == "CANCELLED" and appt.google_event_id:
            return cls.delete_appointment_from_google_calendar(appt.google_event_id, cal_id, token=token)

        start_dt: datetime = appt.appointment_date
        end_dt: datetime = start_dt + timedelta(hours=1)
        tz_name = settings.TZ or "America/Mexico_City"
        reminder_mins = getattr(appt, "reminder_minutes_before", 1440) or 1440

        overrides = [
            {"method": "popup", "minutes": reminder_mins},
            {"method": "email", "minutes": reminder_mins},
        ]
        if reminder_mins != 120:
            overrides.append({"method": "popup", "minutes": 120})

        event_body = {
            "summary": cls.build_event_title(appt, baby_nickname),
            "location": appt.doctor_or_clinic,
            "description": cls.build_event_description(appt, baby_nickname),
            "start": {
                "dateTime": start_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": tz_name,
            },
            "end": {
                "dateTime": end_dt.strftime("%Y-%m-%dT%H:%M:%S"),
                "timeZone": tz_name,
            },
            "reminders": {
                "useDefault": False,
                "overrides": overrides,
            },
        }

        encoded_cal = quote(cal_id, safe="")
        base_url = f"https://www.googleapis.com/calendar/v3/calendars/{encoded_cal}/events"

        if appt.google_event_id:
            encoded_evt = quote(appt.google_event_id, safe="")
            target_url = f"{base_url}/{encoded_evt}"
            method = "PUT"
        else:
            target_url = base_url
            method = "POST"

        try:
            resp_data = cls._api_request(target_url, token, method=method, body=event_body)
            return {
                "synced": True,
                "calendarId": cal_id,
                "eventId": resp_data.get("id"),
                "htmlLink": resp_data.get("htmlLink"),
            }
        except urllib.error.HTTPError as e:
            # Si falló con 404/410 en PUT (el evento fue borrado o cambió de calendario), o si el calendario dio 404:
            if e.code in (404, 410):
                ensured = cls.ensure_accessible_calendar(cal_id, baby_nickname=baby_nickname, token=token)
                if ensured.get("ok") and ensured.get("calendarId"):
                    resolved_cal_id = ensured["calendarId"]
                    new_base_url = f"https://www.googleapis.com/calendar/v3/calendars/{quote(resolved_cal_id, safe='')}/events"
                    try:
                        resp_data = cls._api_request(new_base_url, token, method="POST", body=event_body)
                        return {
                            "synced": True,
                            "calendarId": resolved_cal_id,
                            "autoCreatedCalendar": ensured.get("autoCreated", False),
                            "addCalendarUrl": ensured.get("addCalendarUrl"),
                            "eventId": resp_data.get("id"),
                            "htmlLink": resp_data.get("htmlLink"),
                        }
                    except Exception as inner_exc:
                        return {"synced": False, "reason": str(inner_exc)}
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                pass
            return {"synced": False, "reason": f"HTTP {e.code}: {err_body[:200]}"}
        except Exception as exc:
            return {"synced": False, "reason": str(exc)}

    @classmethod
    def delete_appointment_from_google_calendar(
        cls,
        google_event_id: Optional[str],
        calendar_id: Optional[str],
        token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Elimina un evento de Google Calendar cuando se borra o cancela la cita en BabyTrack."""
        cal_id = (calendar_id or "").strip()
        evt_id = (google_event_id or "").strip()
        if not cal_id or not evt_id:
            return {"deleted": False, "reason": "Sin ID de calendario o de evento."}

        access_token = token or cls._fetch_gcp_access_token()
        if not access_token:
            return {"deleted": False, "reason": "Sin token de acceso GCP."}

        encoded_cal = quote(cal_id, safe="")
        encoded_evt = quote(evt_id, safe="")
        url = f"https://www.googleapis.com/calendar/v3/calendars/{encoded_cal}/events/{encoded_evt}"

        try:
            req = urllib.request.Request(
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                method="DELETE",
            )
            with urllib.request.urlopen(req, timeout=5.0):
                return {"deleted": True}
        except urllib.error.HTTPError as e:
            if e.code in (404, 410):
                return {"deleted": True}
            return {"deleted": False, "reason": f"HTTP {e.code}"}
        except Exception as exc:
            return {"deleted": False, "reason": str(exc)}
