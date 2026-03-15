"""Parse all estadual .ces config files fully."""
import struct, os, glob

def parse_estadual(filepath):
    data = open(filepath, "rb").read()
    
    # ConfigEstadualType has 6 fields:
    # I desempate, I divisao, I formula, I id, I nRebaixados, [I finaisIdaVolta
    ces_idx = data.find(b"ConfigEstadualType")
    if ces_idx < 0:
        return None
    
    # Find xp (TC_ENDBLOCKDATA + TC_NULL) after class descriptor
    # After class name + uid(8) + flags(1) + fieldcount(2) + field descs + xp
    xp_pos = data.find(b"\x78\x70", ces_idx + 18)  # after "ConfigEstadualType"
    if xp_pos < 0:
        return None
    
    pos = xp_pos + 2
    results = []
    for div_num in range(4):
        if pos + 20 > len(data):
            break
        desempate = struct.unpack(">i", data[pos:pos+4])[0]; pos += 4
        divisao = struct.unpack(">i", data[pos:pos+4])[0]; pos += 4
        formula = struct.unpack(">i", data[pos:pos+4])[0]; pos += 4
        estado_id = struct.unpack(">i", data[pos:pos+4])[0]; pos += 4
        nRebaixados = struct.unpack(">i", data[pos:pos+4])[0]; pos += 4
        
        # finaisIdaVolta array
        finais = []
        if pos < len(data) and data[pos] == 0x75:  # TC_ARRAY
            pos += 1
            if data[pos] == 0x72:  # TC_CLASSDESC (first time for [I)
                nl = struct.unpack(">H", data[pos+1:pos+3])[0]
                pos += 3 + nl + 8 + 1 + 2 + 1 + 1  # skip class desc
            elif data[pos] == 0x71:  # TC_REFERENCE
                pos += 5
            alen = struct.unpack(">i", data[pos:pos+4])[0]; pos += 4
            for _ in range(alen):
                finais.append(struct.unpack(">i", data[pos:pos+4])[0])
                pos += 4
        elif pos < len(data) and data[pos] == 0x70:  # TC_NULL
            pos += 1
        
        results.append({
            "divisao": divisao, "formula": formula, "id": estado_id,
            "nRebaixados": nRebaixados, "desempate": desempate,
            "finaisIdaVolta": finais,
        })
        
        # Next object marker
        if div_num < 3 and pos < len(data) - 1:
            if data[pos] == 0x73 and data[pos+1] == 0x71:
                pos += 6
    
    return results


# Parse all estadual files
print("=" * 80)
print("CONFIGURACOES ESTADUAIS")
print("=" * 80)

for cesfile in sorted(glob.glob("conf_estadual/*.ces")):
    fname = os.path.basename(cesfile).replace(".ces", "")
    results = parse_estadual(cesfile)
    if results:
        print(f"\n{fname}:")
        for r in results:
            finais_str = str(r["finaisIdaVolta"]) if r["finaisIdaVolta"] else "[]"
            print(f"  Div {r['divisao']}: formula={r['formula']}, "
                  f"nRebaixados={r['nRebaixados']}, desempate={r['desempate']}, "
                  f"finaisIdaVolta={finais_str}")
    else:
        print(f"\n{fname}: PARSE FAILED")
