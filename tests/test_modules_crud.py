import io
from pathlib import Path
from PIL import Image
from app.config import settings


def _make_png_bytes(width=120, height=120, color="coral") -> io.BytesIO:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf


def _make_pdf_bytes() -> io.BytesIO:
    return io.BytesIO(
        b"%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Type /Pages /Kids [] /Count 0 >> endobj\n%%EOF\n"
    )


def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["defaultDueDate"] == "2027-07-07"


def test_get_settings_and_metrics(client):
    response = client.get("/api/v1/settings")
    assert response.status_code == 200
    data = response.json()
    assert data["dueDate"] == "2027-07-07"
    assert data["genderMode"] == "SURPRISE"
    assert "gestationalAge" in data
    assert data["gestationalAge"]["weeks"] >= 6


def test_gender_theme_switching(client):
    res_boy = client.put("/api/v1/settings/gender-theme", json={"genderMode": "BOY"})
    assert res_boy.status_code == 200
    assert res_boy.json()["genderMode"] == "BOY"
    assert res_boy.json()["babyNickname"] == "Nuestro Niño"

    res_girl = client.put("/api/v1/settings/gender-theme", json={"genderMode": "GIRL", "babyNickname": "Princesa"})
    assert res_girl.status_code == 200
    assert res_girl.json()["genderMode"] == "GIRL"
    assert res_girl.json()["babyNickname"] == "Princesa"

    res_err = client.put("/api/v1/settings/gender-theme", json={"genderMode": "INVALID"})
    assert res_err.status_code == 400


def test_calibrate_obstetric_endpoint(client):
    res = client.put("/api/v1/settings/obstetric", json={
        "currentWeeks": 7,
        "currentDays": 0,
        "bloodTypeMom": "O+",
        "allergiesNotes": "Penicilina"
    })
    assert res.status_code == 200
    data = res.json()
    assert data["gestationalAge"]["weeks"] == 7
    assert data["gestationalAge"]["days"] == 0
    assert data["bloodTypeMom"] == "O+"
    assert data["allergiesNotes"] == "Penicilina"


def test_render_all_web_pages_and_pwa_assets(client):
    for route, expected in [
        ("/", "BabyTrack"),
        ("/checklist", "Checklist & Presupuesto"),
        ("/journal", "Diario para el Bebé"),
        ("/medical", "Médico, Estudios y Ecos"),
        ("/moments", "Momentos y Bóveda"),
    ]:
        response = client.get(route)
        assert response.status_code == 200
        assert expected in response.text
        assert "/static/manifest.json" in response.text

    # Verificar activos PWA y estáticos
    manifest_res = client.get("/static/manifest.json")
    assert manifest_res.status_code == 200
    manifest_data = manifest_res.json()
    assert manifest_data["short_name"] == "BabyTrack"
    assert len(manifest_data["icons"]) >= 2

    sw_res = client.get("/static/sw.js")
    assert sw_res.status_code == 200
    assert "CACHE_NAME" in sw_res.text

    for icon_path in ["/static/icons/icon-192.png", "/static/icons/icon-512.png", "/static/icons/icon.svg"]:
        icon_res = client.get(icon_path)
        assert icon_res.status_code == 200


def test_family_pin_authentication_flow(client):
    # 1. Estado inicial no autenticado
    st0 = client.get("/api/v1/auth/status")
    assert st0.status_code == 200
    assert st0.json()["authenticated"] is False

    # 2. PIN incorrecto -> 401
    bad = client.post("/api/v1/auth/login", json={"pin": "9999", "activeParent": "PAPA"})
    assert bad.status_code == 401

    # 3. PIN correcto (1419) -> 200 + Cookie HttpOnly firmada
    ok = client.post("/api/v1/auth/login", json={"pin": "1419", "activeParent": "PAPA"})
    assert ok.status_code == 200
    assert ok.json()["authenticated"] is True
    assert ok.json()["activeParent"] == "PAPA"
    assert "babytrack_session" in ok.cookies

    # 4. Verificar sesión persistente mediante la cookie
    st1 = client.get("/api/v1/auth/status")
    assert st1.status_code == 200
    assert st1.json()["authenticated"] is True
    assert st1.json()["activeParent"] == "PAPA"

    # 5. Manipulación de cookie (tampering) debe invalidar sesión
    client.cookies.set("babytrack_session", "PAPA.invalidsignature123")
    st_tampered = client.get("/api/v1/auth/status")
    assert st_tampered.json()["authenticated"] is False

    # 6. Logout limpia estado
    out = client.post("/api/v1/auth/logout")
    assert out.status_code == 200
    assert out.json()["authenticated"] is False


