import io
from pathlib import Path
from PIL import Image
from app.config import settings


def _make_png_bytes(width=2400, height=1200, color="teal") -> io.BytesIO:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _make_pdf_bytes() -> io.BytesIO:
    pdf_content = (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [] /Count 0 >> endobj\n"
        b"%%EOF\n"
    )
    return io.BytesIO(pdf_content)


def test_simultaneous_pdf_and_images_upload(client):
    """
    Verifica que un solo estudio clínico acepte simultáneamente 1 PDF de laboratorio
    y 2 fotografías (recetas/indicaciones), optimizando imágenes con Pillow y
    conservando íntegro el PDF.
    """
    pdf_buf = _make_pdf_bytes()
    img1_buf = _make_png_bytes(width=2600, height=1300, color="navy")
    img2_buf = _make_png_bytes(width=800, height=600, color="green")

    res = client.post(
        "/api/v1/medical/studies",
        data={
            "studyType": "LABORATORIO",
            "title": "Biometría Hemática y Receta 1er Trimestre",
            "studyDate": "2026-11-12",
            "summaryNotes": "Hemoglobina y glucosa en rangos óptimos",
            "createdBy": "PAPA",
        },
        files=[
            ("files", ("resultado_lab.pdf", pdf_buf, "application/pdf")),
            ("files", ("receta_frente.png", img1_buf, "image/png")),
            ("files", ("indicaciones.jpg", img2_buf, "image/jpeg")),
        ],
    )

    assert res.status_code == 201
    study = res.json()
    assert study["studyType"] == "LABORATORIO"
    assert study["gestationalWeek"] == 6
    assert study["gestationalDay"] == 2
    assert len(study["attachments"]) == 3

    pdf_att = study["attachments"][0]
    img1_att = study["attachments"][1]
    img2_att = study["attachments"][2]

    assert pdf_att["fileCategory"] == "PDF"
    assert pdf_att["mimeType"] == "application/pdf"
    assert pdf_att["storedRelativePath"].startswith("uploads/estudios/")

    assert img1_att["fileCategory"] == "IMAGE"
    assert img1_att["mimeType"] == "image/jpeg"
    assert img1_att["storedRelativePath"].startswith("uploads/estudios/")

    assert img2_att["fileCategory"] == "IMAGE"
    assert img2_att["mimeType"] == "image/jpeg"

    # Verificar que la imagen > 2000px fue redimensionada a max_width=2000
    img1_disk = Path(settings.DATA_DIR) / img1_att["storedRelativePath"]
    assert img1_disk.exists()
    with Image.open(img1_disk) as saved_img:
        assert saved_img.width == 2000
        assert saved_img.height == 1000

    # Verificar que el PDF existe íntegro en disco
    pdf_disk = Path(settings.DATA_DIR) / pdf_att["storedRelativePath"]
    assert pdf_disk.exists()
    assert pdf_disk.read_bytes().startswith(b"%PDF-1.4")

    # Agregar archivo adicional al estudio existente
    extra_img = _make_png_bytes(width=400, height=400, color="purple")
    res_add = client.post(
        f"/api/v1/medical/studies/{study['id']}/attachments",
        files=[("files", ("nota_extra.png", extra_img, "image/png"))],
    )
    assert res_add.status_code == 201
    assert len(res_add.json()["attachments"]) == 4

    # Eliminar estudio y verificar limpieza de archivos físicos
    res_del = client.delete(f"/api/v1/medical/studies/{study['id']}")
    assert res_del.status_code == 204
    assert not pdf_disk.exists()
    assert not img1_disk.exists()


def test_ultrasound_gallery_and_ecos_subfolder(client):
    """Verifica que los ultrasonidos se guarden en uploads/ecos/ y aparezcan en /ultrasounds."""
    eco_img = _make_png_bytes(width=1200, height=900, color="gray")
    eco_pdf = _make_pdf_bytes()

    res = client.post(
        "/api/v1/medical/studies",
        data={
            "studyType": "ULTRASONIDO",
            "title": "Primer Ultrasonido Obstétrico",
            "studyDate": "2026-11-12",
            "summaryNotes": "Latido presente",
            "createdBy": "MAMA",
        },
        files=[
            ("files", ("eco_6s2d.png", eco_img, "image/png")),
            ("files", ("reporte_eco.pdf", eco_pdf, "application/pdf")),
        ],
    )
    assert res.status_code == 201
    eco = res.json()
    assert all(att["storedRelativePath"].startswith("uploads/ecos/") for att in eco["attachments"])

    res_list = client.get("/api/v1/medical/ultrasounds")
    assert res_list.status_code == 200
    ultrasounds = res_list.json()
    assert len(ultrasounds) == 1
    assert ultrasounds[0]["title"] == "Primer Ultrasonido Obstétrico"


