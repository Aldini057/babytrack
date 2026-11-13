from datetime import date
import pytest
from app.services.obstetric_calculator import ObstetricCalculatorService


def test_exact_obstetric_calculation_anchor():
    """
    Verifica que al 12 de noviembre de 2026, con FPP al 07 de julio de 2027
    y offset de calibración = 1, el motor calcule exactamente:
    - 6 Semanas y 2 Días cumplidos
    - 44 días transcurridos de 280
    - 237 días restantes
    - 1er Trimestre
    - Comparación de tamaño: Lenteja / Arándano
    """
    due_date = date(2027, 7, 7)
    current_date = date(2026, 11, 12)
    offset = 1

    metrics = ObstetricCalculatorService.calculate_metrics(
        due_date=due_date,
        calibration_offset_days=offset,
        current_date=current_date
    )

    assert metrics["weeks"] == 6
    assert metrics["days"] == 2
    assert metrics["elapsedDays"] == 44
    assert metrics["daysRemaining"] == 237
    assert metrics["progressPercent"] == 15.7
    assert metrics["trimester"] == 1
    assert "Arándano" in metrics["sizeComparison"] or "Lenteja" in metrics["sizeComparison"]


def test_calibration_offset_calculation():
    """Verifica el cálculo inverso de offset dado un objetivo de semanas y días."""
    due_date = date(2027, 7, 7)
    current_date = date(2026, 11, 12)

    offset = ObstetricCalculatorService.calculate_offset_from_weeks_days(
        due_date=due_date,
        target_weeks=6,
        target_days=2,
        current_date=current_date
    )
    assert offset == 1


def test_trimester_exact_boundaries():
    """
    Verifica con precisión matemática las fronteras exactas de cada trimestre:
    - Día 97 (Semana 13 + 6d) -> Trimestre 1
    - Día 98 (Semana 14 + 0d) -> Trimestre 2
    - Día 195 (Semana 27 + 6d) -> Trimestre 2
    - Día 196 (Semana 28 + 0d) -> Trimestre 3
    """
    due_date = date(2027, 7, 7)

    # Día 97 -> restan 183 días -> 2027-01-05
    m97 = ObstetricCalculatorService.calculate_metrics(due_date, 0, date(2027, 1, 5))
    assert m97["elapsedDays"] == 97
    assert m97["trimester"] == 1

    # Día 98 -> restan 182 días -> 2027-01-06
    m98 = ObstetricCalculatorService.calculate_metrics(due_date, 0, date(2027, 1, 6))
    assert m98["elapsedDays"] == 98
    assert m98["trimester"] == 2

    # Día 195 -> restan 85 días -> 2027-04-13
    m195 = ObstetricCalculatorService.calculate_metrics(due_date, 0, date(2027, 4, 13))
    assert m195["elapsedDays"] == 195
    assert m195["trimester"] == 2

    # Día 196 -> restan 84 días -> 2027-04-14
    m196 = ObstetricCalculatorService.calculate_metrics(due_date, 0, date(2027, 4, 14))
    assert m196["elapsedDays"] == 196
    assert m196["trimester"] == 3


@pytest.mark.parametrize(
    "week,expected_keyword",
    [
        (2, "Blastocisto"),
        (4, "amapola"),
        (5, "Sésamo"),
        (6, "Arándano"),
        (7, "Lenteja"),
        (8, "Frambuesa"),
        (10, "Fresa"),
        (11, "Higo"),
        (13, "Durazno"),
        (14, "Manzana"),
        (17, "Pera"),
        (18, "Pimiento"),
        (22, "Papaya"),
        (23, "Elote"),
        (27, "Coliflor"),
        (28, "Berenjena"),
        (33, "Piña"),
        (34, "Melón"),
        (40, "Sandía"),
        (41, "término"),
    ],
)
def test_size_comparison_all_ranges(week, expected_keyword):
    """Verifica todos los rangos de la tabla comparativa de crecimiento semanal."""
    info = ObstetricCalculatorService.get_size_comparison(week)
    assert expected_keyword.lower() in info["size_text"].lower()
    assert len(info["weight_length"]) > 0


def test_extreme_dates_clamping():
    """Verifica que fechas anteriores a FUM o posteriores a FPP no produzcan porcentajes fuera de [0, 100]."""
    due_date = date(2027, 7, 7)

    # Muy antes del inicio
    early = ObstetricCalculatorService.calculate_metrics(due_date, 0, date(2026, 1, 1))
    assert early["elapsedDays"] == 0
    assert early["progressPercent"] == 0.0
    assert early["weeks"] == 0

    # Fecha de parto exacta y post-término
    on_due = ObstetricCalculatorService.calculate_metrics(due_date, 0, date(2027, 7, 7))
    assert on_due["daysRemaining"] == 0
    assert on_due["progressPercent"] == 100.0

    overdue = ObstetricCalculatorService.calculate_metrics(due_date, 0, date(2027, 7, 15))
    assert overdue["daysRemaining"] == 0
    assert overdue["progressPercent"] == 100.0
