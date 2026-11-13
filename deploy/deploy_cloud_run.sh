#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# BabyTrack - Script de Despliegue y Actualización Segura en Google Cloud Run
# Región: us-central1 (Free Tier) + Bucket GCS persistente montado en /app/data
# NOTA: Este script NUNCA borra ni sobrescribe los datos existentes en el bucket.
# ==============================================================================

PROJECT_ID="${1:-$(gcloud config get-value project 2>/dev/null || true)}"
REGION="${REGION:-us-central1}"
SERVICE_NAME="${SERVICE_NAME:-babytrack}"
BUCKET_NAME="${BUCKET_NAME:-${PROJECT_ID}-babytrack-data}"
FAMILY_PIN="${FAMILY_ACCESS_PIN:-0707}"

if [[ -z "$PROJECT_ID" ]]; then
  echo "❌ Error: Debes indicar tu PROJECT_ID de Google Cloud."
  echo "Uso: ./deploy/deploy_cloud_run.sh TU_PROJECT_ID"
  exit 1
fi

echo "🍼 Desplegando / Actualizando BabyTrack en Google Cloud Run..."
echo "   • Proyecto: $PROJECT_ID"
echo "   • Región:   $REGION"
echo "   • Bucket:   gs://$BUCKET_NAME (Tus datos guardados se conservan intactos)"

# 1. Habilitar APIs necesarias
gcloud services enable \
  run.googleapis.com \
  storage.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  --project "$PROJECT_ID"

# 2. Asegurar permisos IAM de la cuenta de servicio de construcción/ejecución
PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
if [[ -n "$PROJECT_NUMBER" ]]; then
  echo "🔐 Verificando permisos IAM para ${PROJECT_NUMBER}-compute@developer.gserviceaccount.com..."
  for ROLE in \
    roles/storage.admin \
    roles/logging.logWriter \
    roles/artifactregistry.repoAdmin \
    roles/cloudbuild.builds.builder \
    roles/run.admin; do
    gcloud projects add-iam-policy-binding "$PROJECT_ID" \
      --member="serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
      --role="$ROLE" \
      --quiet >/dev/null 2>&1 || true
  done
fi

# 3. Crear bucket privado SOLO si no existe (jamás borra ni modifica datos existentes)
if ! gcloud storage buckets describe "gs://$BUCKET_NAME" --project "$PROJECT_ID" >/dev/null 2>&1; then
  echo "📦 Creando bucket privado gs://$BUCKET_NAME en $REGION..."
  gcloud storage buckets create "gs://$BUCKET_NAME" \
    --project "$PROJECT_ID" \
    --location "$REGION" \
    --uniform-bucket-level-access
else
  echo "✅ El bucket gs://$BUCKET_NAME ya existe. Conservando base de datos y fotos existentes."
fi

# 4. Desplegar nueva revisión en Cloud Run Gen2 conectada al mismo volumen GCS
gcloud run deploy "$SERVICE_NAME" \
  --project "$PROJECT_ID" \
  --region "$REGION" \
  --source . \
  --execution-environment gen2 \
  --allow-unauthenticated \
  --memory 512Mi \
  --cpu 1 \
  --min-instances 0 \
  --max-instances 2 \
  --set-env-vars "APP_ENV=production,TZ=America/Mexico_City,DATA_DIR=/app/data,DEFAULT_DUE_DATE=2027-07-07,FAMILY_ACCESS_PIN=${FAMILY_PIN}" \
  --add-volume "name=babytrack-data,type=cloud-storage,bucket=${BUCKET_NAME}" \
  --add-volume-mount "volume=babytrack-data,mount-path=/app/data"

echo "🎉 ¡BabyTrack actualizado con éxito en Google Cloud Run sin perder ningún dato!"
