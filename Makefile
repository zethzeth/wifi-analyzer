SHELL := /bin/bash
VENV_NAME := .venv
DB_NAME := kestrel.db
PYTHON := $(VENV_NAME)/bin/python
UNAME := $(shell uname)
ELECTRON_FLAGS := $(if $(filter Linux,$(UNAME)),--no-sandbox,) # Ubuntu's AppArmor blocks Electron's sandbox; see README

# ANSI Escape Codes for colors
RESET  := \033[0m

# Regular Colors
BLACK  := \033[0;30m
ORANGE := \033[33m
RED    := \033[0;31m
GREEN  := \033[0;32m
YELLOW := \033[0;33m
BLUE   := \033[0;34m
PURPLE := \033[0;35m
CYAN   := \033[0;36m
WHITE  := \033[0;37m

# Bright Colors
BRIGHT_RED    := \033[1;31m
BRIGHT_GREEN  := \033[1;32m
BRIGHT_YELLOW := \033[1;33m
BRIGHT_BLUE   := \033[1;34m
BRIGHT_PURPLE := \033[1;35m
BRIGHT_CYAN   := \033[1;36m
BRIGHT_WHITE  := \033[1;37m

.PHONY: help ship run channels test setup-env setup-app reset-db clean-up-env

help:
	@grep -E '^[1-9a-zA-Z_-]+:.*?## .*$$|(^#--)' $(MAKEFILE_LIST) \
	| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[32m %-43s\033[0m %s\n", $$1, $$2}' \
	| sed -e 's/\[32m #-- /[33m/'

#-- Program execution
ship: $(PYTHON) app/node_modules ## Launch the Kestrel desktop app (installs what's missing)
	@cd app && npx electron . $(ELECTRON_FLAGS)

run: $(PYTHON) ## Run an interactive test in the terminal
	@$(PYTHON) -m kestrel run

channels: $(PYTHON) ## Scan and show how crowded each Wi-Fi channel is
	@$(PYTHON) -m kestrel channels

test: $(PYTHON) ## Run the parser/analysis unit tests
	@$(PYTHON) -m unittest discover -s tests -t .

#-- Setup
setup-env: ## Create the Python virtual environment and install dependencies
	@python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))' || { echo -e "${RED}Python 3.10+ needed (macOS: brew install python)${RESET}"; exit 1; }
	@python3 -m venv $(VENV_NAME)
	@$(VENV_NAME)/bin/pip install --quiet -r requirements.txt
	@tools="ping dig"; [ "$(UNAME)" = Linux ] && tools="$$tools iw nmcli resolvectl"; \
	for tool in $$tools; do \
		command -v $$tool >/dev/null || echo -e "${ORANGE}Missing '$$tool' - install it with your package manager${RESET}"; \
	done
	@echo -e "${GREEN}Python engine ready.${RESET}"

setup-app: ## Install the Electron app's dependencies
	@command -v npm >/dev/null || { echo -e "${RED}npm not found - install Node.js first${RESET}"; exit 1; }
	@cd app && npm install --silent
	@echo -e "${GREEN}App ready. Run: make ship${RESET}"

$(PYTHON):
	@$(MAKE) --no-print-directory setup-env

app/node_modules:
	@$(MAKE) --no-print-directory setup-app

#-- Cleanup
reset-db: ## Delete the measurements database
	@rm -f $(DB_NAME)

clean-up-env: ## Delete the virtual environment and the app's node_modules
	@rm -rf $(VENV_NAME) app/node_modules
