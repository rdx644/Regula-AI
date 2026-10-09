"""Encrypted backup/restore drill restricted to disposable local verification DBs."""
import argparse
import hashlib
import io
import json
import subprocess
import time
import uuid
import zipfile
from pathlib import Path
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.db import base
from app.db.base_class import Base
from app.services.storage import PrivateLocalStorage


def command(*args, data=None):
    result = subprocess.run(['docker', 'compose', 'exec', '-T', 'postgres', *args], cwd=Path.cwd().parent,
        input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return result.stdout


def fingerprint(engine):
    with engine.connect() as db:
        return {table.name: dict(db.execute(text(f'SELECT count(*) AS rows, md5(coalesce(json_agg(to_json(t) ORDER BY id)::text, \'[]\')) AS digest FROM "{table.name}" t')).mappings().one())
            for table in Base.metadata.sorted_tables}


def main():
    url = make_url(settings.SQLALCHEMY_DATABASE_URI)
    if settings.ENVIRONMENT != 'test' or url.host not in {'localhost', '127.0.0.1'} or not url.database.startswith('regulaai_verify_'):
        raise SystemExit('Restore drill only accepts a local disposable regulaai_verify_* database in ENVIRONMENT=test')
    source_engine = create_engine(url)
    original = fingerprint(source_engine)
    output = Path('../output/recovery')
    output.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex[:12]
    backup = command('pg_dump', '-U', 'postgres', '-Fc', url.database)
    storage = PrivateLocalStorage()
    with source_engine.connect() as db:
        keys = set()
        for table in ['regulatory_versions', 'policies', 'evidence']:
            keys.update(row[0] for row in db.execute(text(f'SELECT file_reference FROM {table} WHERE file_reference IS NOT NULL')))
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as zipped:
        zipped.writestr('database.dump', backup)
        for key in keys:
            zipped.writestr('objects/'+key, storage.read(key))
    key_path = output / f'{run_id}.recovery-key'
    key_path.write_bytes(Fernet.generate_key())
    cipher = Fernet(key_path.read_bytes())
    encrypted = output / f'{run_id}.backup.enc'
    encrypted.write_bytes(cipher.encrypt(archive.getvalue()))
    restore_name = 'regulaai_restore_' + run_id
    command('createdb', '-U', 'postgres', restore_name)
    started = time.monotonic()
    objects = PrivateLocalStorage(output / ('objects-'+run_id))
    with zipfile.ZipFile(io.BytesIO(cipher.decrypt(encrypted.read_bytes()))) as zipped:
        command('pg_restore', '-U', 'postgres', '--exit-on-error', '-d', restore_name, data=zipped.read('database.dump'))
        for key in keys:
            target = objects._path_for(key)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(zipped.read('objects/'+key))
            assert objects.read(key) == storage.read(key)
    restored_engine = create_engine(url.set(database=restore_name))
    restored = fingerprint(restored_engine)
    assert restored == original, 'Restored data fingerprint differs'
    report = {'status': 'passed', 'scope': 'disposable local PostgreSQL plus referenced local synthetic source objects',
        'source_database': url.database, 'restored_database': restore_name, 'tables': original,
        'objects_restored': len(keys), 'recovery_seconds': round(time.monotonic()-started, 3),
        'data_loss_window': 'snapshot; no concurrent source writes during this drill',
        'archive_sha256': hashlib.sha256(encrypted.read_bytes()).hexdigest(),
        'limitations': ['This does not verify managed-cloud backup scheduling, KMS, IAM, retention, or staging RTO/RPO.',
            'Local recovery key is excluded from Git; production requires a separate secret manager.']}
    (output/'restore-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({key: report[key] for key in ['status', 'objects_restored', 'recovery_seconds', 'restored_database']}))
    source_engine.dispose(); restored_engine.dispose()


if __name__ == '__main__':
    main()
