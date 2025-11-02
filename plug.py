# /// script
# requires-python = "==3.12"
# dependencies = [
#     "click==8.1.8",
#     "tinytuya==1.17.4",
#     "loguru==0.7.2",
# ]
# ///

import click
import tinytuya
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from loguru import logger


DB_PATH = "history.db"
LOCAL_TZ = datetime.now().astimezone().tzinfo


# Switch definition:
# https://developer.tuya.com/en/docs/iot/smart-switch-product-function-definition?id=K9r7gh4lbe886
@dataclass
class TuyaSmartPlug:
    power: bool
    countdown_1_s: int
    energy_wh: int
    current_a: float
    voltage_v: float
    power_w: float
    fault_code: int
    relay_status: str

    @classmethod
    def from_raw(cls, raw: dict) -> "TuyaSmartPlug":
        if not raw.get("success"):
            raise ValueError("Tuya API call failed or returned no data.")
        dps = {item["code"]: item["value"] for item in raw.get("result", [])}
        return cls(
            power=dps.get("switch_1", False),
            countdown_1_s=dps.get("countdown_1", 0),
            energy_wh=dps.get("add_ele", 0),
            current_a=dps.get("cur_current", 0) / 1000,
            voltage_v=dps.get("cur_voltage", 0) / 10,
            power_w=dps.get("cur_power", 0) / 10,
            fault_code=dps.get("fault", 0),
            relay_status=dps.get("relay_status", "unknown"),
        )

    def print(self) -> None:
        print(f"Power:         {'On' if self.power else 'Off'}")
        print(f"Countdown:     {self.countdown_1_s} s")
        print(f"Voltage:       {self.voltage_v:.1f} V")
        print(f"Current:       {self.current_a:.3f} A")
        print(f"Power Usage:   {self.power_w:.1f} W")
        print(f"Energy Used:   {self.energy_wh} Wh")
        print(f"Relay Status:  {self.relay_status}")
        print(f"Fault Code:    {self.fault_code}")


def fetch_plug(api_device_id: str, *, api_region: str, api_key: str, api_secret: str) -> TuyaSmartPlug:
    cloud = tinytuya.Cloud(
        apiRegion=api_region,
        apiKey=api_key,
        apiSecret=api_secret,
        apiDeviceID=api_device_id,
    )
    raw = cloud.getstatus(api_device_id)
    return TuyaSmartPlug.from_raw(raw)


def evaluate_plug_state(plug: TuyaSmartPlug, threshold) -> tuple[str, str]:
    plug_state = "On" if plug.power else "Off"
    if not plug.power:
        device_state = "Off"
    elif plug.power_w > threshold:
        device_state = "On"
    else:
        device_state = "Off"
    return plug_state, device_state


