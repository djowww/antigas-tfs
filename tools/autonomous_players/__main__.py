"""Explicit commands only: importing or --help never opens game connections."""
import argparse
import asyncio
import json
import time
from pathlib import Path
from .health import atomic_json,Collector,collect_once


def main():
    parser = argparse.ArgumentParser(description='Persistent normal-player population, maximum 20')
    sub = parser.add_subparsers(dest='command',required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--manifest',type=Path,required=True)
    prepare.add_argument('--identity',required=True)
    prepare.add_argument('--count',type=int,default=20)
    prepare.add_argument('--public-authorized',action='store_true')
    provision = sub.add_parser('provision')
    provision.add_argument('--manifest',type=Path,required=True)
    provision.add_argument('--identity',required=True)
    provision.add_argument('--database',required=True)
    provision.add_argument('--backup',type=Path,required=True)
    backup=sub.add_parser('backup')
    backup.add_argument('--database',required=True)
    backup.add_argument('--path',type=Path,required=True)
    backup.add_argument('--identity',required=True)
    for name in ('run','guardian','status','pause','resume','stop','verify'):
        p = sub.add_parser(name)
        p.add_argument('--config',type=Path,required=True)
    args = parser.parse_args()
    if args.command=='backup':
        from .provision import backup_database
        print(json.dumps(backup_database(args.database,args.path,args.identity)))
        return
    if args.command == 'prepare':
        from .provision import prepare_manifest
        m = prepare_manifest(args.manifest,args.identity,args.count,args.public_authorized)
        print(json.dumps(dict(prepared=len(m['players']),provisioned=m['provisioned'])))
        return
    if args.command == 'provision':
        from .provision import provision as apply
        m = apply(args.manifest,args.identity,args.database,args.backup)
        print(json.dumps(dict(provisioned=len(m['players']))))
        return
    config = json.loads(args.config.read_text())
    if args.command == 'guardian':
        manifest = json.loads(Path(config['manifest']).read_text())
        if manifest['identity'] != config['identity'] or not manifest.get('provisioned'):
            raise ValueError('guardian manifest mismatch')
        collector = Collector(config['service'],config['database'],[p['player_id'] for p in manifest['players']],
                              config['status_port'],config.get('mysql_defaults'))
        while True:
            started = time.monotonic()
            result = collect_once(collector)
            atomic_json(config['health_file'],result)
            time.sleep(max(.1,5-(time.monotonic()-started)))
    elif args.command == 'run':
        from .app import run
        asyncio.run(run(config))
    elif args.command == 'status':
        print((Path(config['state_dir'])/'status.json').read_text())
    elif args.command in ('pause','resume','stop'):
        atomic_json(Path(config['state_dir'])/'control.json',dict(action=args.command,at=time.time()),0o600)
        print(args.command)
    elif args.command == 'verify':
        from .app import validate_config
        from .definitions import load_items
        validate_config(config)
        manifest = json.loads(Path(config['manifest']).read_text())
        if manifest['identity'] != config['identity'] or len(manifest['players']) > 20:
            raise ValueError('manifest mismatch')
        print(json.dumps(dict(configuration_valid=True,items=len(load_items(Path(config['items']))),
                              provisioned=manifest['provisioned'],network_tested=False)))


if __name__ == '__main__':
    main()
