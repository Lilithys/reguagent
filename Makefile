PYTHON ?= python3

.PHONY: demo test validate check package api

demo:
	$(PYTHON) scripts/demo.py

test:
	$(PYTHON) -m unittest discover -s agent -p 'test_*.py'
	$(PYTHON) -m unittest discover -s scripts -p 'test_*.py'

validate:
	$(PYTHON) scripts/validate_dataset.py
	$(PYTHON) data/regulatory-governance-dataset/scripts/validate_person1_data.py --root calibrated_v0_2 --strict --require-first-demo

check: test validate demo

package:
	$(PYTHON) scripts/package_submission.py

api:
	$(PYTHON) agent/api_server.py --db runs/demo/cases.sqlite3
