# MVP test record — 2026-10-11

Environment: Python 3.14.5 in the existing `.venv`; Streamlit 1.65.0; PyTest 9.1.1; macOS. Test data was created in temporary directories, so the project's `data/*.json` files were not changed.

Command: `.venv/bin/python -m pytest -q tests`

Result: **20 passed, 0 failed** (plus 2 passing parameterised subtests). This includes five actor-level Streamlit AppTest flows in `tests/test_ui_flows.py`.

Verified service behaviour:

- F-01: consent and household-size validation; volunteer access to profiles denied.
- F-02: zero/negative stock rejected; past expiry rejected; current-day expiry accepted; expiry ordering and near-expiry flag.
- F-03: peanut allergen filtering; anonymised volunteer view; unsafe manual addition blocked; packing deducts stock once; competing hampers cannot make stock negative; a changed allergy blocks packing an old list.
- F-04: positive offer quantity, checklist required, one booking per slot, receipt data and priority categories.
- F-05: password hashing, invalid login rejection, role change on next login, audit entry and admin account restriction.

Actor-level AppTest results: FTEST-01 client consent blocks then permits profile save; FTEST-02 staff inventory rejects quantity 0 then accepts 1; FTEST-03 staff generates a peanut-safe hamper and volunteer navigation omits client profiles; FTEST-04 donor cannot book without checklist but receives confirmation after booking; FTEST-05 volunteer navigation and service access deny profile access. These tests execute Streamlit widgets and service persistence with temporary JSON data. The initial administrator flow and login also rendered without exceptions in a manual AppTest check; Admin, Staff, Volunteer, Donor and Client landing screens each rendered without exceptions. The app started as a Streamlit server and `/_stcore/health` returned `ok`.

Scope limit: these tests cover the implemented MVP paths. They do not establish full coverage of every SRS functional requirement, the 50-user load target, accessibility compliance, backup/restore or think-aloud usability results.
