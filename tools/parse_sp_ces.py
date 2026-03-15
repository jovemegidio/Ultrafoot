"""Complete hex dump and parsing of SP.ces"""
import struct

data = open("conf_estadual/SP.ces", "rb").read()
print(f"SP.ces: {len(data)} bytes\n")

# Full hex dump
for off in range(0, len(data), 16):
    hx = " ".join(f"{data[off+j]:02X}" for j in range(min(16, len(data)-off)))
    asc = "".join(chr(data[off+j]) if 32 <= data[off+j] < 127 else "." for j in range(min(16, len(data)-off)))
    print(f"{off:04X}: {hx:<48} {asc}")

print("\n\n=== Field Descriptors ===")
# Locate ConfigEstadualType class descriptor
ces = data.find(b"ConfigEstadualType")
if ces >= 0:
    # Back up to find TC_CLASSDESC
    class_start = ces - 4  # "00 16" + TC_CLASSDESC(0x72)
    # After class name: serialVersionUID(8) + flags(1) + fieldCount(2)
    after_name = ces + len("ConfigEstadualType")
    uid = data[after_name:after_name+8]
    flags = data[after_name+8]
    nfields = struct.unpack(">H", data[after_name+9:after_name+11])[0]
    print(f"  serialVersionUID: {uid.hex()}")
    print(f"  flags: {flags}")
    print(f"  field count: {nfields}")
    
    pos = after_name + 11
    for i in range(nfields):
        tc = chr(data[pos])
        pos += 1
        namelen = struct.unpack(">H", data[pos:pos+2])[0]
        pos += 2
        name = data[pos:pos+namelen].decode("ascii")
        pos += namelen
        
        if tc in "BCSIJFDZ":
            print(f"  Field {i}: type={tc} name={name}")
        elif tc in "[L":
            # Object or array: read className
            # TC_STRING (0x74) + len(2) + string
            if data[pos] == 0x74:
                cnlen = struct.unpack(">H", data[pos+1:pos+3])[0]
                cname = data[pos+3:pos+3+cnlen].decode("ascii")
                pos += 3 + cnlen
                print(f"  Field {i}: type={tc} name={name} className={cname}")
            elif data[pos] == 0x71:
                # TC_REFERENCE
                handle = struct.unpack(">I", data[pos+1:pos+5])[0]
                pos += 5
                print(f"  Field {i}: type={tc} name={name} classRef=0x{handle:08X}")
    
    # After fields: TC_ENDBLOCKDATA(0x78) + TC_NULL(0x70) = "xp"
    print(f"\n  After fields at 0x{pos:03X}: {data[pos]:02X} {data[pos+1]:02X}")
    if data[pos] == 0x78 and data[pos+1] == 0x70:
        pos += 2
        print(f"  Instance data starts at 0x{pos:03X}")
        
        # Parse 4 objects
        for obj in range(4):
            print(f"\n  --- Object {obj+1} at 0x{pos:03X} ---")
            for fname in ["desempate", "divisao", "formula", "id", "nRebaixados"]:
                if fname == "id" and nfields < 5:
                    continue
                val = struct.unpack(">i", data[pos:pos+4])[0]
                print(f"    {fname} = {val}")
                pos += 4
            
            # finaisIdaVolta array
            if data[pos] == 0x75:  # TC_ARRAY
                pos += 1
                if data[pos] == 0x72:  # TC_CLASSDESC
                    # Skip [I class desc
                    nl = struct.unpack(">H", data[pos+1:pos+3])[0]
                    pos += 3 + nl + 8 + 1 + 2 + 1 + 1
                elif data[pos] == 0x71:
                    pos += 5
                alen = struct.unpack(">i", data[pos:pos+4])[0]
                pos += 4
                arr = [struct.unpack(">i", data[pos+j*4:pos+j*4+4])[0] for j in range(alen)]
                pos += alen * 4
                print(f"    finaisIdaVolta = {arr}")
            elif data[pos] == 0x70:  # TC_NULL
                pos += 1
                print(f"    finaisIdaVolta = null")
            
            # Next object marker
            if obj < 3 and pos < len(data) - 1:
                if data[pos] == 0x73:  # TC_OBJECT
                    pos += 1
                    if data[pos] == 0x71:  # TC_REFERENCE
                        pos += 5
                    print(f"    (next object at 0x{pos:03X})")
