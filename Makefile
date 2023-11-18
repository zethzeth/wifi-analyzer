SHELL := /bin/bash
VENV_NAME := wifianalyzerenv
DB_NAME := wifi_analyzer.db

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

.PHONY: help start clean db test

help:
	@grep -E '^[1-9a-zA-Z_-]+:.*?## .*$$|(^#--)' $(MAKEFILE_LIST) \
	| awk 'BEGIN {FS = ":.*?## "}; {printf "\033[32m %-43s\033[0m %s\n", $$1, $$2}' \
	| sed -e 's/\[32m #-- /[33m/'

#-- Program execution
run: ## Run the program
	@if [ -z "$$VIRTUAL_ENV" ] || [[ ! "$$VIRTUAL_ENV" =~ "wifianalyzerenv" ]]; then \
		echo "You are not in the 'wifianalyzerenv' virtual environment. Activate it with:"; \
		echo -e "${ORANGE}source $(VENV_NAME)/bin/activate ${RESET}"; \
		exit 1; \
	fi
	@python3 main.py

#-- DB
reset-db: ## Delete database
	@python3 scripts/drop-all-tables.py
	@rm $(DB_NAME)

#-- Venv
setup-env: ## Install the virtual environment
	@python3 -m venv $(VENV_NAME)
	$(VENV_NAME)/bin/pip3 install -r requirements.txt

activate-env: ## Activate the virtual environment
	@echo "Run this command:"
	@echo -e "${ORANGE}source $(VENV_NAME)/bin/activate ${RESET}"
	@echo "This cannot be done via make-targets, since they run in subprocesses"

deactivate-env: ## Deactivate the virtual environment
	@echo "Run this command:"
	@echo -e "${ORANGE}deactivate ${RESET}"
	@echo "This cannot be done via make-targets, since they run in subprocesses"

clean-up-env: deactivate-env ## Deactivate the virtual environment (and delete files)
	@rm -rf $(VENV_NAME)
