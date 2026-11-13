import io
import uuid
from datetime import datetime
from pathlib import Path
from typing import Tuple
from fastapi import UploadFile, HTTPException, status
from PIL import Image, ImageOps

from app.config import settings

ALLOWED_IMAGE_MIMES = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
ALLOWED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_PDF_MIMES = {"application/pdf"}
ALLOWED_PDF_EXTS = {".pdf"}


class HybridStorageService:
    """
    Servicio de almacenamiento híbrido:
    - Optimiza y comprime fotografías con Pillow (calidad 85%, ancho máx 2000px).
    - Conserva intactos los documentos PDF.
    - Organiza en /app/data/uploads/{ecos,estudios,documentos,momentos}.
    """

    @classmethod
    def get_uploads_base(cls) -> Path:
        return Path(settings.DATA_DIR) / "uploads"

    @classmethod
    def resolve_study_subfolder(cls, study_type: str) -> str:
        mapping = {
            "ULTRASONIDO": "ecos",
            "DOCUMENTO_CLINICO": "documentos",
            "LABORATORIO": "estudios",
            "RECETA": "estudios",
        }
        return mapping.get((study_type or "").upper(), "estudios")

    @classmethod
    def _compress_image_bytes(cls, raw_bytes: bytes, max_width: int = 2000, quality: int = 85) -> bytes:
        try:
            img = Image.open(io.BytesIO(raw_bytes))
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")

            if img.width > max_width:
                ratio = max_width / float(img.width)
                new_height = int(float(img.height) * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)

            output_buffer = io.BytesIO()
            img.save(output_buffer, format="JPEG", quality=quality, optimize=True)
            return output_buffer.getvalue()
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"No se pudo procesar la imagen: {str(exc)}",
            )

    @classmethod
    async def save_image(
        cls,
        file: UploadFile,
        subfolder: str = "momentos",
        max_width: int = 2000,
        quality: int = 85,
    ) -> Tuple[str, str, int]:
        """
        Guarda una imagen optimizada y devuelve (relative_path, mime_type, size_bytes).
        """
        content_type = (file.content_type or "").lower()
        filename = file.filename or "image.jpg"
        ext = Path(filename).suffix.lower()

        if content_type not in ALLOWED_IMAGE_MIMES and ext not in ALLOWED_IMAGE_EXTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Formato de imagen no soportado: {content_type or ext}",
            )

        raw_bytes = await file.read()
        if not raw_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo de imagen está vacío.",
            )

        optimized_bytes = cls._compress_image_bytes(raw_bytes, max_width=max_width, quality=quality)

        target_dir = cls.get_uploads_base() / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)

        date_prefix = datetime.utcnow().strftime("%Y-%m-%d")
        unique_name = f"{date_prefix}_{uuid.uuid4().hex[:8]}.jpg"
        target_path = target_dir / unique_name

        target_path.write_bytes(optimized_bytes)

        relative_path = f"uploads/{subfolder}/{unique_name}"
        return relative_path, "image/jpeg", len(optimized_bytes)

    @classmethod
    async def save_hybrid_file(
        cls,
        file: UploadFile,
        subfolder: str = "estudios",
        max_width: int = 2000,
        quality: int = 85,
    ) -> Tuple[str, str, str, int]:
        """
        Guarda archivos híbridos (Imagen o PDF).
        Devuelve (relative_path, mime_type, file_category['IMAGE'|'PDF'], size_bytes).
        """
        content_type = (file.content_type or "").lower()
        filename = file.filename or "archivo"
        ext = Path(filename).suffix.lower()

        is_pdf = content_type in ALLOWED_PDF_MIMES or ext in ALLOWED_PDF_EXTS
        is_image = content_type in ALLOWED_IMAGE_MIMES or ext in ALLOWED_IMAGE_EXTS

        if not is_pdf and not is_image:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Formato no permitido ({filename}): solo se aceptan imágenes (JPG/PNG/WEBP) o PDF.",
            )

        raw_bytes = await file.read()
        if not raw_bytes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El archivo '{filename}' está vacío.",
            )

        target_dir = cls.get_uploads_base() / subfolder
        target_dir.mkdir(parents=True, exist_ok=True)
        date_prefix = datetime.utcnow().strftime("%Y-%m-%d")

        if is_pdf:
            if not raw_bytes.lstrip().startswith(b"%PDF"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"El archivo '{filename}' no es un PDF válido.",
                )
            unique_name = f"{date_prefix}_{uuid.uuid4().hex[:8]}.pdf"
            target_path = target_dir / unique_name
            target_path.write_bytes(raw_bytes)
            relative_path = f"uploads/{subfolder}/{unique_name}"
            return relative_path, "application/pdf", "PDF", len(raw_bytes)

        # Imagen: compresión inteligente manteniendo nitidez clínica
        optimized_bytes = cls._compress_image_bytes(raw_bytes, max_width=max_width, quality=quality)
        unique_name = f"{date_prefix}_{uuid.uuid4().hex[:8]}.jpg"
        target_path = target_dir / unique_name
        target_path.write_bytes(optimized_bytes)
        relative_path = f"uploads/{subfolder}/{unique_name}"
        return relative_path, "image/jpeg", "IMAGE", len(optimized_bytes)

    @classmethod
    def delete_file(cls, relative_path: str) -> None:
        if not relative_path:
            return
        full_path = Path(settings.DATA_DIR) / relative_path
        if full_path.exists() and full_path.is_file():
            full_path.unlink()
