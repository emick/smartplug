# Smart Plug Status

`plug.py` is a tiny CLI for polling Tuya smart plug status from Tuya Cloud and recording history to SQLite database.

This is intended to be periodically run from cron.

## Supported devices

Tested with these devices:

- Airam Smart Pistoke IP20

Most likely many other are also supported.

## Tuya Cloud setup

Since my device is in an isolated network that cannot be accessed directly from the polling server, the script uses
Tuya cloud for polling. Note that Tuya cloud free tier may have API limits. 

First, create a Tuya Cloud account:

1. Sign up for [Tuya developer platform](https://platform.tuya.com/)
2. Cloud / Create Cloud Project. Note: you must use your country-specific instance. For me, it was Central Europe
3. Project / Devices / Link App Account: Link your Tuya App (not e.g., Airam App) which has the devices linked
4. Project / Devices: You should now see your device. Take note of Device ID for the next step
5. Project / Authorization: take note of Access ID/Client ID and Access Secret/Client Secret for the next step

Tuya cloud details are configured through `.env` file:

```dotenv
TUYA_DEVICE_ID=
TUYA_API_REGION=<e.g. eu>
TUYA_API_KEY=
TUYA_API_SECRET=
```

## Running `plug.py`

Use [uv](https://docs.astral.sh/uv/) to run with `.env`:

```bash
uv run --env-file=.env plug.py <command>
```

No need to manually install dependencies or anything.

Running `--help` shows a list of all available commands.

<!-- [[[cog
import cog, shlex, subprocess

cmd = ["uv", "run", "plug.py", "--help"]
res = subprocess.run(cmd, capture_output=True, text=True)

cog.out("```console\n")
cog.out(f"$ {shlex.join(cmd)}\n")
cog.out(res.stdout)
if res.stderr:
    cog.out(res.stderr)
cog.out("```\n")
]]] -->
```console
$ uv run plug.py --help
Usage: plug.py [OPTIONS] COMMAND [ARGS]...

  Tuya Smart Plug CLI. Use record command from a cron job to record plug state
  periodically.

Options:
  --api-device-id TEXT  Tuya Device ID  [required]
  --api-region TEXT     Tuya API region  [required]
  --api-key TEXT        Tuya API key  [required]
  --api-secret TEXT     Tuya API secret  [required]
  --help                Show this message and exit.

Commands:
  history  Print log of status ranges.
  info     Show detailed plug info.
  log      Print raw event log entries.
  record   Record plug and device state to history DB; This command is...
  status   Show On/Off status.
```
<!-- [[[end]]] -->

## Crontab

Edit crontab with `crontab -e` to include something like this:

```text
# Scheduled smartplug polling (7-22)
* 7-21 * * * cd /path/to/smartplug && /usr/bin/make UV=/home/<user>/.local/bin/uv record
```

Optionally add logging `>> /path/to/smartplug/cron.log 2>&1`:

## Standby detection

The code used to have standby detection, but the device sends brief 0 W results which cause Standby and Off flip-flop.
