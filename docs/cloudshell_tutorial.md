# 🍼 Despliegue en 1 Clic de BabyTrack en Google Cloud Run

¡Bienvenido al asistente interactivo de despliegue de **BabyTrack**!

## Paso 1: Selecciona tu proyecto de Google Cloud
Ejecuta el siguiente comando (o verifica que tu proyecto esté activo):
```bash
gcloud config set project $(gcloud projects list --format='value(PROJECT_ID)' --limit=1)
```

## Paso 2: Publicar BabyTrack con URL Pública (`.run.app`) y Persistencia
Ejecuta nuestro script oficial que crea el bucket de almacenamiento en `us-central1` y despliega el contenedor en **Google Cloud Run** con acceso público (`--allow-unauthenticated`):
```bash
chmod +x deploy/deploy_cloud_run.sh
./deploy/deploy_cloud_run.sh $(gcloud config get-value project)
```

Al terminar, la consola imprimirá tu link público `https://babytrack-xxxx.us-central1.run.app` listo para compartir con toda la familia.
