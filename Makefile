SHELL:= /bin/bash
PROGRAM:= ~/.virtualenvs/arenavision/bin/python arenavision_sopcast.py

VENV:= source .virtualenv/bin/activate &&

.PHONY: virtualenv

help:
	@echo "make virtualenv -- create install dependencies"
	@echo "make test -- execute unit tests"

virtualenv:
	virtualenv .virtualenv
	$(VENV) pip install -r requirements.txt
	$(VENV) pip install -r requirements-dev.txt

test: virtualenv
	$(VENV) py.test
