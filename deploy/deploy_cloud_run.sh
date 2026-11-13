#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# BabyTrack - Script de Despliegue Automatizado en Google Cloud Run (Costo $0)
# Región: us-central1 (Free Tier) + Bucket GCS montado en /app/data
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

echo "🍼 Desplegando BabyTrack en Google Cloud Run..."
echo "   • Proyecto: $PROJECT_ID"
echo "   • Región:   $REGION"
echo "   • Bucket:   gs://$BUCKET_NAME"

# 1. Habilitar APIs necesarias
gcloud services enable run.googleapis.com storage.googleapis.com cloudbuild.googleapis.com --project "$PROJECT_ID"

# 2. Crear bucket privado si no existe
if ! gcloud storage buckets describe "gs://$BUCKET_NAME" --project "$PROJECT_ID" >/dev/null 2>&1; then
  echo "📦 Creando bucket privado gs://$BUCKET_NAME en $REGION..."
  gcloud storage buckets create "gs://$BUCKET_NAME" \
    --project "$PROJECT_ID" \
    --location "$REGION" \
    --uniform-bucket-level-access
else
  echo "✅ El bucket gs://$BUCKET_NAME ya existe."
fi

# 3. Desplegar servicio Cloud Run Gen2 con volumen GCS montado en /app/data
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

echo "🎉 ¡BabyTrack desplegado con éxito en Google Cloud Run!"
