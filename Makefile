.PHONY: install clean venv deps playwright-install run help

VENV := .venv
PYTHON := $(VENV)/bin/python
UV := uv

help:
	@echo "Available commands:"
	@echo "  make install           - Create virtual environment and install all dependencies"
	@echo "  make venv              - Create virtual environment only"
	@echo "  make deps              - Install Python dependencies"
	@echo "  make playwright-install - Install Playwright browsers"
	@echo "  make run               - Run the Costco scraper"
	@echo "  make clean             - Remove virtual environment"

install: venv deps playwright-install
	@echo "Installation complete! Activate with: source $(VENV)/bin/activate"

venv:
	@echo "Creating virtual environment with uv..."
	$(UV) venv $(VENV)

deps: venv
	@echo "Installing dependencies with uv..."
	$(UV) pip install -r requirements.txt

playwright-install: deps
	@echo "Installing Playwright browsers (chromium and firefox)..."
	$(VENV)/bin/playwright install chromium firefox

run:
	@echo "Running Costco scraper..."
	$(PYTHON) costco_scraper.py

clean:
	@echo "Cleaning up virtual environment..."
	rm -rf $(VENV)
	@echo "Cleanup complete!"
