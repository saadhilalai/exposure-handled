"""Generate a property-code -> name table from Sony's CrDeviceProperty.h.

Run at build time against the developer's own SDK download, so no Sony
file is copied into this repo. Output is a C++ include file with lines like:
    {0x0100u, "FNumber"},
"""
import re
import sys


def parse_property_codes(header_text):
    match = re.search(r"enum\s+CrDevicePropertyCode\s*:\s*\w+\s*\{(.*?)\};", header_text, re.S)
    if not match:
        raise SystemExit("CrDevicePropertyCode enum not found in header")
    body = re.sub(r"/\*.*?\*/", "", match.group(1), flags=re.S)
    body = re.sub(r"//[^\n]*", "", body)

    codes = {}
    value = -1
    for item in body.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            name, expr = (part.strip() for part in item.split("=", 1))
            value = codes[expr] if expr in codes else int(expr, 0)
        else:
            name = item
            value += 1
        codes[name] = value
    return codes


def main():
    header_path, out_path = sys.argv[1], sys.argv[2]
    with open(header_path, encoding="utf-8-sig", errors="replace") as f:
        codes = parse_property_codes(f.read())

    lines = []
    for name, value in codes.items():
        short = name.replace("CrDeviceProperty_", "", 1)
        if short in ("Undefined", "MaxVal") or short.startswith("Reserved"):
            continue
        lines.append('{0x%04Xu, "%s"},' % (value, short))

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("// Generated from CrDeviceProperty.h by gen_property_names.py. Do not edit.\n")
        f.write("\n".join(lines) + "\n")
    print("wrote %d property names to %s" % (len(lines), out_path))


if __name__ == "__main__":
    main()
