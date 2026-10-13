"""Database version guard and ordered web migrations; schema 1 is the beta baseline."""
SCHEMA_VERSION=1

def migrate(connect):
    with connect() as db:
        db.execute('CREATE TABLE IF NOT EXISTS web_schema_version(id INTEGER PRIMARY KEY CHECK(id=1),version INTEGER NOT NULL)')
        db.execute('LOCK TABLE web_schema_version IN EXCLUSIVE MODE')
        row=db.execute('SELECT version FROM web_schema_version WHERE id=1').fetchone()
        version=row[0] if row else 0
        if version>SCHEMA_VERSION:raise ValueError('The database requires a newer SpRocket release.')
        # Migration 1 establishes a baseline for the existing additive beta schema.
        if version<1:db.execute('INSERT INTO web_schema_version VALUES (1,1) ON CONFLICT(id) DO UPDATE SET version=1')
