.PHONY: help build build-up up down restart logs shell test clean migrate makemigrations collectstatic setup-host

help:
	@echo "Available commands:"
	@echo "  make build          - Build podman containers"
	@echo "  make build-up       - Build and start podman containers"
	@echo "  make up             - Start podman containers"
	@echo "  make down           - Stop podman containers"
	@echo "  make restart        - Restart podman containers"
	@echo "  make logs           - View podman logs"
	@echo "  make shell          - Connect to Django container shell"
	@echo "  make test           - Run tests"
	@echo "  make migrate        - Run database migrations"
	@echo "  make makemigrations - Create new migrations"
	@echo "  make collectstatic  - Collect static files"
	@echo "  make clean          - Remove podman containers and volumes"
	@echo "  make setup-host     - Fix host.containers.internal -> Windows host (run once, or after WSL2 restart)"

build:
	podman-compose -f docker-compose.local.yml build

build-up:
	podman-compose -f docker-compose.local.yml up -d --build
up:
	podman-compose -f docker-compose.local.yml up -d

down:
	podman-compose -f docker-compose.local.yml down

restart: down up

logs:
	podman-compose -f docker-compose.local.yml logs -f

shell:
	podman exec -it thetataucmt_local_django bash

shellworker:
	podman exec -it thetataucmt_local_celeryworker bash

shellpg:
	podman exec -it thetataucmt_local_postgres bash

test:
	podman exec -it thetataucmt_local_django pytest

test-fresh:
	podman exec -it thetataucmt_local_django pytest --create-db

test-fast:
	podman exec -it thetataucmt_local_django pytest -x --no-header -q

test-path:
	podman exec -it thetataucmt_local_django pytest $(path)

migrate:
	podman exec -it thetataucmt_local_django python manage.py migrate

makemigrations:
	podman exec -it thetataucmt_local_django python manage.py makemigrations

collectstatic:
	podman exec -it thetataucmt_local_django python manage.py collectstatic --noinput

clean:
	podman-compose -f docker-compose.local.yml down -v

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
