# 🍼 BabyTrack — Arquitectura, Decisiones de Diseño (ADR) y Guía Cloud Run

## 1. Visión Arquitectónica
BabyTrack es un monolito modular contenedorizado en **Python 3.11 + FastAPI + SQLAlchemy 2.0 + Jinja2/TailwindCSS/Alpine.js**, diseñado con enfoque *Mobile-First* e instalable como **PWA** en Android e iOS.

## 2. Registro de Decisiones de Arquitectura (ADR)
- **ADR-01 (Persistencia Unificada `/app/data`):** Tanto la base de datos SQLite (`babytrack.db`) como las 4 carpetas de archivos (`uploads/ecos`, `uploads/estudios`, `uploads/documentos`, `uploads/momentos`) residen bajo `/app/data`. Esto permite montar `./data:/app/data` en Docker local y montar un bucket de **Google Cloud Storage** en Cloud Run Gen2 sin cambiar una sola línea de código.
- **ADR-02 (Soporte Híbrido 1:N):** Cada estudio médico o ultrasonido (`MedicalStudy`) posee relación `1:N` con `StudyAttachment`, permitiendo subir simultáneamente PDFs de laboratorio (conservados íntegros) e imágenes de recetas/ecos (optimizadas con `Pillow` a máx. 2000px y calidad 85%).
- **ADR-03 (Tema Reactivo por Género):** Atributo `data-theme="SURPRISE|BOY|GIRL"` en `<html>` gobernando variables CSS semánticas y disparando confeti temático en el navegador.
- **ADR-04 (Seguridad Familiar Ligera):** Acceso protegido con PIN compartido (`0707` configurable vía `FAMILY_ACCESS_PIN`) y cookie firmada `HttpOnly` con HMAC-SHA256.

## 3. Despliegue a Producción en Google Cloud Run
Ejecuta el script automatizado:
```bash
chmod +x deploy/deploy_cloud_run.sh
./deploy/deploy_cloud_run.sh TU_PROJECT_ID
```
