# NET KIT build & install. Cross-platform target notes inline.
PY ?= python3
DIST := dist
PYZ := $(DIST)/netkit.pyz

.PHONY: help run build pyz wheel install uninstall clean service-mac service-linux

help:
	@echo "NET KIT make targets:"
	@echo "  make run            run from source (python -m netkit)"
	@echo "  make build          build the single-file executable (netkit.pyz)"
	@echo "  make pyz            alias for build"
	@echo "  make wheel          build a pip-installable wheel + sdist"
	@echo "  make install        pipx-install the netkit command"
	@echo "  make clean          remove build artifacts"
	@echo "  make service-mac    install the macOS LaunchAgent"
	@echo "  make service-linux  install the Linux systemd --user unit"

run:
	$(PY) -m netkit

# Single-file executable: a zipapp. Runs anywhere with Python 3.9+.
#   ./dist/netkit.pyz   or   python3 dist/netkit.pyz
build pyz:
	@rm -rf build_stage $(DIST)
	@mkdir -p build_stage $(DIST)
	@cp -r netkit build_stage/netkit
	@find build_stage -name '__pycache__' -type d -prune -exec rm -rf {} +
	$(PY) -m zipapp build_stage -m "netkit.server:main" -p "/usr/bin/env python3" -o $(PYZ)
	@chmod +x $(PYZ)
	@rm -rf build_stage
	@echo "built $(PYZ)"

wheel:
	$(PY) -m pip install --quiet --upgrade build
	$(PY) -m build

install:
	$(PY) -m pip install --quiet --upgrade pipx
	pipx install --force .

uninstall:
	-pipx uninstall netkit

clean:
	rm -rf $(DIST) build_stage build *.egg-info netkit.egg-info
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +

service-mac:
	cp packaging/com.jservo.netkit.plist $(HOME)/Library/LaunchAgents/
	launchctl bootout gui/$$(id -u)/com.jservo.netkit 2>/dev/null || true
	launchctl bootstrap gui/$$(id -u) $(HOME)/Library/LaunchAgents/com.jservo.netkit.plist
	@echo "NET KIT service installed (macOS)."

service-linux:
	mkdir -p $(HOME)/.config/systemd/user
	cp packaging/netkit.service $(HOME)/.config/systemd/user/
	systemctl --user daemon-reload
	systemctl --user enable --now netkit.service
	@echo "NET KIT service installed (Linux, systemd --user)."
