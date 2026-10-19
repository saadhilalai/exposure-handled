"""Step 7: the take order and blind-test picks, drawn ONCE before the shoot from a fixed seed.

Balanced: for every scene and person, each method is shot first, second and third exactly
once (a Latin square), so no method always gets the warm-up slot or the later light. In the
scenes everyone does (S1, S4), the people's rounds alternate (A, B, A, B...) so neither person
always gets the earlier light. The sunset uses two squares (the second mirrored) so each
method gets two blocks early, mid and late. Running this again prints the same order.

People are "Person A" / "Person B"; their names go into the run sheet before the shoot.
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


def show(scene, who, square, rounds):
    print("| %s | %s | %s |" % (scene, who, " | ".join("R%d: %s" % (n, " → ".join(r)) for n, r in zip(rounds, square))))


def main():
    rng = random.Random(SEED)
    print("| Scene | Who | Rounds |\n|---|---|---|")
    for scene in EVERYONE:
        squares = {p: latin_square(rng) for p in PEOPLE}
        for i, p in enumerate(PEOPLE):             # interleaved: A1 B1 A2 B2 A3 B3
            show(scene, p, squares[p], [1 + 2 * k + i for k in range(3)])
    for scene, who in SPLIT:
        show(scene, who, latin_square(rng), [1, 2, 3])
    show(CONTROL, "nobody needed", latin_square(rng), [1, 2, 3])
    square = latin_square(rng)
    sunset = square + [list(reversed(r)) for r in reversed(square)]
    print("\nS5 Sunset (one person, whoever is free that evening), 2-minute blocks in this order:")
    print(" / ".join(", ".join(r) for r in sunset))
    print("\nBlind test: the take used for each scene and person (same take number for all three methods):")
    for scene in EVERYONE:
        for i, p in enumerate(PEOPLE):
            k = rng.choice([1, 2, 3])                  # this person's k-th round = R(1 + 2(k-1) + i)
            print("  %s, %s: R%d (their round %d)" % (scene, p, 1 + 2 * (k - 1) + i, k))
    for scene, who in SPLIT:
        print("  %s, %s: round %d" % (scene, who, rng.choice([1, 2, 3])))
    print("  S5 Sunset: block round %d" % rng.choice([2, 3, 4, 5]))


if __name__ == "__main__":
    main()
