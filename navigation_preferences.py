"""Validated, owner-scoped sidebar shortcuts and collapsed sections."""
import json
from pathlib import Path

CATALOG = json.loads((Path(__file__).parent/'web/navigation-catalog.json').read_text())
DEFAULT_PINS = ['Contacts', 'Companies', 'Deals', 'Tickets', 'Tasks', 'Inbox', 'Calendar', 'Data Quality']
FIXED = {'Dashboards', 'Activity Feed', 'Configuration'}


def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS navigation_preferences (owner TEXT PRIMARY KEY, body TEXT NOT NULL)')


def catalog(settings):
    result = {group: list(items) for group, items in CATALOG.items()}
    custom = ['record:'+t['id'] for t in settings['types'] if t['id'] not in ('contacts','companies','deals','tasks','tickets')]
    if custom:
        result['Custom records'] = custom
    return result


def normalize(data, groups, strict=True):
    if not isinstance(data, dict) or set(data) != {'pins','collapsed'}:
        raise ValueError('Invalid navigation preferences.')
    allowed = {item for items in groups.values() for item in items} - FIXED
    for key, choices in [('pins', allowed), ('collapsed', set(groups))]:
        values = data[key]
        if (not isinstance(values, list) or len(values)>150 or any(not isinstance(v,str) for v in values)
                or len(set(values)) != len(values)):
            raise ValueError('Use unique, valid sidebar choices.')
        if strict and any(v not in choices for v in values):
            raise ValueError('Choose available sidebar items and sections.')
    return {'pins':[p for p in data['pins'] if p in allowed],
            'collapsed':[g for g in data['collapsed'] if g in groups]}


def load(db, owner, settings):
    groups = catalog(settings)
    row = db.execute('SELECT body FROM navigation_preferences WHERE owner=?', (owner,)).fetchone()
    defaults = {'pins':DEFAULT_PINS+groups.get('Custom records',[]), 'collapsed':[]}
    return {'catalog':groups,'preferences':normalize(json.loads(row['body']) if row else defaults, groups, strict=False)}


def save(db, owner, settings, data):
    validated = normalize(data, catalog(settings))
    db.execute('INSERT INTO navigation_preferences VALUES(?,?) ON CONFLICT(owner) DO UPDATE SET body=excluded.body',
               (owner,json.dumps(validated)))
    return validated