def test_reject_invalid_file_type_and_fake_pdf(client):
    """Verifica rechazo de archivos no permitidos (.exe/.txt) y PDFs falsos."""
    res_txt = client.post(
        "/api/v1/medical/studies",
        data={
            "studyType": "RECETA",
            "title": "Archivo inválido",
            "studyDate": "2026-11-12",
        },
        files=[("files", ("script.txt", io.BytesIO(b"hello"), "text/plain"))],
    )
    assert res_txt.status_code == 400

    res_fake_pdf = client.post(
        "/api/v1/medical/studies",
        data={
            "studyType": "LABORATORIO",
            "title": "PDF corrupto",
            "studyDate": "2026-11-12",
        },
        files=[("files", ("fake.pdf", io.BytesIO(b"NOT_A_PDF"), "application/pdf"))],
    )
    assert res_fake_pdf.status_code == 400


def test_appointments_by_type_medico_laboratorio_eco(client):
    """
    Verifica que se puedan agendar citas de tipo MEDICO, LABORATORIO y ECO
    sin requerir documentos y filtrarlas por tipo.
    """
    res_med = client.post(
        "/api/v1/medical/appointments",
        json={
            "appointmentType": "MEDICO",
            "appointmentDate": "2026-12-01T10:00:00",
            "doctorOrClinic": "Dra. García · Control Mensual",
            "questionsForDoctor": "¿Puedo tomar magnesio?",
        },
    )
    assert res_med.status_code == 201
    assert res_med.json()["appointmentType"] == "MEDICO"
    assert res_med.json()["specialty"] == "Ginecología y Obstetricia"

    res_lab = client.post(
        "/api/v1/medical/appointments",
        json={
            "appointmentType": "LABORATORIO",
            "appointmentDate": "2026-12-05T07:30:00",
            "doctorOrClinic": "Laboratorio Chopo · Curva de Tolerancia",
            "questionsForDoctor": "Ayuno de 8 horas",
        },
    )
    assert res_lab.status_code == 201
    assert res_lab.json()["appointmentType"] == "LABORATORIO"
    assert res_lab.json()["specialty"] == "Análisis Clínicos / Laboratorio"

    res_eco = client.post(
        "/api/v1/medical/appointments",
        json={
            "appointmentType": "ECO",
            "appointmentDate": "2026-12-10T16:00:00",
            "doctorOrClinic": "Dr. Morales · Eco Genético",
        },
    )
    assert res_eco.status_code == 201
    assert res_eco.json()["appointmentType"] == "ECO"
    assert res_eco.json()["specialty"] == "Ultrasonido Obstétrico"

    # Filtrar solo citas de LABORATORIO
    list_lab = client.get("/api/v1/medical/appointments?type=LABORATORIO")
    assert list_lab.status_code == 200
    assert len(list_lab.json()) == 1
    assert list_lab.json()[0]["appointmentType"] == "LABORATORIO"

    # Filtrar solo citas de ECO
    list_eco = client.get("/api/v1/medical/appointments?type=ECO")
    assert list_eco.status_code == 200
    assert len(list_eco.json()) == 1
    assert list_eco.json()[0]["appointmentType"] == "ECO"


