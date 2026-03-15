"""Debug parser for BRA.cfg - traces exact field offsets."""
import struct

data = open("conf_ligas_nacionais/BRA.cfg", "rb").read()

FIELDS = [
    ("classificaPeloGeral", "Z"),
    ("desempate", "I"),
    ("divisao", "I"),
    ("doisTurnos", "Z"),
    ("formula", "I"),
    ("jogosDentroGrupo", "Z"),
    ("melhoresTerceiros", "Z"),
    ("nGrupos", "I"),
    ("nRebaixados", "I"),
    ("nTimes", "I"),
    ("numeroTimesMataMata", "I"),
    ("pais", "I"),
    ("playoffRebaixamento", "I"),
    ("rebaixadoPeloGrupo", "Z"),
    ("rebaixadosDireto", "I"),
    ("vagasSobemPeloMataMata", "I"),
    ("valido", "Z"),
    ("versaoArquivo", "I"),
]


def parse_debug(data, start, label):
    pos = start
    print(f"\n{label} - start=0x{start:03X}")
    vals = {}
    for name, typ in FIELDS:
        if typ == "I":
            raw = data[pos : pos + 4]
            val = struct.unpack(">i", raw)[0]
            print(f"  0x{pos:03X}: {name}(I) = {raw.hex()} = {val}")
            pos += 4
        else:
            val = bool(data[pos])
            print(f"  0x{pos:03X}: {name}(Z) = {data[pos]:02x} = {val}")
            pos += 1
        vals[name] = val
    print(f"  End at 0x{pos:03X}")
    # Read arrays after primitives
    print(f"  --- Arrays at 0x{pos:03X} ---")
    for arr_name in ["duasVoltasMataMata", "duasVoltasMataMataSobe", "duasVoltasplayoffReb"]:
        if data[pos] == 0x75:  # TC_ARRAY
            pos += 1
            if data[pos] == 0x72:  # TC_CLASSDESC (first time)
                # Skip class descriptor for [Z
                name_len = struct.unpack(">H", data[pos + 1 : pos + 3])[0]
                pos += 3 + name_len + 8 + 1 + 2 + 1 + 1  # name+uid+flags+nfields+endblock+null
            elif data[pos] == 0x71:  # TC_REFERENCE
                pos += 5  # 1 + 4 byte handle
            arr_len = struct.unpack(">i", data[pos : pos + 4])[0]
            pos += 4
            arr_data = list(data[pos : pos + arr_len])
            pos += arr_len
            print(f"  {arr_name}[{arr_len}] = {arr_data}")
    # Read strings
    for str_name in ["nome", "nomeDivisao"]:
        if data[pos] == 0x74:  # TC_STRING
            pos += 1
            slen = struct.unpack(">H", data[pos : pos + 2])[0]
            pos += 2
            sval = data[pos : pos + slen].decode("utf-8", errors="replace")
            pos += slen
            print(f"  {str_name} = '{sval}'")
        elif data[pos] == 0x71:  # TC_REFERENCE
            pos += 5
            print(f"  {str_name} = <reference>")
    return vals, pos


# Serie A at 0x235
vals_a, pos = parse_debug(data, 0x235, "Serie A")

# Serie B, C, D
for label in ["Serie B", "Serie C", "Serie D"]:
    # Find TC_OBJECT(0x73) + TC_REFERENCE(0x71)
    while pos < len(data) - 1:
        if data[pos] == 0x73 and data[pos + 1] == 0x71:
            pos += 6
            break
        pos += 1
    vals, pos = parse_debug(data, pos, label)
