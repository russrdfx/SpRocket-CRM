#!/usr/bin/env python3
"""Host-side Docker Compose backup with a full restore into a new disposable database."""
import argparse,hashlib,json,os,subprocess,uuid
from datetime import datetime,timezone
from pathlib import Path

def backup(root,folder,run=subprocess.run):
    root=Path(root).resolve();folder=Path(folder).resolve();folder.mkdir(mode=0o700,parents=True,exist_ok=True)
    prefix=['docker','compose','--env-file','deploy/.env','exec','-T','db']
    def command(args,data=None):
        result=run(prefix+args,cwd=root,input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if result.returncode:raise RuntimeError('Backup or isolated restore failed. Check Docker/database access and available disk space. No credentials were logged.')
        return result.stdout
    stamp=datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:8]
    archive=folder/('SpRocket-web-'+stamp+'.dump');pending=archive.with_suffix('.incomplete')
    payload=command(['pg_dump','-U','sprocket','-d','sprocket','--format=custom','--no-owner','--no-acl'])
    with pending.open('xb') as file:
        os.chmod(pending,0o600);file.write(payload)
    command(['pg_restore','--list'],payload)
    verify='sprocket_verify_'+uuid.uuid4().hex;created=False
    try:
        command(['createdb','-U','sprocket',verify]);created=True
        command(['pg_restore','-U','sprocket','--dbname',verify,'--no-owner','--no-acl','--exit-on-error'],payload)
        counts={}
        for table in ('settings','records','activities','web_users','mail_accounts','calendar_accounts'):
            counts[table]=int(command(['psql','-U','sprocket','-d',verify,'-At','-c','SELECT COUNT(*) FROM '+table]).strip())
        if counts['settings']!=1:raise RuntimeError('Restored workspace configuration is missing.')
    finally:
        if created:command(['dropdb','-U','sprocket',verify])
    pending.rename(archive)
    receipt=dict(completed=datetime.now(timezone.utc).isoformat(),restore_verified=True,backup_file=archive.name,sha256=hashlib.sha256(payload).hexdigest(),bytes=len(payload),restored_counts=counts)
    receipt_file=folder/'latest-verified-backup.json';temporary=folder/('receipt-'+uuid.uuid4().hex+'.tmp')
    with temporary.open('x') as file:
        os.chmod(temporary,0o600);json.dump(receipt,file,indent=2)
    temporary.replace(receipt_file)
    return receipt

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',default='.');parser.add_argument('--folder',default='backups');args=parser.parse_args()
    try:
        result=backup(args.root,args.folder);print('Backup and isolated restore verified: '+result['backup_file'])
    except Exception as error:raise SystemExit(str(error))
if __name__=='__main__':main()
