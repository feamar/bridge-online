import pytest

from bridge.auction import Auction, Contract, IllegalCall
from bridge.cards import board_dealer, board_vulnerability, deal, hcp, to_pbn


def run(dealer, calls):
    a = Auction(dealer)
    for c in calls:
        a.make_call(c)
    return a


def test_passed_out():
    a = run("N", ["P", "P", "P", "P"])
    assert a.is_over and a.contract() is None


def test_three_passes_after_opening_end_auction():
    a = run("N", ["1H", "P", "P"])
    assert not a.is_over
    a.make_call("P")
    assert a.is_over
    assert a.contract() == Contract(1, "H", "N", "")


def test_declarer_is_first_of_side_to_name_strain():
    a = run("N", ["1S", "P", "2H", "P", "4S", "P", "P", "P"])
    assert a.contract() == Contract(4, "S", "N", "")
    a = run("E", ["P", "1D", "P", "1H", "P", "3NT", "P", "P", "P"])
    assert a.contract() == Contract(3, "NT", "S", "")


def test_double_and_redouble():
    a = run("N", ["1NT", "X", "XX", "P", "P", "P"])
    assert a.contract() == Contract(1, "NT", "N", "XX")
    a = run("N", ["1NT", "X", "2C", "P", "P", "P"])
    assert a.contract().doubled == ""


def test_illegal_calls():
    a = run("N", ["1H"])
    assert "1H" not in a.legal_calls() and "1S" in a.legal_calls()
    assert "X" in a.legal_calls() and "XX" not in a.legal_calls()
    with pytest.raises(IllegalCall):
        a.make_call("1C")
    a = run("N", ["1H", "P"])
    assert "X" not in a.legal_calls()  # cannot double partner
    a = run("N", ["1H", "P", "P"])
    assert "X" in a.legal_calls()  # balancing double of opponent's bid


def test_deal_is_complete():
    hands = deal()
    cards = [s + r for h in hands.values() for s, rs in h.items() for r in rs]
    assert len(cards) == 52 and len(set(cards)) == 52
    assert all(sum(len(r) for r in h.values()) == 13 for h in hands.values())
    assert sum(hcp(h) for h in hands.values()) == 40
    assert to_pbn(hands).startswith("N:")


def test_board_schedule():
    assert [board_dealer(b) for b in (1, 2, 3, 4, 5)] == ["N", "E", "S", "W", "N"]
    assert [board_vulnerability(b) for b in (1, 2, 3, 4, 17)] == ["-", "NS", "EW", "ALL", "-"]
