from bridge.auction import Contract
from bridge.review import double_dummy, ns_score


def h(pbn):
    return dict(zip("SHDC", [list(p) for p in pbn.split(".")]))


# North holds all spades, East all hearts, South all diamonds, West all clubs.
HANDS = {
    "N": h("AKQJT98765432..."),
    "E": h(".AKQJT98765432.."),
    "S": h("..AKQJT98765432."),
    "W": h("...AKQJT98765432"),
}


def test_scores_from_north_south_view():
    assert ns_score(4, "S", "N", "", 0, "-") == 420
    assert ns_score(4, "S", "N", "", 0, "NS") == 620
    assert ns_score(3, "NT", "E", "X", -2, "EW") == 500
    assert ns_score(2, "H", "W", "", 1, "-") == -140


def test_double_dummy_tricks_par_and_result():
    dd = double_dummy(HANDS, "N", "-", Contract(4, "S", "N", ""))
    assert dd["tricks"]["S"]["N"] == 13
    assert dd["tricks"]["H"]["E"] == 13
    assert dd["contract"] == {"tricks": 13, "result": 3, "score": 510}
    assert dd["par"]["contracts"][0]["level"] == 7


def test_passed_out_board():
    dd = double_dummy(HANDS, "N", "-", None)
    assert dd["contract"]["score"] == 0
