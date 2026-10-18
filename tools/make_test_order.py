"""Step 7: the take order and blind-test picks, drawn ONCE before the shoot from a fixed seed.

Balanced: in every scene each method is shot first, second and third exactly once (a Latin
square), so no method always gets the "warm-up" slot or the later light. The sunset uses two
squares (the second mirrored) so each method gets two blocks early, mid and late.
Running this again prints the same order (that's the point of the fixed seed).
"""
import random

SEED = 20261018
METHODS = ["Agent", "FX2 auto", "Manual"]
SCENES = ["S1 Window-backlit face", "S2 Shade to sun walk", "S3 Tungsten interior", "S4 Low light",
          "S6 Static control"]


def latin_square(rng):
    base = METHODS[:]
    rng.shuffle(base)
    rows = [base[i:] + base[:i] for i in range(3)]
    rng.shuffle(rows)
    return rows


def main():
    rng = random.Random(SEED)
    print("| Scene | Round 1 | Round 2 | Round 3 |\n|---|---|---|---|")
    for scene in SCENES:
        print("| %s | %s |" % (scene, " | ".join(" → ".join(r) for r in latin_square(rng))))
    square = latin_square(rng)
    sunset = square + [list(reversed(r)) for r in reversed(square)]
    print("\nS5 Sunset, 2-minute blocks in this order:")
    print(" / ".join(", ".join(r) for r in sunset))
    print("\nBlind test, take used per scene (same take number for all three methods):")
    for scene in SCENES[:4]:                     # the static control isn't rated
        print("  %s: take %d" % (scene, rng.choice([1, 2, 3])))
    print("  S5 Sunset: block round %d" % rng.choice([2, 3, 4, 5]))


if __name__ == "__main__":
    main()
