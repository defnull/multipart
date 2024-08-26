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
	$(VENV)/bin/python3 -m pytest

upload: build
	$(VENV)/bin/python3 -m twine upload --skip-existing dist/multipart-*
