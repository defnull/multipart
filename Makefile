VENV = build/venv

venv: $(VENV)/.installed
$(VENV)/.installed: Makefile
	python3 -mvenv $(VENV)
	$(VENV)/bin/python3 -mensurepip
	$(VENV)/bin/pip install -U pip build wheel twine pytest coverage
	touch $(VENV)/.installed

build: venv
	$(VENV)/bin/python3 -m build .

test: venv
	$(VENV)/bin/pytest . -ra -q --doctest-modules --cov=multipart --cov-report=term --cov-report=html:build/htmlcov

upload: build
	$(VENV)/bin/python3 -m twine upload --skip-existing dist/multipart-*
