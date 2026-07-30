.PHONY: test validate demo package

test:
	python3 -m unittest discover -s tests -v

validate:
	python3 tests/validate_skill.py
	python3 -m py_compile meeting-scouter/scripts/meeting_scouter.py

demo:
	MEETING_SCOUTER_HOME=$$(mktemp -d) python3 meeting-scouter/scripts/meeting_scouter.py analyze \
		--text-file tests/fixtures/airy-meeting.md \
		--analysis-file tests/fixtures/airy-analysis.json \
		--no-learn

package:
	rm -f meeting-scouter.zip
	zip -r meeting-scouter.zip meeting-scouter -x '*/__pycache__/*'
