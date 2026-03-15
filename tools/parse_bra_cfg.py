"""Parse BRA.cfg (Java serialized ConfigLigaType) to extract division configs."""
import struct, json, sys, os, glob

def parse_config_liga(data, start):
    """Parse one ConfigLigaType instance from offset 'start'. Returns (dict, end_offset)."""
    # Exact field types from class descriptor (verified from binary):
    FIELDS = [
        ("classificaPeloGeral", "Z"),  # boolean
        ("desempate", "I"),
        ("divisao", "I"),
        ("doisTurnos", "Z"),  # boolean
        ("formula", "I"),
        ("jogosDentroGrupo", "Z"),  # boolean
        ("melhoresTerceiros", "Z"),  # boolean
        ("nGrupos", "I"),
        ("nRebaixados", "I"),
        ("nTimes", "I"),
        ("numeroTimesMataMata", "I"),
        ("pais", "I"),
        ("playoffRebaixamento", "I"),
        ("rebaixadoPeloGrupo", "Z"),  # boolean
        ("rebaixadosDireto", "I"),
        ("vagasSobemPeloMataMata", "I"),
        ("valido", "Z"),  # boolean
        ("versaoArquivo", "I"),
    ]
    pos = start
    vals = {}
    for name, typ in FIELDS:
        if typ == "I":
            val = struct.unpack(">i", data[pos:pos+4])[0]
            pos += 4
        else:
            val = bool(data[pos])
            pos += 1
        vals[name] = val
    return vals, pos


# Parse BRA.cfg
data = open("conf_ligas_nacionais/BRA.cfg", "rb").read()

# nTimes for Serie A is at offset 0x24D. Before nTimes:
# Z(1)+I(4)+I(4)+Z(1)+I(4)+Z(1)+Z(1)+I(4)+I(4) = 24 bytes
# So Serie A data starts at 0x24D - 24 = 0x235
SERIE_STARTS = {"A": 0x235}

# Find all 4 divisions
print("=" * 60)
print("BRA.cfg - Configuracao das Divisoes Brasileiras")
print("=" * 60)

# Parse Serie A first
cfg_a, end_a = parse_config_liga(data, 0x235)
print(f"\n--- Serie A (divisao={cfg_a['divisao']}) ---")
for k, v in cfg_a.items():
    print(f"  {k}: {v}")

# After primitive fields, there are 2 string fields (nomeLiga, nomeDivisao)
# Each is either TC_STRING(74) + len(2) + bytes, or TC_REFERENCE(71) + handle(4)
# Then next object: TC_OBJECT(73) + TC_REFERENCE(71) + handle(4) + instance data

# Let's use a search approach: find each division's nTimes offset
# nTimes = 20 for A,B,C and 68 for D in big-endian
import re
divisions = []
# Find byte 0x14 (20) preceded by nRebaixados (4 bytes) at expected positions
# Actually, let's just scan for the "sq" (TC_OBJECT + TC_REFERENCE) pattern between divisions
pos = end_a
for serie_name in ["B", "C", "D"]:
    # Skip string fields and find next object marker
    # After strings, look for TC_OBJECT(0x73) + TC_REFERENCE(0x71)
    while pos < len(data) - 1:
        if data[pos] == 0x73 and data[pos+1] == 0x71:
            # Found object start - skip TC_OBJECT(1) + TC_REFERENCE(1) + handle(4)
            pos += 6
            break
        pos += 1
    cfg, pos = parse_config_liga(data, pos)
    print(f"\n--- Serie {serie_name} (divisao={cfg['divisao']}) ---")
    for k, v in cfg.items():
        print(f"  {k}: {v}")

# Now parse estadual configs
print("\n" + "=" * 60)
print("Configuracoes Estaduais (.ces)")
print("=" * 60)

estadual_dir = "conf_estadual"
if os.path.isdir(estadual_dir):
    for cesfile in sorted(glob.glob(os.path.join(estadual_dir, "*.ces"))):
        fname = os.path.basename(cesfile)
        edata = open(cesfile, "rb").read()
        # Find field descriptors to verify structure
        # Look for nTimes pattern: search for known int values
        # Estadual configs may use same ConfigLigaType or different class
        # Try to find "xp" marker (0x78 0x70) which ends class desc
        xp_pos = edata.find(b"\x78\x70")
        if xp_pos >= 0:
            start = xp_pos + 2
            try:
                cfg, _ = parse_config_liga(edata, start)
                if 4 <= cfg["nTimes"] <= 20 and cfg["pais"] == 29:
                    print(f"\n--- {fname} ---")
                    print(f"  nTimes={cfg['nTimes']}, nGrupos={cfg['nGrupos']}, "
                          f"doisTurnos={cfg['doisTurnos']}, nRebaixados={cfg['nRebaixados']}, "
                          f"formula={cfg['formula']}, nTimesMataMata={cfg['numeroTimesMataMata']}, "
                          f"divisao={cfg['divisao']}")
                else:
                    # Try offset +1 in case of alignment
                    cfg2, _ = parse_config_liga(edata, start + 1)
                    if 4 <= cfg2["nTimes"] <= 20:
                        print(f"\n--- {fname} ---")
                        print(f"  nTimes={cfg2['nTimes']}, nGrupos={cfg2['nGrupos']}, "
                              f"doisTurnos={cfg2['doisTurnos']}, nRebaixados={cfg2['nRebaixados']}, "
                              f"formula={cfg2['formula']}, nTimesMataMata={cfg2['numeroTimesMataMata']}")
                    else:
                        print(f"\n--- {fname} --- (parse failed: nTimes={cfg['nTimes']})")
            except Exception as e:
                print(f"\n--- {fname} --- (error: {e})")