def ensure_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS status_log (
                start TEXT NOT NULL,
                end TEXT NOT NULL,
                plug_state TEXT NOT NULL,
                device_state TEXT NOT NULL
            )"""
        )
        conn.execute(
            """CREATE TABLE IF NOT EXISTS event_log (
                recorded_at TEXT NOT NULL,
                plug_state TEXT NOT NULL,
                device_state TEXT NOT NULL,
                plug_power INTEGER NOT NULL,
                countdown_s INTEGER NOT NULL,
                energy_wh INTEGER NOT NULL,
                current_a REAL NOT NULL,
                voltage_v REAL NOT NULL,
                power_w REAL NOT NULL,
                relay_status TEXT NOT NULL,
                fault_code INTEGER NOT NULL
            )"""
        )


def parse_timestamp(raw: str) -> datetime:
    """Return a UTC-aware datetime from an ISO formatted string."""
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@click.group()
@click.option("--api-device-id", envvar="TUYA_DEVICE_ID", required=True, help="Tuya Device ID")
@click.option("--api-region", envvar="TUYA_API_REGION", required=True, help="Tuya API region")
@click.option("--api-key", envvar="TUYA_API_KEY", required=True, help="Tuya API key")
@click.option("--api-secret", envvar="TUYA_API_SECRET", required=True, help="Tuya API secret")
@click.pass_context
def cli(ctx: click.Context, api_device_id: str, api_region: str, api_key: str, api_secret: str) -> None:
    """Tuya Smart Plug CLI. Use record command from a cron job to record plug state periodically."""
    ctx.ensure_object(dict)
    ctx.obj["api_device_id"] = api_device_id
    ctx.obj["api_region"] = api_region
    ctx.obj["api_key"] = api_key
    ctx.obj["api_secret"] = api_secret


@cli.command()

@click.pass_context
def info(ctx: click.Context) -> None:
    """Show detailed plug info."""
    try:
        plug = fetch_plug(
            api_device_id=ctx.obj["api_device_id"],
            api_region=ctx.obj["api_region"],
            api_key=ctx.obj["api_key"],
            api_secret=ctx.obj["api_secret"],
        )
        plug.print()
    except Exception as e:
        logger.error("Error: {}", e)


@cli.command()
@click.option("--threshold", default=5.0, envvar="THRESHOLD", show_default=True, help="Power threshold (W) to detect active usage")
@click.pass_context
def status(ctx: click.Context, threshold: float) -> None:
    """Show On/Off status."""
    try:
        plug = fetch_plug(
            api_device_id=ctx.obj["api_device_id"],
            api_region=ctx.obj["api_region"],
            api_key=ctx.obj["api_key"],
            api_secret=ctx.obj["api_secret"],
        )
        plug_state, device_state = evaluate_plug_state(plug, threshold)
        print(f"Plug:     {plug_state}")
        print(f"Device:   {device_state}")
    except Exception as e:
        logger.error("Error: {}", e)


@cli.command()
@click.option("--threshold", default=5.0, envvar="THRESHOLD", show_default=True, help="Power threshold (W)")
@click.pass_context
def record(ctx: click.Context, threshold: float) -> None:
    """Record plug and device state to history DB; This command is intended to be run in a cron job, once a minute."""
    ensure_db()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    try:
        plug = fetch_plug(
            api_device_id=ctx.obj["api_device_id"],
            api_region=ctx.obj["api_region"],
            api_key=ctx.obj["api_key"],
            api_secret=ctx.obj["api_secret"],
        )
        plug_state, device_state = evaluate_plug_state(plug, threshold)

        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """INSERT INTO event_log (
                    recorded_at,
                    plug_state,
                    device_state,
                    plug_power,
                    countdown_s,
                    energy_wh,
                    current_a,
                    voltage_v,
                    power_w,
                    relay_status,
                    fault_code
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    now,
                    plug_state,
                    device_state,
                    int(plug.power),
                    plug.countdown_1_s,
                    plug.energy_wh,
                    plug.current_a,
                    plug.voltage_v,
                    plug.power_w,
                    plug.relay_status,
                    plug.fault_code,
                ),
            )

            # Get the last record
            cursor.execute("SELECT rowid, plug_state, device_state FROM status_log ORDER BY rowid DESC LIMIT 1")
            row = cursor.fetchone()

            if row:
                rowid, last_plug_state, last_device_state = row
                if (plug_state, device_state) == (last_plug_state, last_device_state):
                    cursor.execute("UPDATE status_log SET end = ? WHERE rowid = ?", (now, rowid))
                    logger.info("Updated existing state; Plug: {}, Device: {}", plug_state, device_state)
                    return

            # Insert a new state
            cursor.execute(
                "INSERT INTO status_log (start, end, plug_state, device_state) VALUES (?, ?, ?, ?)",
                (now, now, plug_state, device_state)
            )
            logger.info("Logged new state; Plug: {}, Device: {}", plug_state, device_state)

    except Exception as e:
        logger.error("Failed to record state: {}", e)


@cli.command()
def history() -> None:
    """Print log of status ranges."""
    ensure_db()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT start, end, plug_state, device_state FROM status_log ORDER BY start DESC"
            )
            rows = cursor.fetchall()

            if not rows:
                print("No history found.")
                return

            print(f"{'Time Range':<40} {'Duration':<8} {'Plug':<6} {'Device':<8}")
            print("-" * 70)

            for start_raw, end_raw, plug_state, device_state in rows:
                start_dt = parse_timestamp(start_raw)
                end_dt = parse_timestamp(end_raw)

                start_local = start_dt.astimezone(LOCAL_TZ)
                end_local = end_dt.astimezone(LOCAL_TZ)

                same_day = start_local.date() == end_local.date()

                if same_day:
                    time_range = f"{start_local.strftime('%Y-%m-%d %H:%M')} - {end_local.strftime('%H:%M')}"
                else:
                    time_range = (
                        f"{start_local.strftime('%Y-%m-%d %H:%M')} - {end_local.strftime('%Y-%m-%d %H:%M')}"
                    )

                duration_seconds = int((end_dt - start_dt).total_seconds())
                hours, remainder = divmod(duration_seconds, 3600)
                minutes = remainder // 60
                duration_str = f"{hours:02}:{minutes:02}"

                print(f"{time_range:<40} {duration_str:<8} {plug_state:<6} {device_state:<8}")

    except Exception as e:
        logger.error("Failed to load history: {}", e)


if __name__ == "__main__":
    cli()
