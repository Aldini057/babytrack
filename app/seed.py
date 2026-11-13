from datetime import date
from sqlalchemy.orm import Session
from app.models.settings import PregnancySettings
from app.models.checklist import ChecklistItem
from app.models.journal import BabyJournalNote

INITIAL_CHECKLIST_ITEMS = [
    # 1. HABITACION (4 ítems)
    {"category": "HABITACION", "item_name": "Cuna convertible o de madera", "description": "Con barrotes seguros y altura ajustable", "trimester_priority": 2, "quantity": 1, "estimated_cost_mxn": 6500.00},
    {"category": "HABITACION", "item_name": "Colchón firme transpirable para cuna", "description": "Firme anti-asfixia con funda lavable", "trimester_priority": 2, "quantity": 1, "estimated_cost_mxn": 2200.00},
    {"category": "HABITACION", "item_name": "Juego de sábanas de algodón (3 piezas)", "description": "100% algodón suave para piel de recién nacido", "trimester_priority": 3, "quantity": 2, "estimated_cost_mxn": 900.00},
    {"category": "HABITACION", "item_name": "Monitor de bebé con cámara y audio", "description": "Visión nocturna y sensor de temperatura", "trimester_priority": 3, "quantity": 1, "estimated_cost_mxn": 1800.00},

    # 2. TRANSPORTE (4 ítems)
    {"category": "TRANSPORTE", "item_name": "Carriola Travel System plegable", "description": "Ligera, compatible con portabebé", "trimester_priority": 2, "quantity": 1, "estimated_cost_mxn": 7500.00},
    {"category": "TRANSPORTE", "item_name": "Autoasiento / Portabebé certificado", "description": "Con base ISOFIX o cinturón certificado para recién nacido", "trimester_priority": 2, "quantity": 1, "estimated_cost_mxn": 3800.00},
    {"category": "TRANSPORTE", "item_name": "Pañalera mochila impermeable", "description": "Con compartimentos térmicos y cambiador portátil", "trimester_priority": 3, "quantity": 1, "estimated_cost_mxn": 1100.00},
    {"category": "TRANSPORTE", "item_name": "Fular o canguro ergonómico", "description": "Para porteo seguro desde los primeros meses", "trimester_priority": 3, "quantity": 1, "estimated_cost_mxn": 1200.00},

    # 3. ALIMENTACION (4 ítems)
    {"category": "ALIMENTACION", "item_name": "Set de biberones anticólicos", "description": "Flujo lento para recién nacido (libre de BPA)", "trimester_priority": 3, "quantity": 4, "estimated_cost_mxn": 950.00},
    {"category": "ALIMENTACION", "item_name": "Esterilizador de biberones", "description": "A vapor eléctrico o para microondas", "trimester_priority": 3, "quantity": 1, "estimated_cost_mxn": 1400.00},
    {"category": "ALIMENTACION", "item_name": "Cepillo limpiador de biberones y tetinas", "description": "De silicón suave con secador portátil", "trimester_priority": 3, "quantity": 1, "estimated_cost_mxn": 320.00},
    {"category": "ALIMENTACION", "item_name": "Extractor de leche y bolsas de almacenamiento", "description": "Eléctrico doble o manual + cojín de lactancia", "trimester_priority": 3, "quantity": 1, "estimated_cost_mxn": 2400.00},

    # 4. HIGIENE (4 ítems)
    {"category": "HIGIENE", "item_name": "Bañera ergonómica con termómetro", "description": "Con soporte antideslizante para recién nacido", "trimester_priority": 2, "quantity": 1, "estimated_cost_mxn": 950.00},
    {"category": "HIGIENE", "item_name": "Kit de cuidado (termómetro digital, cortaúñas, aspirador)", "description": "Kit básico de primeros auxilios e higiene", "trimester_priority": 3, "quantity": 1, "estimated_cost_mxn": 650.00},
    {"category": "HIGIENE", "item_name": "Pañales etapa Recién Nacido y Etapa 1", "description": "Paquetes iniciales hipoalergénicos", "trimester_priority": 3, "quantity": 2, "estimated_cost_mxn": 800.00},
    {"category": "HIGIENE", "item_name": "Toallitas húmedas y crema para rozaduras", "description": "Sin fragancia, a base de agua y óxido de zinc", "trimester_priority": 3, "quantity": 3, "estimated_cost_mxn": 450.00},

    # 5. ROPA (4 ítems)
    {"category": "ROPA", "item_name": "Pañaleros de algodón manga corta y larga (0-3m)", "description": "Pack de 6 a 8 piezas suaves", "trimester_priority": 2, "quantity": 8, "estimated_cost_mxn": 1200.00},
    {"category": "ROPA", "item_name": "Mamelucos completos con cierre bidireccional", "description": "Prácticos para cambios nocturnos", "trimester_priority": 3, "quantity": 6, "estimated_cost_mxn": 1500.00},
    {"category": "ROPA", "item_name": "Gorritos, guantes antirrasguños y calcetines", "description": "Para regular temperatura los primeros días", "trimester_priority": 3, "quantity": 4, "estimated_cost_mxn": 400.00},
    {"category": "ROPA", "item_name": "Cobijas ligeras y muselinas de algodón", "description": "Ideales para envolver (swaddle) y cubrir", "trimester_priority": 2, "quantity": 3, "estimated_cost_mxn": 850.00},

    # 6. HOSPITAL (4 ítems)
    {"category": "HOSPITAL", "item_name": "Maleta de Mamá para el hospital", "description": "Pijama cómoda de lactancia, pantuflas, artículos personales", "trimester_priority": 3, "quantity": 1, "estimated_cost_mxn": 1200.00},
    {"category": "HOSPITAL", "item_name": "Maleta del Bebé (mudas y conjunto de salida)", "description": "3 cambios completos, pañales RN y cobija de salida", "trimester_priority": 3, "quantity": 1, "estimated_cost_mxn": 900.00},
    {"category": "HOSPITAL", "item_name": "Carpeta clínica con identificaciones y póliza", "description": "INEs, orden de internamiento, últimos estudios y ultrasonidos", "trimester_priority": 1, "quantity": 1, "estimated_cost_mxn": 150.00},
    {"category": "HOSPITAL", "item_name": "Toallas postparto y ropa interior desechable", "description": "Indispensables para la recuperación en hospital", "trimester_priority": 3, "quantity": 2, "estimated_cost_mxn": 450.00},
]


def seed_database(db: Session):
    """
    Inicializa de forma idempotente los ajustes maestros de embarazo
    y los 24 artículos esenciales de la checklist.
    """
    settings = db.query(PregnancySettings).first()
    if not settings:
        settings = PregnancySettings(
            baby_nickname="Nuestro Bebé",
            due_date=date(2027, 7, 7),
            calibration_offset_days=1,
            gender_mode="SURPRISE",
            mom_name="Mamá",
            dad_name="Papá"
        )
        db.add(settings)
        db.commit()
        db.refresh(settings)

    if db.query(ChecklistItem).count() == 0:
        for item_data in INITIAL_CHECKLIST_ITEMS:
            db.add(ChecklistItem(**item_data))
        db.commit()

    return settings
