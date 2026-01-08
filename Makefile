.PHONY: help up down restart logs status build clean backup test-briefing

help:
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║           mail-stack - AI-Powered Email Server               ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "  make up            Start all services"
	@echo "  make down          Stop all services"
	@echo "  make restart       Restart all services"
	@echo "  make build         Rebuild all containers"
	@echo "  make status        Show service status"
	@echo ""
	@echo "  make logs          Follow all logs"
	@echo "  make logs-imap     Follow IMAP server logs"
	@echo "  make logs-fetch    Follow mail fetcher logs"
	@echo "  make logs-scanner  Follow AI scanner logs"
	@echo "  make logs-briefing Follow daily briefing logs"
	@echo ""
	@echo "  make shell-imap    Shell into IMAP container"
	@echo "  make shell-scanner Shell into AI scanner container"
	@echo "  make fetch-now     Trigger immediate mail fetch"
	@echo "  make test-briefing Generate a test daily briefing"
	@echo "  make backup        Run manual backup"
	@echo "  make clean         Stop and remove all containers"

up:
	docker-compose up -d

down:
	docker-compose down

restart:
	docker-compose restart

logs:
	docker-compose logs -f

logs-imap:
	docker-compose logs -f imap

logs-fetch:
	docker-compose logs -f mail-fetch

logs-scanner:
	docker-compose logs -f ai-scanner

logs-briefing:
	docker-compose logs -f daily-briefing

logs-antivirus:
	docker-compose logs -f antivirus

status:
	docker-compose ps

fetch-now:
	docker-compose exec mail-fetch fetchmail -v

shell-imap:
	docker-compose exec imap /bin/sh

shell-scanner:
	docker-compose exec ai-scanner /bin/bash

test-briefing:
	docker-compose exec daily-briefing /app/daily-briefing.sh

backup:
	./scripts/backup.sh

build:
	DOCKER_BUILDKIT=0 docker-compose build

clean:
	docker-compose down -v --remove-orphans
