#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Unpack owner's firmware/vendor images locally; never access the tablet.

Optional: requires amd64 Linux for the pinned Ubuntu unpacking tools. All
extracted proprietary files and inventories remain under ignored artifacts/.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import urllib.request

ROOT=Path(__file__).resolve().parent.parent
def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda:stream.read(4*1024*1024),b''):
            digest.update(data)
    return digest.hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot',type=Path)
    parser.add_argument('--vendor',action='store_true',help='Also unpack vendor EROFS, including display configuration and touch firmware')
    args=parser.parse_args()
    if platform.machine()!='x86_64':
        raise SystemExit('Pinned unpacking tools target amd64; use native mtools/erofs-utils on other hosts')
    manifest=json.loads((args.snapshot/'manifest.json').read_text())
    if manifest['model']!='SM-X710' or manifest.get('errors'):
        raise SystemExit('Expected completed SM-X710 snapshot')
    files={f['file']:f for f in manifest['files']}
    wanted=['partitions/apnhlos.img']+(['logical/vendor.img'] if args.vendor else [])
    for name in wanted:
        if sha(args.snapshot/name)!=files[name]['sha256']:
            raise SystemExit('Snapshot SHA256 mismatch: '+name)
    pins=json.loads((ROOT/'device/host-tools.json').read_text())
    tools=ROOT/'work/unpack-tools'
    for name in ['mtools']+(['erofs-utils', 'libdeflate0'] if args.vendor else []):
        pin=pins[name]; archive=ROOT/'work/downloads'/pin['filename']
        archive.parent.mkdir(parents=True,exist_ok=True)
        if not archive.exists():
            urllib.request.urlretrieve(pin['url'],archive)
        if sha(archive)!=pin['sha256']:
            raise SystemExit('Unpacking tool SHA256 mismatch: '+name)
        tools.mkdir(parents=True,exist_ok=True)
        subprocess.run(['dpkg-deb','-x',str(archive),str(tools)],check=True)
    out=ROOT/'artifacts/stock-files'
    out.mkdir(parents=True,exist_ok=True)
    firmware=out/'apnhlos'
    if firmware.exists():
        raise SystemExit('Output already exists; move artifacts/stock-files/apnhlos aside before another import')
    firmware.mkdir()
    subprocess.run([str(tools/'usr/bin/mcopy'),'-i',str(args.snapshot/'partitions/apnhlos.img'),'-s','::/image',str(firmware)],check=True)
    if args.vendor:
        vendor=out/'vendor'
        if vendor.exists():
            raise SystemExit('Vendor output already exists; move it aside before another import')
        env=os.environ.copy()
        env['LD_LIBRARY_PATH']=str(tools/'usr/lib/x86_64-linux-gnu')+(':'+env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else '')
        subprocess.run([str(tools/'usr/bin/fsck.erofs'),'--extract='+str(vendor),str(args.snapshot/'logical/vendor.img')],check=True,env=env)
    inventory=[]
    for path in sorted(out.rglob('*')):
        if path.is_file() and not path.is_symlink() and path.name!='manifest.json':
            inventory.append({'file':str(path.relative_to(out)),'size':path.stat().st_size,'sha256':sha(path)})
    (out/'manifest.json').write_text(json.dumps({'model':'SM-X710','source_images':{name:files[name]['sha256'] for name in wanted},'redistributable':False,'files':inventory},indent=2)+'\n')
    # Commit only paths/hashes of relevant source assets, never their contents.
    assets=[item for item in inventory if
            item['file'].startswith(('apnhlos/image/adsp.', 'apnhlos/image/adsp_dtb.',
                                     'apnhlos/image/cdsp.', 'apnhlos/image/cdsp_dtb.')) or
            item['file'] in ('vendor/firmware/GTS9_ANA38407_AMSA10FA01.dat',
                             'vendor/firmware/tsp_stm/fts1ba90a_gts9.bin',
                             'vendor/firmware/wez01_gts9.bin',
                             'vendor/etc/display/qdcm_calib_data_GTS9_ANA38407_AMSA10FA01.json')]
    (ROOT/'device/stock-assets.json').write_text(json.dumps({'model':'SM-X710',
        'local_root':'artifacts/stock-files', 'source_images':{name:files[name]['sha256'] for name in wanted},
        'files':assets},indent=2)+'\n')
    print(f'Unpacked and hashed {len(inventory)} local files under artifacts/stock-files/')
if __name__=='__main__':
    main()
