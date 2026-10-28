"""Post-auction review: double-dummy analysis and par (via the DDS solver in endplay)."""

from __future__ import annotations

from endplay.dds import calc_dd_table, par
from endplay.types import Contract as DDContract
from endplay.types import Deal, Denom, Penalty, Player, Vul

from .auction import Contract
from .cards import SEATS, Hand, side, to_pbn

DENOM = {"C": Denom.clubs, "D": Denom.diamonds, "H": Denom.hearts, "S": Denom.spades, "NT": Denom.nt}
STRAIN_OF = {v: k for k, v in DENOM.items()}
PLAYER = {"N": Player.north, "E": Player.east, "S": Player.south, "W": Player.west}
SEAT_OF = {v: k for k, v in PLAYER.items()}
VUL = {"-": Vul.none, "NS": Vul.ns, "EW": Vul.ew, "ALL": Vul.both}
PENALTY = {"": Penalty.passed, "X": Penalty.doubled, "XX": Penalty.redoubled}
DOUBLED_OF = {v: k for k, v in PENALTY.items()}


def ns_score(level: int, strain: str, declarer: str, doubled: str, result: int, vulnerability: str) -> int:
    """Duplicate score from North-South's point of view. `result` is tricks over/under the contract."""
    c = DDContract(level=level, denom=DENOM[strain], declarer=PLAYER[declarer],
                   penalty=PENALTY[doubled], result=result)
    score = c.score(VUL[vulnerability])
    return score if side(declarer) == "NS" else -score


def double_dummy(hands: dict[str, Hand], dealer: str, vulnerability: str,
                 contract: Contract | None) -> dict:
    """Tricks per strain and declarer, par, and how the final contract fares double dummy."""
    table = calc_dd_table(Deal(to_pbn(hands)))
    tricks = {strain: {seat: table[DENOM[strain], PLAYER[seat]] for seat in SEATS} for strain in DENOM}

    p = par(table, VUL[vulnerability], PLAYER[dealer])
    par_contracts = [
        {
            "level": c.level,
            "strain": STRAIN_OF[c.denom],
            "declarer": SEAT_OF[c.declarer],
            "doubled": DOUBLED_OF[c.penalty],
            "result": c.result,
        }
        for c in p
        if not c.is_passout()
    ]

    if contract is None:
        result = {"tricks": None, "result": 0, "score": 0}
    else:
        made = tricks[contract.strain][contract.declarer]
        over = made - (6 + contract.level)
        result = {
            "tricks": made,
            "result": over,
            "score": ns_score(contract.level, contract.strain, contract.declarer,
                              contract.doubled, over, vulnerability),
        }

    return {
        "tricks": tricks,
        "par": {"score": p.score, "contracts": par_contracts},
        "contract": result,
    }
