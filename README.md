# FIT1056 Group 11 FoodShare Tracker

This MVP follows the SRS's five feature groups using the existing project folders. Data is stored in the existing `data/*.json` files; no database or external service is required.

## Run

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run main.py
```

On first run, create the initial Admin account. Sign in as Admin to create Staff, Volunteer, Donor and Client accounts. A Staff user can then create client profiles, record food, generate hampers, set donor priorities and define drop-off slots. Donors submit offers and book a free slot after acknowledging the safety checklist. Volunteers see only hamper IDs and food items in the packing view.

## Test

```sh
.venv/bin/python -m pytest -q tests
```

The service tests use temporary data directories and do not edit `data/*.json`. The screen tests (`tests/test_ui_flows.py`, `tests/test_ui_regressions.py`) need Streamlit installed. To run only the service tests without Streamlit or PyTest, name the modules, for example `python3 -m unittest tests.test_auth_service tests.test_admin_accounts tests.test_acceptance_gaps -v`.

## MVP coverage and limits

- F-01: client/staff profile entry (household size, dietary, allergies, cultural needs, accessibility needs and preferred communication method, recorded for staff reference only), consent, validation, own deletion and staff-only substitution notes.
- F-02: staff food intake, expiry and quantity validation, allergen/dietary tags (or "None", never both), expiry ordering, 48-hour warning and issue flags shown on the inventory list.
- F-03: allergy/dietary safe list, anonymised volunteer Packing View (item name and quantity only), role-specific warnings for unsafe manual additions (staff see the reason, volunteers do not), hamper history and stock deduction on packing.
- F-04: priority categories, staff-defined slots, multi-category donor offers, date-specific slot selection, checklist, conflict-free booking and receipt.
- F-05: password login, five roles, account administration and audit entries. Passwords use salted PBKDF2 hashes.

This is a prototype, not full SRS completion. In particular, the 50-user load target, screen reader audit, backup/restore exercise and think-aloud usability evaluation still need separate evidence. Run the interface and acceptance scenarios with synthetic data before reporting them as passed.

The existing `app/inverntory_ui.py` filename is intentionally retained to preserve the folder structure.
