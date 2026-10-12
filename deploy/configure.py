"""Generate private deployment settings; never replace an existing secrets file."""
import argparse,base64,os,re,secrets
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--domain',required=True);p.add_argument('--output',default='deploy/.env');args=p.parse_args()
if not re.fullmatch(r'(?=.{1,253}$)(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]{2,63}',args.domain):p.error('Use your CRM hostname without https:// or a path.')
values=dict(SPROCKET_DOMAIN=args.domain.lower(),POSTGRES_PASSWORD=secrets.token_hex(32),SPROCKET_SETUP_TOKEN=secrets.token_urlsafe(32),MAIL_TOKEN_KEY=base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),GOOGLE_MAIL_CLIENT_ID='',GOOGLE_MAIL_CLIENT_SECRET='')
path=Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'w') as file:file.write('\n'.join(k+'='+v for k,v in values.items())+'\n')
print('Private deployment settings created. Use the setup code in that file at https://'+args.domain+'/setup. Keep the file for upgrades and recovery.')
