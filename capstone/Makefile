.PHONY: install test eval run up prod down logs pull-model

install:
	pip install -r requirements.txt

test:
	python -m pytest tests -q

eval:
	python evaluate.py

run:            ## local dev (both processes, shared metrics)
	python start.py

up:             ## dev stack (app + prometheus + grafana + qdrant + ollama)
	docker compose up -d --build

prod:           ## production stack (adds nginx, localhost-bound app)
	docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

pull-model:     ## download the local LLM once
	docker compose exec ollama ollama pull $${LLM_MODEL:-llama3.1:8b}

down:
	docker compose down

logs:
	docker compose logs -f proposalforge-pro
