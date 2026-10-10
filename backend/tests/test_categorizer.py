from app.services.categorizer import match_builtin, normalize_merchant


def test_normalize_strips_processor_prefixes_and_store_numbers():
    assert normalize_merchant("SQ *JOES COFFEE #4421 CHARLOTTE NC") == "JOES COFFEE CHARLOTTE"
    assert normalize_merchant("TST* MAMA RICOTTAS") == "MAMA RICOTTAS"
    assert normalize_merchant("STARBUCKS STORE 08812") == "STARBUCKS"


def test_normalize_keeps_names_that_end_in_two_letters():
    assert normalize_merchant("STAPLES") == "STAPLES"
    assert normalize_merchant("AT&T") == "AT&T"


def test_builtin_rules():
    assert match_builtin("ADOBE CREATIVE CLOUD") == "Software & Subscriptions"
    assert match_builtin("UBER EATS") == "Meals"
    assert match_builtin("UBER TRIP") == "Travel"
    assert match_builtin("IRS USATAXPYMT") == "Taxes"
    assert match_builtin("JOES COFFEE CHARLOTTE") is None


def test_keyword_must_be_whole_word():
    # "DELTA" shouldn't match "DELTAVISION"
    assert match_builtin("DELTAVISION STUDIOS") is None
