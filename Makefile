.PHONY: help build build-up up down restart logs shell test clean migrate makemigrations collectstatic setup-host

# ------------------------------------------------------------------------------
# Container engine configuration (Docker or Podman)
# ------------------------------------------------------------------------------
# Select the engine in the root .env file:
#     CONTAINER_ENGINE=podman   # default
#     CONTAINER_ENGINE=docker
# It can also be overridden per invocation, e.g. `make up CONTAINER_ENGINE=docker`.
# The compose command is derived from the engine but can be overridden too, e.g.
# for the legacy Docker Compose v1 binary: `make up COMPOSE=docker-compose`.
-include .env

CONTAINER_ENGINE ?= docker
CONTAINER_ENGINE := $(strip $(CONTAINER_ENGINE))

ifeq ($(CONTAINER_ENGINE),docker)
COMPOSE ?= docker compose
else
COMPOSE ?= podman-compose
endif

COMPOSE_FILE ?= docker-compose.local.yml

# Engine-aware helpers used by the targets below.
DC := $(COMPOSE) -f $(COMPOSE_FILE)
EXEC := $(CONTAINER_ENGINE) exec -it

help:
	@echo "Available commands (engine: $(CONTAINER_ENGINE), compose: $(COMPOSE)):"
	@echo "  make build          - Build containers"
	@echo "  make build-up       - Build and start containers"
	@echo "  make up             - Start containers"
	@echo "  make down           - Stop containers"
	@echo "  make restart        - Restart containers"
	@echo "  make logs           - View container logs"
	@echo "  make shell          - Connect to Django container shell"
	@echo "  make test           - Run tests"
	@echo "  make migrate        - Run database migrations"
	@echo "  make makemigrations - Create new migrations"
	@echo "  make collectstatic  - Collect static files"
	@echo "  make clean          - Remove containers and volumes"
	@echo "  make setup-host     - Fix host.containers.internal -> Windows host (run once, or after WSL2 restart)"
	@echo ""
	@echo "  Switch engine in .env (CONTAINER_ENGINE=docker|podman) or per run, e.g.: make up CONTAINER_ENGINE=docker"

build:
	$(DC) build

build-up:
	$(DC) up -d --build
up:
	$(DC) up -d

down:
	$(DC) down

restart: down up

logs:
	$(DC) logs -f

shell:
	$(EXEC) thetataucmt_local_django bash

shellworker:
	$(EXEC) thetataucmt_local_celeryworker bash

shellpg:
	$(EXEC) thetataucmt_local_postgres bash

test:
	$(EXEC) thetataucmt_local_django pytest

test-fresh:
	$(EXEC) thetataucmt_local_django pytest --create-db

test-fast:
	$(EXEC) thetataucmt_local_django pytest -x --no-header -q

test-path:
	$(EXEC) thetataucmt_local_django pytest $(path)

migrate:
	$(EXEC) thetataucmt_local_django python manage.py migrate

makemigrations:
	$(EXEC) thetataucmt_local_django python manage.py makemigrations

collectstatic:
	$(EXEC) thetataucmt_local_django python manage.py collectstatic --noinput

clean:
	$(DC) down -v

# Detect the Windows host IP as seen from the Podman WSL2 machine
WINDOWS_HOST_IP := $(shell wsl -d podman-machine-default ip route show default 2>NUL | tr -s ' ' | cut -d' ' -f3)

WINDOWS_IP := $(shell wsl hostname -I)

# One-time (or after WSL2 restart) setup: configures host.containers.internal inside
# the Podman machine to point to the actual Windows host so containers can reach
# services like PostgreSQL running on the host. Re-run if the WSL2 IP ever changes.
wslvpn:
	wsl.exe -d wsl-vpnkit2 --cd /app wsl-vpnkit

lint:
	pre-commit run --all-files

lint-setup:
	git config --global --add safe.directory /app

wsl-lan:
	netsh interface portproxy add v4tov4 listenport=5432 listenaddress=0.0.0.0 connectport=5432 connectaddress=$(WINDOWS_IP)

# 	netsh interface portproxy add v4tov4 listenport=5432 listenaddress=0.0.0.0 connectport=5432 connectaddress=172.20.233.249
