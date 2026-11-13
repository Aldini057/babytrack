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
