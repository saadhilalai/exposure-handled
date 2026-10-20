# luts/

The LUT for the Step 7 blind test goes here. It's Sony's file, so it never goes in the repo: `.gitignore` keeps everything in this folder out except this note.

| File | What it is | SHA-256 |
|---|---|---|
| `2_SGamut3CineSLog3_To_LC-709TypeA.cube` | Sony LookProfile LUT, S-Gamut3.Cine/S-Log3 → LC-709TypeA, full in/full out, v1.04.04, 33-point | `04066dc0a6d2b381bc146dfc93c01cb8154581653a070ab1739d1656c34c236d` |

To set it up on another machine, get the file from Sony (its LookProfile LUTs for S-Log3/S-Gamut3.Cine) and put it here. Then check it's the same file: `shasum -a 256 luts/*.cube`.

Why this one: [docs/step7-tools.md](../docs/step7-tools.md). The rule it's used under: [docs/step7-test-plan.md](../docs/step7-test-plan.md).