def test_studies_without_documents_for_lab_and_medical_visits(client):
    """
    Verifica que en Laboratorio (LABORATORIO) y en Resultados de Visitas Médicas
    (DIAGNOSTICO y RECETA) se pueda guardar sin adjuntar ningún documento (0 archivos),
    y opcionalmente adjuntar archivos después.
    """
    # 1. Guardar resultado de Laboratorio sin documento
    res_lab = client.post(
        "/api/v1/medical/studies",
        data={
            "studyType": "LABORATORIO",
            "title": "Glucosa en ayuno y EGO",
            "studyDate": "2026-11-15",
            "summaryNotes": "Glucosa: 82 mg/dL, EGO negativo a infección.",
            "createdBy": "MAMA",
        },
    )
    assert res_lab.status_code == 201
    lab_data = res_lab.json()
    assert lab_data["studyType"] == "LABORATORIO"
    assert lab_data["attachments"] == []
    assert "Glucosa: 82 mg/dL" in lab_data["summaryNotes"]

    # 2. Guardar Diagnóstico de Visita Médica sin documento
    res_diag = client.post(
        "/api/v1/medical/studies",
        data={
            "studyType": "DIAGNOSTICO",
            "title": "Consulta 1er Trimestre - Evolución Normal",
            "studyDate": "2026-11-16",
            "summaryNotes": "Embarazo normoevolutivo, continuar ácido fólico y buena hidratación.",
            "createdBy": "PAPA",
        },
    )
    assert res_diag.status_code == 201
    diag_data = res_diag.json()
    assert diag_data["studyType"] == "DIAGNOSTICO"
    assert diag_data["attachments"] == []

    # 3. Guardar Receta Médica sin documento y luego adjuntarle foto de la receta
    res_rec = client.post(
        "/api/v1/medical/studies",
        data={
            "studyType": "RECETA",
            "title": "Receta Vitaminas Prenatales Regenesis Max",
            "studyDate": "2026-11-16",
            "summaryNotes": "1 cápsula diaria por las mañanas.",
            "createdBy": "MAMA",
        },
    )
    assert res_rec.status_code == 201
    rec_data = res_rec.json()
    assert rec_data["studyType"] == "RECETA"
    assert rec_data["attachments"] == []

    # Adjuntar foto posteriormente al registro que se creó sin documento
    rec_img = _make_png_bytes(width=600, height=800, color="white")
    res_attach = client.post(
        f"/api/v1/medical/studies/{rec_data['id']}/attachments",
        files=[("files", ("foto_receta.png", rec_img, "image/png"))],
    )
    assert res_attach.status_code == 201
    assert len(res_attach.json()["attachments"]) == 1


