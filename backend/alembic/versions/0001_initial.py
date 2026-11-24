"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS timescaledb")

    op.create_table(
        "farms",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("owner", sa.String(255), nullable=False, server_default=""),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("timezone", sa.String(64), server_default="UTC"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_table(
        "fields",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("farm_id", sa.String(36), sa.ForeignKey("farms.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("area_ha", sa.Float, nullable=True),
        sa.Column("soil_type", sa.String(64), nullable=True),
        sa.Column("polygon", sa.JSON, nullable=True),
    )
    op.create_index("ix_fields_farm_id", "fields", ["farm_id"])
    op.create_table(
        "zones",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("field_id", sa.String(36), sa.ForeignKey("fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("polygon", sa.JSON, nullable=True),
    )
    op.create_index("ix_zones_field_id", "zones", ["field_id"])
    op.create_table(
        "crops",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("zone_id", sa.String(36), sa.ForeignKey("zones.id", ondelete="CASCADE"), nullable=False),
        sa.Column("species", sa.String(128), nullable=False),
        sa.Column("variety", sa.String(128), nullable=True),
        sa.Column("planted_at", sa.DateTime, nullable=True),
        sa.Column("growth_stage", sa.String(64), server_default="unknown"),
        sa.Column("thresholds", sa.JSON, nullable=True),
    )
    op.create_index("ix_crops_zone_id", "crops", ["zone_id"])

    op.create_table(
        "devices",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("farm_id", sa.String(36), sa.ForeignKey("farms.id"), nullable=True),
        sa.Column("zone_id", sa.String(36), sa.ForeignKey("zones.id"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("hardware_type", sa.String(64), server_default="esp32"),
        sa.Column("firmware", sa.String(64), nullable=True),
        sa.Column("source", sa.String(32), server_default="simulation"),
        sa.Column("status", sa.String(32), server_default="offline"),
        sa.Column("last_seen", sa.DateTime, nullable=True),
        sa.Column("config", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_devices_farm_id", "devices", ["farm_id"])
    op.create_index("ix_devices_zone_id", "devices", ["zone_id"])
    op.create_index("ix_devices_status", "devices", ["status"])

    op.create_table(
        "sensors",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("device_id", sa.String(64), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("min_value", sa.Float, nullable=True),
        sa.Column("max_value", sa.Float, nullable=True),
        sa.Column("calibration", sa.JSON, nullable=True),
        sa.Column("enabled", sa.Boolean, server_default=sa.text("true")),
    )
    op.create_index("ix_sensors_device_id", "sensors", ["device_id"])
    op.create_index("ix_sensors_type", "sensors", ["type"])

    op.create_table(
        "sensor_readings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sensor_id", sa.String(64), sa.ForeignKey("sensors.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.String(64), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ts", sa.DateTime, nullable=False),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("unit", sa.String(16), nullable=False),
        sa.Column("quality", sa.Float, server_default="1.0"),
        sa.Column("source", sa.String(32), nullable=False),
    )
    op.create_index("ix_sensor_readings_sensor_ts", "sensor_readings", ["sensor_id", "ts"])
    op.create_index("ix_sensor_readings_source", "sensor_readings", ["source"])
    # Convert to hypertable (TimescaleDB). Falls back silently on vanilla Postgres.
    op.execute(
        "SELECT create_hypertable('sensor_readings', 'ts', if_not_exists => TRUE, migrate_data => TRUE)"
    )

    op.create_table(
        "weather_observations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("field_id", sa.String(36), sa.ForeignKey("fields.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ts", sa.DateTime, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("provider", sa.String(64), server_default="open-meteo"),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("source", sa.String(32), server_default="forecast"),
    )
    op.create_index("ix_weather_field_ts", "weather_observations", ["field_id", "ts"])

    op.create_table(
        "audio_recordings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("zone_id", sa.String(36), sa.ForeignKey("zones.id"), nullable=True),
        sa.Column("device_id", sa.String(64), sa.ForeignKey("devices.id"), nullable=True),
        sa.Column("ts", sa.DateTime, nullable=False),
        sa.Column("duration_s", sa.Float, server_default="0"),
        sa.Column("sample_rate", sa.Integer, server_default="16000"),
        sa.Column("channels", sa.Integer, server_default="1"),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("source", sa.String(32), server_default="manual"),
        sa.Column("status", sa.String(32), server_default="pending"),
        sa.Column("notes", sa.String(1024), nullable=True),
    )
    op.create_index("ix_audio_zone_ts", "audio_recordings", ["zone_id", "ts"])

    op.create_table(
        "acoustic_detections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recording_id", sa.String(36), sa.ForeignKey("audio_recordings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("model", sa.String(64), nullable=False),
        sa.Column("model_version", sa.String(64), nullable=True),
        sa.Column("category", sa.String(128), nullable=False),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("signal_quality", sa.Float, server_default="0"),
        sa.Column("evidence", sa.JSON, nullable=True),
        sa.Column("ts", sa.DateTime, nullable=False),
    )
    op.create_index("ix_detections_recording", "acoustic_detections", ["recording_id"])

    op.create_table(
        "acoustic_labels",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recording_id", sa.String(36), sa.ForeignKey("audio_recordings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("start_s", sa.Float, server_default="0"),
        sa.Column("end_s", sa.Float, nullable=True),
        sa.Column("label", sa.String(128), nullable=False),
        sa.Column("labeler", sa.String(128), server_default="user"),
        sa.Column("notes", sa.String(1024), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_labels_recording", "acoustic_labels", ["recording_id"])

    op.create_table(
        "image_analyses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("zone_id", sa.String(36), sa.ForeignKey("zones.id"), nullable=True),
        sa.Column("path", sa.String(512), nullable=False),
        sa.Column("ts", sa.DateTime, nullable=False),
        sa.Column("model", sa.String(64), server_default="none"),
        sa.Column("findings", sa.JSON, nullable=True),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("source", sa.String(32), server_default="manual"),
    )
    op.create_index("ix_images_zone_ts", "image_analyses", ["zone_id", "ts"])

    op.create_table(
        "predictions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("zone_id", sa.String(36), sa.ForeignKey("zones.id"), nullable=True),
        sa.Column("ts", sa.DateTime, nullable=False),
        sa.Column("kind", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("summary", sa.String(512), nullable=False),
        sa.Column("supporting", sa.JSON, nullable=False),
        sa.Column("confidence", sa.Float, server_default="0"),
        sa.Column("model", sa.String(64), server_default="rules-v1"),
        sa.Column("explanation", sa.String(2048), nullable=True),
    )
    op.create_index("ix_predictions_zone_ts", "predictions", ["zone_id", "ts"])

    op.create_table(
        "alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("zone_id", sa.String(36), sa.ForeignKey("zones.id"), nullable=True),
        sa.Column("prediction_id", sa.String(36), sa.ForeignKey("predictions.id"), nullable=True),
        sa.Column("ts", sa.DateTime, nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("message", sa.String(1024), nullable=False),
        sa.Column("data", sa.JSON, nullable=True),
        sa.Column("acknowledged", sa.Boolean, server_default=sa.text("false")),
        sa.Column("ack_by", sa.String(128), nullable=True),
        sa.Column("ack_at", sa.DateTime, nullable=True),
    )
    op.create_index("ix_alerts_zone_ts", "alerts", ["zone_id", "ts"])
    op.create_index("ix_alerts_ack", "alerts", ["acknowledged"])

    op.create_table(
        "simulation_scenarios",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(128), nullable=False, unique=True),
        sa.Column("description", sa.String(1024), server_default=""),
        sa.Column("config", sa.JSON, nullable=False),
        sa.Column("active", sa.Boolean, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "verifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("target_type", sa.String(32), nullable=False),
        sa.Column("target_id", sa.String(36), nullable=False),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("notes", sa.String(2048), nullable=True),
        sa.Column("verifier", sa.String(128), server_default="user"),
        sa.Column("extra", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_verifications_target", "verifications", ["target_id"])


def downgrade() -> None:
    for t in [
        "verifications", "simulation_scenarios", "alerts", "predictions",
        "image_analyses", "acoustic_labels", "acoustic_detections", "audio_recordings",
        "weather_observations", "sensor_readings", "sensors", "devices",
        "crops", "zones", "fields", "farms",
    ]:
        op.drop_table(t)
