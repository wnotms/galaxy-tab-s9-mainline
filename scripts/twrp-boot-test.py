#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check, stage and test only the four SM-X710 boot partitions through TWRP.

Default is a read-only preflight. --flash writes the verified bundle;
--restore restores the matching owner snapshot. Recovery/vbmeta are checked
but never written. All operations are recorded in the ignored report folder.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import shlex
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent
PARTITIONS = ("boot", "init_boot", "vendor_boot", "dtbo")
def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda:stream.read(4*1024*1024),b''):h.update(block)
    return h.hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adb',required=True,type=Path)
    p.add_argument('--snapshot',required=True,type=Path)
    p.add_argument('--bundle',type=Path,default=ROOT/'artifacts/boot-bundle')
    p.add_argument('--report',required=True,type=Path)
    action=p.add_mutually_exclusive_group()
    action.add_argument('--stage',action='store_true')
    action.add_argument('--flash',action='store_true')
    action.add_argument('--restore',action='store_true')
    p.add_argument('--reboot',action='store_true')
    args=p.parse_args()
    if args.reboot and not (args.flash or args.restore):p.error('--reboot requires --flash or --restore')
    args.report.mkdir(parents=True,exist_ok=True,mode=0o700)
    profile=json.loads((ROOT/'device/boot-profile.json').read_text())
    snapshot=json.loads((args.snapshot/'manifest.json').read_text())
    bundle=json.loads((args.bundle/'manifest.json').read_text())
    report={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'action':'restore' if args.restore else 'flash' if args.flash else 'stage' if args.stage else 'preflight',
            'written_partitions':[], 'phase':'preflight','events':[]}
    def save():
        (args.report/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    adb=[str(args.adb),'-s',snapshot['serial']]
    def run(arguments,binary=False):
        result=subprocess.run(adb+arguments,capture_output=True,timeout=180)
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace')+result.stdout.decode(errors='replace'))
        return result.stdout if binary else result.stdout.decode(errors='replace').strip()
    def shell(command):return run(['shell',command])
    def device_hash(path):return shell('sha256sum '+shlex.quote(path)).split()[0]
    try:
        if snapshot['model']!='SM-X710' or profile['model']!='SM-X710' or bundle['model']!='SM-X710':
            raise RuntimeError('Expected SM-X710 sources')
        identity={key:shell('getprop '+key) for key in ('ro.boot.em.model','ro.bootloader','ro.boot.revision','ro.boot.vbmeta.device_state')}
        report['identity']=identity
        if identity['ro.boot.em.model']!='SM-X710' or identity['ro.bootloader']!=profile['bootloader']:
            raise RuntimeError('Connected model/bootloader does not match captured profile')
        if identity['ro.boot.vbmeta.device_state']!='unlocked':raise RuntimeError('Bootloader is not unlocked')
        revision=int(identity['ro.boot.revision'],0)
        if not profile['supported_revision_range'][0]<=revision<=profile['supported_revision_range'][1]:
            raise RuntimeError('Unsupported board revision')
        shell('pidof recovery')
        if 'uid=0(' not in shell('id'):raise RuntimeError('TWRP root shell required')
        entries={f['file']:f for f in snapshot['files']}
        current={}
        for name in PARTITIONS+('vbmeta','recovery'):
            path='/dev/block/by-name/'+name
            size=int(shell('blockdev --getsize64 '+path))
            original=entries['partitions/'+name+'.img']
            if size!=original['size']:raise RuntimeError('Partition size changed: '+name)
            digest=device_hash(path);current[name]={'size':size,'sha256':digest}
            expected={original['sha256']}
            if args.restore and name in PARTITIONS:expected.add(bundle['files'][name+'.img']['sha256'])
            if digest not in expected:raise RuntimeError('Current partition differs from expected baseline: '+name)
            if name in PARTITIONS and sha(args.snapshot/'partitions'/(name+'.img'))!=original['sha256']:
                raise RuntimeError('Restore backup hash mismatch: '+name)
        report['before']=current
        raw=run(['exec-out','dd if=/dev/block/by-name/vbmeta bs=1 skip=120 count=4 2>/dev/null'],binary=True)
        flags=struct.unpack('>I',raw)[0];report['vbmeta_flags']=flags
        if not flags&2:raise RuntimeError('AVB verification is enabled')
        if not args.restore:
            subprocess.run([sys.executable,str(ROOT/'scripts/verify-boot-bundle.py'),str(args.bundle)],check=True)
        save()
        if not (args.stage or args.flash or args.restore):
            print('PASS: TWRP device, revision, partition sizes, current hashes, AVB and all four restore backups')
            return
        remote='/tmp/gts9wifi-boot-test'
        shell('mkdir -p '+remote)
        selected=args.snapshot/'partitions' if args.restore else args.bundle
        planned={}
        for name in PARTITIONS:
            source=(selected/(name+'.img')).resolve()
            expected=entries['partitions/'+name+'.img']['sha256'] if args.restore else bundle['files'][name+'.img']['sha256']
            if sha(source)!=expected:raise RuntimeError('Source image hash changed: '+name)
            host=str(source)
            if args.adb.suffix.lower()=='.exe':host=subprocess.check_output(['wslpath','-w',str(source)],text=True).strip()
            run(['push',host,remote+'/'+name+'.img'])
            if device_hash(remote+'/'+name+'.img')!=expected:raise RuntimeError('Staged image hash mismatch: '+name)
            planned[name]=expected
            report['events'].append('staged and verified '+name);save()
        report['phase']='staged';report['planned']=planned;save()
        if args.stage:
            print('PASS: all four images staged and hash-verified in TWRP RAM')
            return
        for name in PARTITIONS:
            shell('dd if='+remote+'/'+name+'.img of=/dev/block/by-name/'+name+' bs=1048576 && sync')
            report['written_partitions'].append(name);save()
            actual=device_hash('/dev/block/by-name/'+name)
            if actual!=planned[name]:raise RuntimeError('Partition readback mismatch: '+name)
            report['events'].append('written and readback verified '+name);save()
            print('Written and verified: '+name,flush=True)
        for name in ('vbmeta','recovery'):
            if device_hash('/dev/block/by-name/'+name)!=current[name]['sha256']:
                raise RuntimeError('Untouched partition changed: '+name)
        report['phase']='restored' if args.restore else 'flashed';save()
        print('PASS: four partition readbacks match; vbmeta and recovery unchanged',flush=True)
        if args.reboot:
            report['phase']='reboot_requested';save()
            run(['reboot'])
            print('Normal boot requested; inspect USB enumeration and persistent log',flush=True)
    except Exception as exc:
        report['error']=str(exc);save()
        raise
if __name__=='__main__':main()
