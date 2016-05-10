PROGRAM := /home/gerard/.virtualenvs/arenavision/bin/python arenavision_sopcast.py

.PHONY: test-acceptance

all: test-acceptance
	@echo "No unit test yet..."

test-acceptance:
	$(PROGRAM) thisstringwillnotbefoundanywayintheputput || true
	
