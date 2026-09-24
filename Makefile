.PHONY: help data data-fresh fixtures serve test clean

PORT ?= 8765

help:
	@echo "make data        - busca APIs (cache) e gera web/data/data.json"
	@echo "make data-fresh  - idem, ignorando o cache (rebusca tudo)"
	@echo "make fixtures     - usa o dataset de exemplo (offline, sem rede)"
	@echo "make serve        - sobe o site em http://localhost:$(PORT)"
	@echo "make test         - roda os testes de scoring"
	@echo "make clean        - limpa cache de APIs (data/raw)"

data:
	python3 -m data.build

data-fresh:
	python3 -m data.build --no-cache

fixtures:
	python3 -m data.build --fixtures

serve:
	cd web && python3 -m http.server $(PORT)

test:
	python3 -m unittest discover -s data -p 'test_*.py' -t . -v

clean:
	rm -f data/raw/*.json

.PHONY: ftc-data ftc-build
ftc-data:
	python3 -m data.ftc.fetch
	python3 -m data.ftc.build

ftc-build:
	python3 -m data.ftc.build
