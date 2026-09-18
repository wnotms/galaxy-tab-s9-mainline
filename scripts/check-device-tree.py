#!/usr/bin/env python3
"""Check S9 identities and critical snapshot-derived values in the final DTB."""
import json
import runpy
import struct
import sys
from pathlib import Path

parse = runpy.run_path(str(Path(__file__).with_name("analyze-device-snapshot.py")))["parse_fdt"]
nodes = parse(Path(sys.argv[1]).read_bytes())
def cells(value):
    return struct.unpack(">" + "I" * (len(value) // 4), value)
def require(ok, message):
    if not ok:
        sys.exit(message)
require(b"samsung,gts9wifi\0" in nodes["/"]["compatible"], "Wrong board compatible")
require(cells(nodes["/"]["qcom,board-id"]) == (0x10008, 4), "Wrong board ID")
require(cells(nodes['/clocks/sleep-clk']['clock-frequency']) == (32000,), 'Wrong S9 sleep clock')
require(cells(nodes['/clocks/xo-board']['clock-frequency']) == (76800000,), 'Wrong S9 XO clock')
repeaters = [p for p in nodes.values() if p.get("compatible") == b"nxp,ptn3222\0"]
require(len(repeaters) == 1, "Expected exactly one S9 repeater")
require(cells(repeaters[0]["qcom,param-override-seq"]) == (0x20,6,0x21,7,0x63,8,3,9,1,10), "Wrong S9 repeater sequence")
require(cells(nodes["/reserved-memory/uh-guest@b1000000"]["reg"]) == (0,0xb1000000,0,0x3600000), "Wrong S9 UH carveout")
require(cells(nodes["/reserved-memory/sec-log@880200000"]["reg"]) == (8,0x80200000,0,0x200000), "Wrong sec_log carveout")
require(cells(nodes["/reserved-memory/adspslpi@9ea00000"]["reg"]) == (0,0x9ea00000,0,0x59b4000), "Wrong ADSP carveout")
require(nodes["/soc@0/usb@a600000"]["dr_mode"] == b"peripheral\0", "USB is not peripheral")
require(not any(b"amsa46as02" in p.get("compatible", b"") or b"goodix" in p.get("compatible", b"") for p in nodes.values()), "Ultra-only display/touch leaked into S9 DTB")
ranges = []
for path, properties in nodes.items():
    if path.startswith('/reserved-memory/') and 'reg' in properties:
        a,b,c,d = cells(properties['reg'])
        if properties.get('status') != b'disabled\0':
            ranges.append(((a<<32)+b, (c<<32)+d, path))
ranges.sort()
for left, right in zip(ranges, ranges[1:]):
    require(left[0]+left[1] <= right[0], 'Overlapping reserved memory: '+left[2]+' / '+right[2])
stock_path = Path(__file__).resolve().parent.parent/'device/stock-hardware.json'
covered = 0
for path, properties in json.loads(stock_path.read_text())['nodes'].items():
    if not path.startswith('/reserved-memory/') or 'reg' not in properties or properties.get('status') == ['disabled']:
        continue
    a,b,c,d = properties['reg']; start=(a<<32)+b; size=(c<<32)+d
    if not size:
        continue
    require(any(begin<=start and begin+length>=start+size for begin,length,_ in ranges), 'Unprotected stock carveout: '+path)
    covered += 1
print(f"Verified S9 identity, USB parameters, {covered} stock carveouts, no reservation overlap and no Ultra panel/touch")
