ENV_FILE ?= .env
UV ?= uv
COG ?= uv tool run --from cogapp cog

.PHONY: help info status record history log readme

help:
	@echo "Available targets:"
	@echo "  make info      # Show detailed plug info"
	@echo "  make status    # Show On/Off/Standby status"
	@echo "  make record    # Record current plug status"
	@echo "  make history   # Print recorded status history"
	@echo "  make log       # Print raw event log entries"
	@echo "  make readme    # Regenerate README snippets via cogapp"

info:
	$(UV) run --env-file=$(ENV_FILE) plug.py info

status:
	$(UV) run --env-file=$(ENV_FILE) plug.py status

record:
	$(UV) run --env-file=$(ENV_FILE) plug.py record

history:
	$(UV) run --env-file=$(ENV_FILE) plug.py history

log:
	$(UV) run --env-file=$(ENV_FILE) plug.py log

readme:
	$(COG) -r README.md
