"""Client profile validation shared by the service and tests."""


def validate_profile(household_size, dietary_requirements, consent):
    if not isinstance(household_size, int) or isinstance(household_size, bool) or household_size < 1:
        raise ValueError("Household size must be at least 1")
    if not dietary_requirements:
        raise ValueError("Select dietary requirements or None")
    if not consent:
        raise ValueError("Consent is required before saving a profile")
