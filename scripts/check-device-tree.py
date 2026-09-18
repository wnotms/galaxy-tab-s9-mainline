#!/usr/bin/env python3
"""Check S9 identities and critical snapshot-derived values in the final DTB."""
import argparse
import hashlib
import json
import runpy
import struct
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("dtb", type=Path)
parser.add_argument("--abl-updated", action="store_true", help="Require the three ABL-added reservations instead of their absence")
args = parser.parse_args()
parse = runpy.run_path(str(Path(__file__).with_name("analyze-device-snapshot.py")))["parse_fdt"]
nodes = parse(args.dtb.read_bytes())
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
abl_reservations = {
    "kaslr_region": (0,0xb01ff000,0,0x1000),
    "uh_heap_region": (0,0xb0200000,0,0x40000),
    "uh_guest_region": (0,0xb1000000,0,0x3600000),
}
# An exact historical DTB is permitted for the controlled firmware-layout trial.
# This never permits arbitrary legacy trees or removes protected-range checks.
baseline = json.loads((Path(__file__).resolve().parent.parent /
                       'device/firmware-dtb-baseline.json').read_text())
legacy_paths = ['/reserved-memory/' + name for name in baseline['legacy_reservations']]
legacy = any(path in nodes for path in legacy_paths)
if legacy:
    require(not args.abl_updated, 'Legacy baseline: ABL duplicate reservations require separate runtime review')
    require(hashlib.sha256(args.dtb.read_bytes()).hexdigest() == baseline['sha256'],
            'Legacy reservation layout requires the exact first boot-confirmed DTB')
    for name, expected in baseline['legacy_reservations'].items():
        path = '/reserved-memory/' + name
        require(path in nodes and cells(nodes[path]['reg']) == tuple(expected),
                'Wrong pinned legacy reservation: ' + name)
        require('no-map' in nodes[path], 'Pinned protected legacy range must remain no-map: ' + name)
for name, expected in abl_reservations.items():
    path = "/reserved-memory/" + name
    if args.abl_updated:
        require(path in nodes, "Missing ABL reservation name: " + name)
        require(cells(nodes[path]["reg"]) == expected, "Wrong ABL reservation: " + name)
    else:
        require(path not in nodes, "ABL must add this reservation itself: " + name)
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
if not args.abl_updated and not legacy:
    for name, (a,b,c,d) in abl_reservations.items():
        start=(a<<32)+b; length=(c<<32)+d
        require(not any(begin < start+length and start < begin+size for begin,size,_ in ranges), "Input DTB already reserves ABL range: " + name)
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
if legacy:
    print('Pinned first boot-confirmed firmware DTB: legacy ranges retained no-map; ABL may add exact duplicates')
print(f"Verified S9 identity, USB parameters, {covered} stock carveouts, no reservation overlap and no Ultra panel/touch; ABL reservations {'present' if args.abl_updated else 'legacy baseline, firmware duplicates expected' if legacy else 'deferred to bootloader'}")
