"""Owner-scoped dashboard layout preferences, shared by desktop and web."""
import copy
import json

WIDGETS = {'daily': ['tasks', 'agenda'], 'sales': ['pipeline', 'closing', 'stalled'],
           'relationships': ['followups', 'conversations']}
DEFAULTS = {'default_tab': 'daily', 'density': 'comfortable', 'task_scope': 'mine',
            'meeting_days': 7, 'inactive_days': 14, 'side_panel': True, 'widgets': WIDGETS}


def initialize(db):
    db.execute('CREATE TABLE IF NOT EXISTS dashboard_preferences (owner TEXT PRIMARY KEY, body TEXT NOT NULL)')


def load(db, owner):
    row = db.execute('SELECT body FROM dashboard_preferences WHERE owner=?', (owner,)).fetchone()
    return json.loads(row['body']) if row else copy.deepcopy(DEFAULTS)


def save(db, owner, data):
    if not isinstance(data, dict) or set(data) != set(DEFAULTS):
        raise ValueError('Invalid dashboard preferences.')
    if (not isinstance(data['default_tab'], str) or data['default_tab'] not in WIDGETS or data['density'] not in ('comfortable', 'compact')
            or data['task_scope'] not in ('mine', 'all') or type(data['side_panel']) is not bool
            or type(data['meeting_days']) is not int or data['meeting_days'] not in (1, 7)
            or type(data['inactive_days']) is not int or data['inactive_days'] not in (7, 14, 30)):
        raise ValueError('Choose valid dashboard options.')
    widgets = data['widgets']
    if not isinstance(widgets, dict) or set(widgets) != set(WIDGETS):
        raise ValueError('Invalid dashboard cards.')
    for tab, allowed in WIDGETS.items():
        values = widgets[tab]
        if (not isinstance(values, list) or any(not isinstance(v, str) or v not in allowed for v in values)
                or len(set(values)) != len(values)):
            raise ValueError('Choose each dashboard card at most once.')
    db.execute('INSERT INTO dashboard_preferences VALUES(?,?) ON CONFLICT(owner) DO UPDATE SET body=excluded.body',
               (owner, json.dumps(data)))
    return copy.deepcopy(data)
