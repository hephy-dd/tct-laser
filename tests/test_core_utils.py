from tct_laser.core import utils


def test_si_format_basic_scales():
    assert utils.si_format(0, "V") == "0 V"
    assert utils.si_format(0.9999, "V") == "999.9 mV"
    assert utils.si_format(1.0, "V") == "1 V"
    assert utils.si_format(999.0, "V") == "999 V"
    assert utils.si_format(1000.0, "V") == "1 kV"
    assert utils.si_format(1e-3, "A") == "1 mA"
    assert utils.si_format(1e-4, "A") == "100 µA"
    assert utils.si_format(-1e-3, "V") == "-1 mV"
    assert utils.si_format(1e6, "Hz") == "1 MHz"
    assert utils.si_format(5e15, "Hz") == "5000 THz"


def test_si_format_non_finite():
    assert utils.si_format(float("nan"), "V") == "nan"
    assert utils.si_format(float("+inf"), "V") == "inf"
    assert utils.si_format(float("-inf"), "V") == "-inf"
