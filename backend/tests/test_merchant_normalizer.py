from modules.merchants.normalizer import normalize_merchant


def test_strips_compra_prefix():
    assert normalize_merchant("COMPRA LIDER PROVI") == "LIDER"


def test_strips_location_suffix():
    assert normalize_merchant("COMPRA LIDER PROVIDENCIA") == "LIDER"
    assert normalize_merchant("COMPRA LIDER LAS CONDES") == "LIDER"


def test_strips_pago_prefix():
    assert normalize_merchant("PAGO NETFLIX") == "NETFLIX"


def test_handles_no_prefix():
    assert normalize_merchant("STARBUCKS VITACURA") == "STARBUCKS"


def test_collapses_whitespace():
    assert normalize_merchant("  COPEC   ") == "COPEC"


def test_same_result_for_location_variants():
    v1 = normalize_merchant("COMPRA LIDER PROVI")
    v2 = normalize_merchant("COMPRA LIDER PROVIDENCIA")
    v3 = normalize_merchant("COMPRA LIDER LAS CONDES")
    assert v1 == v2 == v3
