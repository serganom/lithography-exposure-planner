# Contributing

Contributions are welcome after the repository owner selects a license.

## Development setup

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
~~~

## Rules for test data

- Do not commit production GDSII, CON, sample identifiers, doses, recipes, or
  internal directory paths.
- Build tests from synthetic layouts and minimal anonymized CON snippets.
- State coordinate units explicitly.
- Add a regression test for every GDS transform or CON serialization change.
- Do not claim compatibility with an EBL tool until an operator has validated
  the produced file on that target workflow.

See [the publication checklist](docs/PUBLICATION_CHECKLIST.md) for licensing and
third-party dependency review. CI is configured but not yet run remotely.
