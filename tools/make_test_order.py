"""Step 7: the take order and blind-test picks, drawn ONCE before the shoot from a fixed seed.

Balanced: for every scene and person, each method is shot first, second and third exactly
once (a Latin square), so no method always gets the warm-up slot or the later light. In the
scenes everyone does (S1, S4), the people's rounds alternate (A, B, A, B...) so neither person
always gets the earlier light. The sunset uses two squares (the second mirrored) so each
method gets two blocks early, mid and late. Running this again prints the same order (the
plan froze it: tag step7-plan-final).

People are "Person A" / "Person B"; their names are written on the printed run sheet, never
in the repo.
"""
import random

SEED = 20261018
METHODS = ["Agent", "FX2 auto", "Manual"]
PEOPLE = ["Person A", "Person B"]
EVERYONE = ["S1 Window-backlit face", "S4 Low light"]                 # the two toughest face scenes
SPLIT = [("S2 Shade to sun walk", "Person A"), ("S3 Tungsten interior", "Person B")]
CONTROL = "S6 Static control"


def latin_square(rng):
    base = METHODS[:]
    rng.shuffle(base)
    rows = [base[i:] + base[:i] for i in range(3)]
    rng.shuffle(rows)
    return rows


def build_order():
    """The frozen order as data. (The random draws happen in exactly the same sequence as
    when the plan was approved; don't reorder them.)"""
    rng = random.Random(SEED)
    rows = []                                          # (scene, who, [(round number, [methods])])
    for scene in EVERYONE:
        squares = {p: latin_square(rng) for p in PEOPLE}
        for i, p in enumerate(PEOPLE):                 # interleaved: A1 B1 A2 B2 A3 B3
            rows.append((scene, p, list(zip([1 + 2 * k + i for k in range(3)], squares[p]))))
    for scene, who in SPLIT:
        rows.append((scene, who, list(zip([1, 2, 3], latin_square(rng)))))
    rows.append((CONTROL, "nobody needed", list(zip([1, 2, 3], latin_square(rng)))))
    square = latin_square(rng)
    sunset = square + [list(reversed(r)) for r in reversed(square)]
    picks = []
    for scene in EVERYONE:
        for i, p in enumerate(PEOPLE):
            k = rng.choice([1, 2, 3])                  # this person's k-th round = R(1 + 2(k-1) + i)
            picks.append((scene, p, "R%d (their round %d)" % (1 + 2 * (k - 1) + i, k)))
    for scene, who in SPLIT:
        picks.append((scene, who, "round %d" % rng.choice([1, 2, 3])))
    picks.append(("S5 Sunset", None, "block round %d" % rng.choice([2, 3, 4, 5])))
    return {"rows": rows, "sunset": sunset, "picks": picks}


def main():
    order = build_order()
    print("| Scene | Who | Rounds |\n|---|---|---|")
    for scene, who, rounds in order["rows"]:
        print("| %s | %s | %s |" % (scene, who, " | ".join("R%d: %s" % (n, " → ".join(r)) for n, r in rounds)))
    print("\nS5 Sunset (one person, whoever is free that evening), 2-minute blocks in this order:")
    print(" / ".join(", ".join(r) for r in order["sunset"]))
    print("\nBlind test: the take used for each scene and person (same take number for all three methods):")
    for scene, who, pick in order["picks"]:
        print("  %s%s: %s" % (scene, ", " + who if who else "", pick))


if __name__ == "__main__":
    main()
