.PHONY: dev api web ui test lint freeze-check security-check hello install demo proto product agent-smoke

install:
	python3.12 -m venv .venv || true
	. .venv/bin/activate && pip install -U pip && pip install -r requirements-dev.txt
	@if [ -d apps/nextchat ]; then (cd apps/nextchat && yarn install || npm install); fi

api:
	. .venv/bin/activate && uvicorn app.main:app --app-dir services/api --host 0.0.0.0 --port 8000 --reload

# Product UI = NextChat (OpenAI-compat → Pico agent). apps/web removed.
web ui:
	cd apps/nextchat && npx next dev -H 0.0.0.0 -p 8080

proto product:
	bash scripts/run-product.sh

test:
	. .venv/bin/activate && pytest -q

lint:
	. .venv/bin/activate && ruff check services tests scripts

security-check:
	. .venv/bin/activate && pytest -q tests/security

freeze-check:
	. .venv/bin/activate && python scripts/check_agent_pin.py

hello:
	. .venv/bin/activate && python scripts/model_hello.py

demo:
	. .venv/bin/activate && python scripts/demo_e2e.py

agent-smoke:
	. .venv/bin/activate && curl -s http://127.0.0.1:8000/v1/chat/completions \
	  -H 'Authorization: Bearer pico-dev' -H 'Content-Type: application/json' \
	  -d '{"model":"pico-agent","messages":[{"role":"user","content":"列出我学校的班级"}],"stream":false}'
