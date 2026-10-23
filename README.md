# FoodShare Tracker — FIT1056 Group 11

A Streamlit MVP for community food-bank profiles, inventory, hamper packing, donation offers and user administration. Data is stored in local JSON files under `data/`; no separate database or external service is required.

## Setup and Run

Create a virtual environment:

```bash
python -m venv .venv
```

**macOS / Linux**

```bash
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m streamlit run main.py
```

**Windows PowerShell**

```powershell
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run main.py
```

When the user store is empty, the sign-in screen prompts you to create the initial Admin account. Admin creates the Staff, Volunteer, Donor and Client accounts. Staff can edit profiles for existing active Client accounts; they cannot create Client accounts themselves.

## Role Workflows

- **Admin:** Create accounts, manage account roles and status (except another Admin’s account), view the access log, and view inventory.
- **Staff:** Manage Client profiles, add inventory, flag issues, generate safe hampers and review hamper history, set donation-priority categories, and create future drop-off slots.
- **Volunteer:** View pending hampers, add eligible items, mark hampers packed, view inventory and flag issues. The packing view shows hamper IDs, item names and quantities—not client profile details.
- **Donor:** Submit offers of up to five item categories, view priority categories, book a free future slot, acknowledge the food-safety checklist and receive a booking receipt.
- **Client:** View and update their own profile, including household size, dietary requirements, allergies, cultural needs, accessibility needs and preferred communication method. Consent is required to save. The preferred method is stored for staff reference; the app does not send messages.

Inventory intake validates quantity, expiry dates and allergen/dietary tags. Items are listed by earliest expiry, with an alert for items expiring today or within the next two days. Hamper generation excludes expired, out-of-stock or unsuitable items and currently adds one unit of each eligible item; household size does not affect generated quantities.

## Tests

Run the complete suite, including service tests and Streamlit AppTest UI tests:

```bash
.venv/bin/python -m pytest -q tests
```

On Windows PowerShell, use:

```powershell
.venv\Scripts\python -m pytest -q tests
```

UI tests require Streamlit. Tests use temporary data directories rather than the project's data files.

To run only the service/domain tests with Python's built-in `unittest` runner, without PyTest or Streamlit:

```bash
python -m unittest tests.test_acceptance_gaps tests.test_admin_accounts tests.test_auth_service tests.test_donation_offers_and_dates tests.test_donation_service tests.test_hamper_conflict_messages tests.test_hamper_matching tests.test_inventory tests.test_inventory_tags_and_flags tests.test_profile_fields -v
```

## Data and Known Limitations

The `FOODSHARE_DATA_DIR` environment variable can point the app to another data directory; restart the app after changing it. JSON files are replaced atomically individually, but packing updates both `inventory.json` and `hampers.json` and is not one atomic transaction. Malformed JSON is not automatically recovered.

Other current limitations:

- Pending hampers have no complete cancel or regenerate workflow.
- Changes to an account's role or active status do not invalidate an already-open session immediately; they apply at the next login.
- Deleting a Client profile does not delete the Client account or linked hamper history.
- Inventory issue flags are displayed but are not used by hamper matching.
- Donation offers are stored separately and are not automatically added to inventory.
- Backup/restore, load testing and screen-reader accessibility still require separate evidence. The think-aloud usability sessions are reported in the SRS; proposed interface improvements have not yet been retested.

## Project Structure

`main.py` (entry point) · `app/` (Streamlit screens) · `src/services/` (workflows) · `src/domain/` (validation and safety rules) · `src/data/` (JSON repository) · `data/` (local data) · `tests/` (automated tests).

The existing `app/inverntory_ui.py` filename is retained because the current application imports it by that name.