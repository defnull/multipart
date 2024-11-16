VENV = build/venv

venv: $(VENV)/.installed
$(VENV)/.installed: Makefile pyproject.toml
	python3 -mvenv $(VENV)
	$(VENV)/bin/python3 -m ensurepip
	$(VENV)/bin/pip install -q -U pip
	$(VENV)/bin/pip install -q -e .[dev,docs]
	touch $(VENV)/.installed

build: venv
	$(VENV)/bin/python3 -m build .

.PHONY: test
test: venv
	$(VENV)/bin/pytest .

.PHONY: coverage
coverage: venv
	$(VENV)/bin/pytest . -q --cov=multipart --cov-branch --cov-report=term --cov-report=html:build/htmlcov

.PHONY: docs
docs: venv
	cd docs; ../$(VENV)/bin/sphinx-build -M html . ../build/docs  

upload: build
	$(VENV)/bin/python3 -m twine upload --skip-existing dist/multipart-*
