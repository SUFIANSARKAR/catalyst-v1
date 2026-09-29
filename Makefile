install:
	python -m pip install -e .
test:
	PYTHONPATH=. pytest -q
compile:
	python -m compileall -q catalyst tests
run:
	uvicorn catalyst.api.server:app --host 0.0.0.0 --port 8000
