"""Local non-secret SSO configuration. Environment settings take precedence."""
import json
import os
from pathlib import Path
from urllib.parse import urlparse

CONFIG = Path(os.getenv('SPROCKET_SSO_CONFIG', str(Path(__file__).parent / 'data' / 'sso.json')))
FIELDS = {'issuer':'OIDC_ISSUER','client_id':'OIDC_CLIENT_ID','origin':'SPROCKET_ORIGIN','subjects':'OIDC_ALLOWED_SUBJECTS'}


def read():
    return json.loads(CONFIG.read_text()) if CONFIG.exists() else {}


def effective():
    saved = read()
    return {k:os.environ.get(env, saved.get(k, '')) for k,env in FIELDS.items()}


def validate(data):
    if not isinstance(data, dict) or set(data) != set(FIELDS) or not all(isinstance(v,str) for v in data.values()):
        raise ValueError('Provide issuer, client ID, origin and allowed subjects.')
    data = {k:v.strip() for k,v in data.items()}
    issuer = urlparse(data['issuer'])
    if issuer.scheme != 'https' or not issuer.hostname or issuer.username or issuer.query or issuer.fragment:
        raise ValueError('Issuer must be an HTTPS URL without credentials, query or fragment.')
    origin = urlparse(data['origin'])
    if not origin.hostname or origin.username or origin.path or origin.query or origin.fragment or (origin.scheme != 'https' and not (origin.scheme == 'http' and origin.hostname in ('127.0.0.1','localhost'))):
        raise ValueError('Use an HTTPS origin, or HTTP localhost for development, without a trailing slash.')
    if not data['client_id'] or not any(x.strip() for x in data['subjects'].split(',')):
        raise ValueError('Client ID and at least one allowed subject are required.')
    return data


def save(data):
    data = validate(data)
    CONFIG.parent.mkdir(parents=True,exist_ok=True)
    temp = CONFIG.with_suffix('.tmp')
    with open(temp,'w',encoding='utf-8') as f:
        os.chmod(temp,0o600)
        json.dump(data,f,indent=2)
    temp.replace(CONFIG)
    return data
