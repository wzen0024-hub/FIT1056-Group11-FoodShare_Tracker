"""Client profile validation shared by the service and tests."""

# FR-01.1: the preferred communication method is recorded for staff reference
# only. The system never sends messages (automated SMS alerts, F-06, are out of scope).
NO_COMMUNICATION_PREFERENCE = "Not specified"
COMMUNICATION_METHODS = (NO_COMMUNICATION_PREFERENCE, "SMS", "Phone call", "Email", "In person")

# Values assumed for profiles that were saved before these fields existed, so that
# older records in data/profiles.json keep loading without a data migration.
PROFILE_DEFAULTS = {"accessibility_needs": "",
                    "preferred_communication": NO_COMMUNICATION_PREFERENCE}


def with_profile_defaults(profile):
    """Return a copy of a stored profile with any missing newer fields filled in."""
    return {**PROFILE_DEFAULTS, **profile}


def validate_profile(household_size, dietary_requirements, consent,
                     accessibility_needs="", preferred_communication=NO_COMMUNICATION_PREFERENCE):
    if not isinstance(household_size, int) or isinstance(household_size, bool) or household_size < 1:
        raise ValueError("Household size must be at least 1")
    if not dietary_requirements:
        # The screen shows the stored value "None" as "No restrictions" (FR-01.7).
        raise ValueError("Select dietary requirements, or No restrictions")
    if not consent:
        raise ValueError("Consent is required before saving a profile")
    # Accessibility needs are free text on purpose: the SRS does not define a fixed list.
    if not isinstance(accessibility_needs, str):
        raise ValueError("Accessibility needs must be text")
    if preferred_communication not in COMMUNICATION_METHODS:
        raise ValueError("Choose a preferred communication method from the list")