def test_checklist_seed_and_crud(client):
    res_all = client.get("/api/v1/checklist")
    assert res_all.status_code == 200
    items = res_all.json()
    assert len(items) == 24
    categories = {i["category"] for i in items}
    assert categories == {"HABITACION", "TRANSPORTE", "ALIMENTACION", "HIGIENE", "ROPA", "HOSPITAL"}

    # Filtro inválido -> 400
    assert client.get("/api/v1/checklist?category=INEXISTENTE").status_code == 400

    res_create = client.post("/api/v1/checklist", json={
        "category": "ROPA",
        "itemName": "Zapatitos tejidos",
        "description": "Talla recién nacido",
        "trimesterPriority": 3,
        "quantity": 1,
        "estimatedCostMxn": 250.0
    })
    assert res_create.status_code == 201
    item_id = res_create.json()["id"]

    res_toggle = client.patch(f"/api/v1/checklist/{item_id}/toggle", json={
        "completedBy": "PAPA",
        "actualCostMxn": 220.0
    })
    assert res_toggle.status_code == 200
    toggled = res_toggle.json()
    assert toggled["isCompleted"] is True
    assert toggled["completedBy"] == "PAPA"
    assert toggled["actualCostMxn"] == 220.0

    # Segundo toggle desmarca el ítem y limpia completedBy
    res_untoggle = client.patch(f"/api/v1/checklist/{item_id}/toggle")
    assert res_untoggle.status_code == 200
    assert res_untoggle.json()["isCompleted"] is False
    assert res_untoggle.json()["completedBy"] is None

    res_del = client.delete(f"/api/v1/checklist/{item_id}")
    assert res_del.status_code == 204
    assert client.delete(f"/api/v1/checklist/{item_id}").status_code == 404


def test_journal_crud_and_optional_photo(client):
    res_mama = client.post("/api/v1/journal", json={
        "authorRole": "MAMA",
        "title": "Cuando escuchamos tu latido",
        "content": "Hoy confirmamos nuestras semanas rumbo al 7 de julio de 2027."
    })
    assert res_mama.status_code == 201
    note_mama = res_mama.json()
    assert note_mama["authorRole"] == "MAMA"
    assert note_mama["gestationalWeek"] >= 6

    buf = _make_png_bytes(100, 100, "blue")
    res_papa = client.post(
        "/api/v1/journal",
        data={
            "authorRole": "PAPA",
            "title": "Tu primer ultrasonido",
            "content": "No podemos esperar a conocerte."
        },
        files={"photo": ("eco_test.png", buf, "image/png")}
    )
    assert res_papa.status_code == 201
    note_papa = res_papa.json()
    assert note_papa["authorRole"] == "PAPA"
    assert note_papa["attachedImagePath"] is not None
    assert note_papa["attachedImagePath"].startswith("uploads/momentos/")

    res_del = client.delete(f"/api/v1/journal/{note_papa['id']}")
    assert res_del.status_code == 204


