"""Fresh PostgreSQL migration verification; creates only a disposable local DB."""
import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from app.core.config import settings


def main():
    url = make_url(settings.SQLALCHEMY_DATABASE_URI)
    if settings.ENVIRONMENT != 'test' or url.host not in {'localhost', '127.0.0.1'} or not url.database.startswith('regulaai_verify_'):
        raise SystemExit('Only a local disposable verification database is accepted')
    name = 'regulaai_verify_migration_' + uuid4().hex[:12]
    subprocess.run(['docker', 'compose', 'exec', '-T', 'postgres', 'createdb', '-U', 'postgres', name], cwd='..', check=True)
    env = dict(os.environ)
    env['SQLALCHEMY_DATABASE_URI'] = url.set(database=name).render_as_string(hide_password=False)
    outputs = {}
    for command in ['upgrade head', 'current', 'check']:
        result = subprocess.run([sys.executable, '-m', 'alembic', *command.split()], env=env, text=True, capture_output=True, check=True)
        outputs[command] = result.stdout + result.stderr
    engine = create_engine(url.set(database=name))
    with engine.connect() as db:
        head = db.execute(text('SELECT version_num FROM alembic_version')).scalar()
        vector = db.execute(text("SELECT extversion FROM pg_extension WHERE extname='vector'")).scalar()
    engine.dispose()
    assert head == 'f5a6b7c8d9e0' and vector
    report = {'status': 'passed', 'database': name, 'head': head, 'pgvector_version': vector, 'commands': outputs}
    output = Path('../output/migrations'); output.mkdir(parents=True, exist_ok=True)
    (output/'fresh-migration.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['status', 'head', 'pgvector_version']}))


if __name__ == '__main__':
    main()
