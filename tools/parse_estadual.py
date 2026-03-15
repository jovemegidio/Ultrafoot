"""Parse estadual .ces config files."""
import struct, os, glob

def hex_dump_region(data, start, length, label=""):
    print(f"\n{label} hex dump from 0x{start:03X}:")
    for i in range(0, length, 16):
        off = start + i
        if off >= len(data):
            break
        end = min(off + 16, len(data))
        hx = " ".join(f"{data[j]:02X}" for j in range(off, end))
        asc = "".join(chr(data[j]) if 32 <= data[j] < 127 else "." for j in range(off, end))
        print(f"  {off:04X}: {hx:<48} {asc}")


# First, examine SP.ces structure
for fname in ["SP.ces", "RJ.ces", "MG.ces", "BA.ces", "RS.ces", "SC.ces", "PR.ces", "CE.ces", "AC.ces"]:
    fpath = os.path.join("conf_estadual", fname)
    if not os.path.isfile(fpath):
        continue
    data = open(fpath, "rb").read()
    print(f"\n{'='*60}")
    print(f"{fname} - {len(data)} bytes")
    print(f"{'='*60}")

    # Find class name
    import re
    strings = re.findall(rb"[\x20-\x7E]{4,}", data)
    for s in strings:
        print(f"  String: {s.decode('latin-1')}")

    # Find field descriptors
    i = 0
    fields = []
    while i < min(len(data), 0x200) - 3:
        tc = chr(data[i]) if 32 <= data[i] < 127 else ""
        if tc in "IZBSIJFDCL":
            namelen = (data[i + 1] << 8) | data[i + 2]
            if 3 <= namelen <= 30:
                name = data[i + 3 : i + 3 + namelen]
                try:
                    namestr = name.decode("ascii")
                    if namestr.isidentifier():
                        fields.append((tc, namestr))
                        i += 3 + namelen
                        continue
                except:
                    pass
        i += 1

    if fields:
        print(f"\n  Fields ({len(fields)}):")
        for tc, name in fields:
            print(f"    {tc} {name}")

    # Try to find xp marker and read data
    xp_idx = data.find(b"\x78\x70")
    if xp_idx >= 0:
        start = xp_idx + 2
        print(f"\n  Data starts at 0x{start:03X}")
        hex_dump_region(data, start, min(80, len(data) - start), "  Instance data")
