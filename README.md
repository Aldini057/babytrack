# 🍼 BabyTrack — Seguimiento Obstétrico, Preparativos y Cápsula Familiar

[![Run on Google Cloud](https://deploy.cloud.run/button.svg)](https://deploy.cloud.run/?git_repo=https://github.com/Aldini057/babytrack)
[![Open in Cloud Shell](https://gstatic.com/cloudssh/images/open-btn.svg)](https://ssh.cloud.google.com/cloudshell/editor?cloudshell_git_repo=https://github.com/Aldini057/babytrack&cloudshell_tutorial=docs/cloudshell_tutorial.md)

**Plataforma Web Full-Stack Mobile-First (PWA) para el Seguimiento del Embarazo rumbo al `07/07/2027`**

- **Fecha Probable de Parto (FPP):** 07 de julio de 2027 (`2027-07-07`) — 40 Semanas (280 días)
- **Zona Horaria:** `America/Mexico_City`
- **Stack:** Python 3.11 + FastAPI + SQLAlchemy 2.0 + Pydantic v2 + Pillow + TailwindCSS + Alpine.js + PWA
- **Despliegue Serverless:** Google Cloud Run (`us-central1`) + Google Cloud Storage (Costo \$0 USD cubierto por Free Tier / Créditos Google Developer Program)

---

## ☁️ Despliegue en 1 Clic en Google Cloud Run (Link Público `.run.app`)

Tienes dos formas directas de generar tu URL pública `https://babytrack-xxxx.us-central1.run.app` para compartir con quien quieras:

1. **Opción A — Botón Directo (Cloud Run Button):**  
   Haz clic en **[👉 Desplegar en Google Cloud Run](https://deploy.cloud.run/?git_repo=https://github.com/Aldini057/babytrack)**, elige tu proyecto de Google Cloud y la región `us-central1`.
2. **Opción B — Asistente con Bucket Persistente en Cloud Shell (Recomendado):**  
   Haz clic en **[👉 Abrir en Google Cloud Shell con Tutorial](https://ssh.cloud.google.com/cloudshell/editor?cloudshell_git_repo=https://github.com/Aldini057/babytrack&cloudshell_tutorial=docs/cloudshell_tutorial.md)** y ejecuta:
   ```bash
   chmod +x deploy/deploy_cloud_run.sh
   ./deploy/deploy_cloud_run.sh $(gcloud config get-value project)
   ```

---

## ✨ Los 5 Módulos Completos (Sprints 1 a 4)

1. **Módulo 1 — Dashboard Obstétrico, Tema Dinámico y Modo Consulta Médica (`/`)**
   - Cálculo matemático en tiempo real hacia el `07/07/2027` (`6 semanas, 2 días`, porcentaje, días restantes y tamaño comparativo).
   - Cambio instantáneo de identidad visual por género (`SURPRISE`, `BOY`, `GIRL`) con lluvia de confeti.
   - Botón **Modo Consulta Médica** en un toque con últimos signos vitales, preguntas pendientes y estudios recientes.
2. **Módulo 2 — Checklist Interactiva y Presupuesto por Trimestre (`/checklist`)**
   - 24 artículos esenciales precargados en 6 categorías (`HABITACION`, `TRANSPORTE`, `ALIMENTACION`, `HIGIENE`, `ROPA`, `HOSPITAL`).
   - Control de costo estimado vs. real en MXN y registro de quién completó cada compra (`Mamá` o `Papá`).
3. **Módulo 3 — Control Prenatal, Estudios Híbridos 1:N y Galería de Ecos (`/medical`)**
   - Subida multiparte simultánea de fotografías de recetas/indicaciones (optimizadas con `Pillow` a máx. 2000px) e informes `application/pdf` intactos.
   - Línea de tiempo exclusiva de ultrasonidos (`uploads/ecos/`) y **Visor Modal Integrado** (Lightbox con zoom para imágenes + `<iframe>` para PDFs).
4. **Módulo 4 — Álbum Fotográfico de Momentos y Bóveda de Documentos (`/moments`)**
   - Galería cronológica de momentos con etiquetado automático de semana y día gestacional (`uploads/momentos/`).
   - Bóveda clínica y administrativa categorizada para pólizas, carnets perinatales, identificaciones y órdenes de ingreso (`uploads/documentos/`).
5. **Módulo 5 — Diario de Cartas y Pensamientos para el Bebé (`/journal`)**
   - Bitácora emocional con autoría explícita (`Escrito por Mamá` / `Escrito por Papá`), estilos visuales diferenciados, foto opcional y filtro por autor.

---

## 🚀 Ejecución en Docker Local y Pruebas

### En Docker Local:
```bash
docker compose -f deploy/docker-compose.yml up -d --build
```

### Suite de Pruebas Automatizadas (Pytest - 37 Tests):
```bash
pytest -v
```
