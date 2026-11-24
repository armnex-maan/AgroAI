"""Seed script: create a default demo farm, field, zones, simulated devices and scenarios."""
from datetime import datetime, timezone
from app.core.database import session_scope
from app.models import Farm, Field, Zone, Crop, Device, Sensor, SimulationScenario
from app.simulation.scenarios import SCENARIOS

# Names used by earlier versions of the demo data → current Italian names.
RENAMES = {
    Farm: {"Demo Farm": "Azienda Demo"},
    Field: {"North Field": "Campo Nord"},
    Zone: {"Zone A": "Zona A", "Zone B": "Zona B"},
    Device: {"Simulated ESP32 (Zone A)": "Sensore demo (Zona A)", "Simulated ESP32 (Zone B)": "Sensore demo (Zona B)"},
}


def _rename_old(db) -> None:
    for model, mapping in RENAMES.items():
        for old, new in mapping.items():
            for row in db.query(model).filter_by(name=old).all():
                row.name = new
    db.flush()


def seed() -> None:
    with session_scope() as db:
        _rename_old(db)
        farm = db.query(Farm).filter_by(name="Azienda Demo").first()
        if farm is None:
            # Rice district south-east of Vercelli (rural, so soil maps have data).
            farm = Farm(name="Azienda Demo", owner="demo", latitude=45.27, longitude=8.50,
                        timezone="Europe/Rome", created_at=datetime.now(timezone.utc))
            db.add(farm)
            db.flush()
        elif (farm.latitude, farm.longitude) == (45.4642, 9.19):  # old default: Milan city centre
            farm.latitude, farm.longitude = 45.27, 8.50
        field = db.query(Field).filter_by(farm_id=farm.id, name="Campo Nord").first()
        if field is None:
            field = Field(farm_id=farm.id, name="Campo Nord", area_ha=3.5, soil_type="loam")
            db.add(field)
            db.flush()
        zones = []
        for zname in ("Zona A", "Zona B"):
            z = db.query(Zone).filter_by(field_id=field.id, name=zname).first()
            if z is None:
                z = Zone(field_id=field.id, name=zname)
                db.add(z)
                db.flush()
            zones.append(z)
        if not db.query(Crop).filter_by(zone_id=zones[0].id).first():
            db.add(Crop(zone_id=zones[0].id, species="pomodoro", variety="San Marzano", growth_stage="vegetative"))

        for i, zone in enumerate(zones):
            dev_id = f"AGRO-SIM-{i+1:03d}"
            device = db.get(Device, dev_id)
            if device is None:
                device = Device(
                    id=dev_id, farm_id=farm.id, zone_id=zone.id, name=f"Sensore demo ({zone.name})",
                    hardware_type="esp32-sim", source="simulation", status="online",
                    last_seen=datetime.now(timezone.utc), created_at=datetime.now(timezone.utc),
                )
                db.add(device)
                db.flush()
            existing = {s.type for s in device.sensors}
            for stype, unit in [
                ("soil_moisture", "%"), ("soil_temperature", "C"),
                ("air_temperature", "C"), ("air_humidity", "%"),
                ("soil_ph", "pH"), ("soil_ec", "mS/cm"), ("rainfall", "mm"),
                ("light_intensity", "lux"), ("wind_speed", "m/s"),
            ]:
                if stype not in existing:
                    db.add(Sensor(device_id=device.id, type=stype, unit=unit, enabled=True))

        existing_scenarios = {s.name for s in db.query(SimulationScenario).all()}
        for name, cfg in SCENARIOS.items():
            if name not in existing_scenarios:
                db.add(SimulationScenario(name=name, description=cfg["description"],
                                          config=cfg, active=(name == "healthy")))

    print("seed complete")


if __name__ == "__main__":
    seed()