def test_non_destructive_schema_migration_preserves_existing_rows(tmp_path):
    """
    Simula una base de datos SQLite existente en producción (antes de la columna appointment_type)
    con citas ya guardadas, y verifica que ensure_schema_migrations agregue la columna
    sin perder ningún registro previo.
    """
    from sqlalchemy import create_engine, text
    from app.database import ensure_schema_migrations

    legacy_db_path = tmp_path / "legacy_babytrack.db"
    legacy_engine = create_engine(f"sqlite:///{legacy_db_path}")

    with legacy_engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE medical_appointments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    appointment_date DATETIME NOT NULL,
                    gestational_week INTEGER NOT NULL,
                    gestational_day INTEGER NOT NULL,
                    doctor_or_clinic VARCHAR(160) NOT NULL,
                    specialty VARCHAR(100) NOT NULL,
                    status VARCHAR(30) NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO medical_appointments
                (appointment_date, gestational_week, gestational_day, doctor_or_clinic, specialty, status)
                VALUES ('2026-11-20 10:00:00', 7, 3, 'Dra. Existente', 'Obstetricia', 'SCHEDULED')
                """
            )
        )

    # Ejecutar migración aditiva segura
    ensure_schema_migrations(legacy_engine)

    with legacy_engine.connect() as conn:
        row = conn.execute(
            text("SELECT doctor_or_clinic, appointment_type, reminder_minutes_before FROM medical_appointments WHERE id = 1")
        ).fetchone()
        assert row is not None
        assert row[0] == "Dra. Existente"
        assert row[1] == "MEDICO"
        assert row[2] == 1440


def test_google_calendar_links_ics_and_1_day_before_alerts(client):
    """
    Verifica las 2 opciones de Google Calendar juntas + sistema de alerta de 1 día antes:
    1. Enlace directo a Google Calendar (googleCalendarTemplateUrl) y recordatorio por defecto (1440 min = 24h).
    2. Archivo .ics individual y feed .ics completo con alarmas VALARM (-PT1440M y -PT120M) + FPP (-P1D).
    3. Configuración de ID de Google Calendar para sincronización automática API.
    """
    res = client.post(
        "/api/v1/medical/appointments",
        json={
            "appointmentType": "LABORATORIO",
            "appointmentDate": "2026-12-15T08:00:00",
            "doctorOrClinic": "Salud Digna · Biometría y Glucosa",
            "questionsForDoctor": "Ayuno estricto de 8 horas",
            "reminderMinutesBefore": 1440,
        },
    )
    assert res.status_code == 201
    appt = res.json()
    assert appt["reminderMinutesBefore"] == 1440
    assert "calendar.google.com/calendar/render?action=TEMPLATE" in appt["googleCalendarTemplateUrl"]
    assert "20261215T080000" in appt["googleCalendarTemplateUrl"]

    # Descargar .ics individual con alarma de 1 día antes (-PT1440M) y 2 horas antes (-PT120M)
    ics_single = client.get(f"/api/v1/medical/appointments/{appt['id']}/calendar.ics")
    assert ics_single.status_code == 200
    assert "text/calendar" in ics_single.headers["content-type"]
    assert "BEGIN:VCALENDAR" in ics_single.text
    assert "TRIGGER:-PT1440M" in ics_single.text
    assert "TRIGGER:-PT120M" in ics_single.text
    assert "Salud Digna" in ics_single.text

    # Descargar feed .ics completo (incluye la cita + la Fecha Probable de Parto FPP con TRIGGER:-P1D)
    ics_feed = client.get("/api/v1/medical/calendar.ics")
    assert ics_feed.status_code == 200
    assert "Fecha Probable de Parto (FPP)" in ics_feed.text
    assert "TRIGGER:-P1D" in ics_feed.text
    assert "TRIGGER:-PT1440M" in ics_feed.text

    # Configurar correo de Google Calendar para auto-sync (Opción 2)
    cfg_put = client.put(
        "/api/v1/medical/calendar/config",
        json={"googleCalendarId": "darielgameplay@gmail.com"},
    )
    assert cfg_put.status_code == 200
    assert cfg_put.json()["googleCalendarId"] == "darielgameplay@gmail.com"
    assert cfg_put.json()["isConfigured"] is True

    cfg_get = client.get("/api/v1/medical/calendar/config")
    assert cfg_get.status_code == 200
    assert cfg_get.json()["googleCalendarId"] == "darielgameplay@gmail.com"


def test_family_share_public_view_and_guestbook_notes(client):
    """
    Verifica la vista pública compartible (/familia y /compartir):
    - Muestra en solo lectura el género, semanas/días, porcentaje, tamaño equivalente y galería de ecos.
    - No expone controles de edición de género ni calibración.
    - Permite que familiares dejen notas con su nombre y parentesco (authorRole='FAMILIA').
    """
    # 1. Subir un eco para verificar que aparece en la vista familiar
    eco_img = _make_png_bytes(width=800, height=600, color="purple")
    client.post(
        "/api/v1/medical/studies",
        data={
            "studyType": "ULTRASONIDO",
            "title": "Eco Compartido con la Familia",
            "studyDate": "2026-11-12",
            "summaryNotes": "¡Saludo para los abuelos!",
            "createdBy": "MAMA",
        },
        files=[("files", ("eco_familia.png", eco_img, "image/png"))],
    )

    # 2. Un familiar deja una nota con su nombre y parentesco
    res_note = client.post(
        "/api/v1/journal",
        data={
            "authorRole": "FAMILIA",
            "authorDisplayName": "Abuelita Carmen (Abuela Materna)",
            "title": "¡Te esperamos con mucho amor!",
            "content": "Ya queremos conocerte y consentirte mucho.",
        },
    )
    assert res_note.status_code == 201
    note_data = res_note.json()
    assert note_data["authorRole"] == "FAMILIA"
    assert note_data["authorDisplayName"] == "Abuelita Carmen (Abuela Materna)"

    # 3. Filtrar notas de FAMILIA desde el API
    res_fam_notes = client.get("/api/v1/journal?author=FAMILIA")
    assert res_fam_notes.status_code == 200
    assert len(res_fam_notes.json()) == 1
    assert res_fam_notes.json()[0]["authorDisplayName"] == "Abuelita Carmen (Abuela Materna)"

    # 4. Verificar renderizado de /familia y /compartir en modo solo lectura
    for path in ("/familia", "/compartir"):
        page = client.get(path)
        assert page.status_code == 200
        assert "Vista Familiar Compartida" in page.text
        assert "del embarazo completado" in page.text
        assert "Tamaño equivalente hoy" in page.text
        assert "Eco Compartido con la Familia" in page.text
        assert "Abuelita Carmen (Abuela Materna)" in page.text
        # Asegurar que no incluye botones para cambiar el género ni calibrar fechas
        assert "updateGenderTheme" not in page.text
        assert "Calibrar Semanas" not in page.text