def test_medical_appointments_and_consultation_mode(client):
    client.put("/api/v1/settings/obstetric", json={
        "bloodTypeMom": "A+",
        "allergiesNotes": "Ninguna"
    })

    res_done = client.post("/api/v1/medical/appointments", json={
        "appointmentDate": "2026-11-12T10:00:00",
        "doctorOrClinic": "Dra. Sofía Martínez · Hospital Ángeles",
        "momWeightKg": 61.5,
        "bloodPressure": "110/70",
        "babyHeartRateBpm": 148,
        "doctorNotesAndDiagnosis": "Todo excelente, continuar ácido fólico",
        "status": "COMPLETED"
    })
    assert res_done.status_code == 201
    done_appt = res_done.json()
    assert done_appt["gestationalWeek"] == 6
    assert done_appt["gestationalDay"] == 2

    res_sched = client.post("/api/v1/medical/appointments", json={
        "appointmentDate": "2026-12-10T11:30:00",
        "doctorOrClinic": "Dra. Sofía Martínez · Hospital Ángeles",
        "questionsForDoctor": "¿Cuándo hacemos el tamiz del primer trimestre?",
        "status": "SCHEDULED"
    })
    assert res_sched.status_code == 201
    sched_id = res_sched.json()["id"]

    buf = _make_png_bytes(200, 200, "white")
    res_study = client.post(
        "/api/v1/medical/studies",
        data={
            "studyType": "RECETA",
            "title": "Receta Ácido Fólico y Vitaminas",
            "studyDate": "2026-11-12",
            "appointmentId": str(done_appt["id"]),
            "createdBy": "MAMA"
        },
        files=[("files", ("receta.png", buf, "image/png"))]
    )
    assert res_study.status_code == 201

    res_consult = client.get("/api/v1/medical/consultation-mode")
    assert res_consult.status_code == 200
    cm = res_consult.json()
    assert cm["momBloodType"] == "A+"
    assert cm["latestVitals"]["momWeightKg"] == 61.5
    assert len(cm["pendingQuestions"]) == 1
    assert len(cm["recentStudies"]) == 1

    res_del = client.delete(f"/api/v1/medical/appointments/{sched_id}")
    assert res_del.status_code == 204


def test_moments_gallery_and_document_vault_crud(client):
    # 1. Subir fotografía al Álbum de Momentos (/api/v1/moments)
    photo_buf = _make_png_bytes(1600, 1200, "gold")
    res_moment = client.post(
        "/api/v1/moments",
        data={
            "title": "Anuncio a la familia",
            "momentDate": "2026-11-12",
            "caption": "La reacción de los abuelos fue inolvidable",
            "uploadedBy": "MAMA",
        },
        files={"photo": ("anuncio.png", photo_buf, "image/png")},
    )
    assert res_moment.status_code == 201
    moment = res_moment.json()
    assert moment["title"] == "Anuncio a la familia"
    assert moment["gestationalWeek"] == 6
    assert moment["gestationalDay"] == 2
    assert moment["imageRelativePath"].startswith("uploads/momentos/")
    moment_file = Path(settings.DATA_DIR) / moment["imageRelativePath"]
    assert moment_file.exists()

    # Listar momentos y filtrar por autor
    res_list_m = client.get("/api/v1/moments?uploadedBy=MAMA")
    assert res_list_m.status_code == 200
    assert len(res_list_m.json()) == 1

    # 2. Subir PDF de Póliza a la Bóveda de Documentos (/api/v1/vault)
    pdf_buf = _make_pdf_bytes()
    res_vault_pdf = client.post(
        "/api/v1/vault",
        data={
            "category": "POLIZA",
            "title": "Póliza Gastos Médicos Mayores 2027",
            "notes": "Cobertura maternidad hospitalaria",
            "uploadedBy": "PAPA",
        },
        files={"file": ("poliza_gmm.pdf", pdf_buf, "application/pdf")},
    )
    assert res_vault_pdf.status_code == 201
    vault_doc = res_vault_pdf.json()
    assert vault_doc["category"] == "POLIZA"
    assert vault_doc["fileCategory"] == "PDF"
    assert vault_doc["storedRelativePath"].startswith("uploads/documentos/")
    vault_file = Path(settings.DATA_DIR) / vault_doc["storedRelativePath"]
    assert vault_file.exists()

    # Subir imagen de carnet perinatal a la bóveda
    carnet_buf = _make_png_bytes(800, 600, "lightblue")
    res_vault_img = client.post(
        "/api/v1/vault",
        data={
            "category": "CARNET",
            "title": "Carnet Perinatal Portada",
            "uploadedBy": "MAMA",
        },
        files={"file": ("carnet.png", carnet_buf, "image/png")},
    )
    assert res_vault_img.status_code == 201
    assert res_vault_img.json()["fileCategory"] == "IMAGE"

    # Filtrar bóveda por categoría
    res_polizas = client.get("/api/v1/vault?category=POLIZA")
    assert res_polizas.status_code == 200
    assert len(res_polizas.json()) == 1

    # 3. Eliminar momento y documento verificando limpieza física en disco
    assert client.delete(f"/api/v1/moments/{moment['id']}").status_code == 204
    assert not moment_file.exists()

    assert client.delete(f"/api/v1/vault/{vault_doc['id']}").status_code == 204
    assert not vault_file.exists()
