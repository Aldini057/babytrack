from datetime import date, datetime
from typing import Optional, Dict, Any
import pytz
from app.config import settings

class ObstetricCalculatorService:
    TOTAL_GESTATIONAL_DAYS = 280  # 40 semanas exactas

    @classmethod
    def get_local_date(cls, tz_name: Optional[str] = None) -> date:
        """Obtiene la fecha actual en la zona horaria configurada."""
        tz = pytz.timezone(tz_name or settings.TZ)
        return datetime.now(tz).date()

    @classmethod
    def calculate_metrics(
        cls,
        due_date: date,
        calibration_offset_days: int = 0,
        current_date: Optional[date] = None,
        tz_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calcula las métricas gestacionales completas basadas en la FPP y calibración.
        """
        if current_date is None:
            current_date = cls.get_local_date(tz_name)

        days_remaining = (due_date - current_date).days
        elapsed_days = (cls.TOTAL_GESTATIONAL_DAYS - days_remaining) + calibration_offset_days

        # Prevenir valores negativos irreales
        display_elapsed = max(0, elapsed_days)
        current_week = display_elapsed // 7
        current_day = display_elapsed % 7

        # Porcentaje de progreso
        progress_percent = round((display_elapsed / cls.TOTAL_GESTATIONAL_DAYS) * 100, 1)
        progress_percent = max(0.0, min(100.0, progress_percent))

        # Trimestre
        if display_elapsed <= 97:  # Semanas 1 a 13
            trimester = 1
            trimester_name = "1er Trimestre"
        elif display_elapsed <= 195:  # Semanas 14 a 27
            trimester = 2
            trimester_name = "2do Trimestre"
        else:  # Semanas 28 a 40+
            trimester = 3
            trimester_name = "3er Trimestre"

        # Tamaño comparativo del bebé
        size_comparison = cls.get_size_comparison(current_week)

        return {
            "dueDate": due_date.isoformat(),
            "currentDate": current_date.isoformat(),
            "daysRemaining": max(0, days_remaining),
            "elapsedDays": display_elapsed,
            "weeks": current_week,
            "days": current_day,
            "progressPercent": progress_percent,
            "trimester": trimester,
            "trimesterName": trimester_name,
            "sizeComparison": size_comparison["size_text"],
            "sizeWeight": size_comparison["weight_length"],
            "calibrationOffsetDays": calibration_offset_days
        }

    @classmethod
    def calculate_offset_from_weeks_days(
        cls,
        due_date: date,
        target_weeks: int,
        target_days: int,
        current_date: Optional[date] = None,
        tz_name: Optional[str] = None
    ) -> int:
        """
        Calcula el calibration_offset_days necesario para que la fecha actual
        refleje exactamente target_weeks y target_days.
        """
        if current_date is None:
            current_date = cls.get_local_date(tz_name)

        target_elapsed_days = (target_weeks * 7) + target_days
        standard_elapsed = cls.TOTAL_GESTATIONAL_DAYS - (due_date - current_date).days
        return target_elapsed_days - standard_elapsed

    @classmethod
    def get_size_comparison(cls, week: int) -> Dict[str, str]:
        """Devuelve el tamaño comparativo y peso/longitud según la semana gestacional."""
        if week < 4:
            return {
                "size_text": "Óvulo fertilizado / Blastocisto",
                "weight_length": "0.1 - 0.2 mm"
            }
        elif 4 <= week <= 5:
            return {
                "size_text": "Semilla de amapola / Sésamo",
                "weight_length": "1 - 3 mm"
            }
        elif 6 <= week <= 7:
            return {
                "size_text": "Lenteja / Arándano",
                "weight_length": "4 - 10 mm"
            }
        elif 8 <= week <= 10:
            return {
                "size_text": "Frambuesa / Fresa",
                "weight_length": "1.6 - 3.1 cm"
            }
        elif 11 <= week <= 13:
            return {
                "size_text": "Higo / Limón / Durazno",
                "weight_length": "4.1 - 7.4 cm (~8 - 23 g)"
            }
        elif 14 <= week <= 17:
            return {
                "size_text": "Manzana / Aguacate / Pera",
                "weight_length": "8.7 - 13 cm (~43 - 140 g)"
            }
        elif 18 <= week <= 22:
            return {
                "size_text": "Pimiento / Mango / Papaya",
                "weight_length": "14.2 - 27.8 cm (~190 - 430 g)"
            }
        elif 23 <= week <= 27:
            return {
                "size_text": "Elote / Coliflor",
                "weight_length": "28.9 - 36.6 cm (~500 - 875 g)"
            }
        elif 28 <= week <= 33:
            return {
                "size_text": "Berenjena / Coco / Piña",
                "weight_length": "37.6 - 43.7 cm (~1.0 - 1.9 kg)"
            }
        elif 34 <= week <= 40:
            return {
                "size_text": "Melón / Sandía",
                "weight_length": "45.0 - 51.2 cm (~2.1 - 3.5 kg)"
            }
        else:
            return {
                "size_text": "Bebé a término listo para nacer",
                "weight_length": "~50 cm (~3.2 - 3.8 kg)"
            }
