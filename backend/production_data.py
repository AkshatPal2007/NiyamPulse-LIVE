"""One-way, backed-up data migration: official evidence in; demo identities out.

The old database stays intact as an archive. An initialized production target is
never overwritten, including when this command is run a second time.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sqlite3

from backend.exam_store import ExamStore
from backend.storage import utc_text

ROOT=Path(__file__).resolve().parents[1]


def prepare_production_data(source, target, *, backup_dir=None):
    source,target=Path(source).resolve(),Path(target).resolve()
    if not target.is_relative_to(ROOT) or source==target:
        raise ValueError('Use a separate production database inside this workspace')
    if not source.is_file():raise ValueError('Source database is missing')
    if target.exists():raise ValueError('Production target already exists; it will not be overwritten')
    if any(part.is_symlink() for part in [target.parent,*target.parent.parents] if part.is_relative_to(ROOT)):
        raise ValueError('Production path cannot cross a symbolic link')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    backup=Path(backup_dir or ROOT/'var'/'backups').resolve()/('before-real-accounts-'+stamp+'.sqlite3')
    if not backup.is_relative_to(ROOT):raise ValueError('Backup must remain inside this workspace')
    backup.parent.mkdir(parents=True,exist_ok=True)
    original=sqlite3.connect(source.as_uri()+'?mode=ro',uri=True)
    archive=sqlite3.connect(backup)
    original.backup(archive);archive.close();original.close()
    old=sqlite3.connect(backup.as_uri()+'?mode=ro',uri=True)
    old.row_factory=sqlite3.Row
    old.execute('BEGIN')
    if old.execute('SELECT count(*) FROM v2_users WHERE synthetic=0').fetchone()[0]:
        old.close()
        raise ValueError('Source already contains real users; use an account-preserving migration')
    store=ExamStore(target)
    real="SELECT id FROM v2_notices WHERE json_extract(payload,'$.source_kind')='OFFICIAL_WEB_LISTING'"
    updates=f'SELECT id FROM v2_updates WHERE notice_id IN ({real})'
    real_ids={row[0] for row in old.execute(real)}
    available={row[0] for row in old.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    # A rule snapshot containing removed fixture evidence cannot be guessed into
    # an operative production rule history.
    if 'v2_rule_history' in available:
        for row in old.execute('SELECT rules FROM v2_rule_history'):
            for rule in json.loads(row[0]):
                if any(e['document_id'] not in real_ids for e in rule['evidence']):
                    old.close()
                    raise ValueError('Mixed synthetic rule history requires review before migration')
    copies=[
        ('v2_exams','1'),('v2_cycles','1'),('v2_sources','1'),
        ('v2_snapshots',"source_id!='local-demo'"),
        ('v2_extractions',"snapshot_id IN (SELECT id FROM v2_snapshots WHERE source_id!='local-demo')"),
        ('v2_notices',f'id IN ({real})'),('v2_updates',f'id IN ({updates})'),
        ('v2_reviews',f'notice_id IN ({real})'),('v2_polls','1'),
        ('v2_ai_budget','1'),('v2_ai_calls','1'),('v2_ai_cache','1'),('v2_ocr_jobs','1'),
        ('v2_notice_analysis',f'notice_id IN ({real})'),
        ('v2_rule_sets',f'update_id IN ({updates})'),('v2_rule_set_versions',f'update_id IN ({updates})'),
        ('v2_rule_history',f'update_id IN ({updates})'),('v2_rule_heads','1'),
        ('v2_attachment_lineage',f'notice_id IN ({real})'),
        ('v2_source_cursors','1'),('v2_credit_reserve','1'),
    ]
    counts={}
    try:
        with store.connect(write=True) as con:
            for table,predicate in copies:
                if table not in available:continue
                columns=[row[1] for row in old.execute('PRAGMA table_info('+table+')')]
                rows=old.execute('SELECT '+','.join(columns)+' FROM '+table+' WHERE '+predicate).fetchall()
                if table in {'v2_exams','v2_cycles','v2_sources','v2_ai_budget'}:
                    # Seeded catalog/source rows are replaced with observed runtime
                    # configuration, not reset to disabled defaults.
                    operation='INSERT OR REPLACE'
                else:operation='INSERT'
                if rows:con.executemany(operation+' INTO '+table+' ('+','.join(columns)+') VALUES ('+','.join('?' for _ in columns)+')',[tuple(row) for row in rows])
                counts[table]=len(rows)
            if 'v2_processing_jobs' in available:
                for row in old.execute('SELECT * FROM v2_processing_jobs WHERE notice_id IN ('+real+')'):
                    status='PAUSED' if row['status']=='LEASED' else row['status']
                    error='MIGRATION_RECONCILIATION_REQUIRED' if row['status']=='LEASED' else row['last_error']
                    con.execute('INSERT INTO v2_processing_jobs VALUES (?,?,?,?,?,?,?)',(row['notice_id'],status,row['attempts'],row['next_attempt_at'],None,error,row['updated_at']))
            con.execute("INSERT OR REPLACE INTO metadata VALUES ('production_data_migration',?)",(json.dumps({'source_archive':str(backup),'completed_at':utc_text(datetime.now(timezone.utc)),'counts':counts}),))
            if con.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('Source migration failed foreign-key validation')
            if con.execute("SELECT count(*) FROM v2_notices WHERE json_extract(payload,'$.source_kind')='LOCAL_DEMO_FIXTURE'").fetchone()[0]:raise ValueError('Demo notices cannot enter production')
    finally:old.close()
    return {'backup':str(backup),'target':str(target),'copied':counts,'users':0,'notifications':0}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path('var/niyampulse.sqlite3'))
    parser.add_argument('--target',type=Path,default=Path('var/production/niyampulse.sqlite3'))
    args=parser.parse_args()
    print(json.dumps(prepare_production_data(args.source,args.target),indent=2))


if __name__=='__main__':main()
