from app.calculator import trip_fare
def test_policy_rounding_and_malformed_distance_export():
    assert trip_fare('6.0','1.5') == 74
    assert trip_fare('5000','1.5') == 65
