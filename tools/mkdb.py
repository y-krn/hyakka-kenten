# 取得した全エンティティを1つのSQLiteにまとめる（同じIDが複数あれば、主張つき・サイトリンク数の多いものを優先）
import gzip,json,sqlite3,glob,os,sys
G='/mnt/user-data/uploads/Downloads/wikibattler_work/full/gz/'
db=sqlite3.connect(sys.argv[1]); db.execute('PRAGMA journal_mode=OFF'); db.execute('PRAGMA synchronous=OFF')
db.execute('CREATE TABLE IF NOT EXISTS e(id TEXT PRIMARY KEY, score INTEGER, j TEXT)')
files=[G+'00_old.jsonl.gz']+sorted(f for f in glob.glob(G+'*_*.jsonl.gz') if '00_old' not in f)
n=0
for f in files:
    rows=[]
    for l in gzip.open(f,'rt',encoding='utf-8'):
        o=json.loads(l); sc=(1000000 if o.get('c') else 0)+(o.get('sl') or 0)
        rows.append((o['id'],sc,l.rstrip('\n')))
    db.executemany('INSERT INTO e VALUES(?,?,?) ON CONFLICT(id) DO UPDATE SET score=excluded.score, j=excluded.j WHERE excluded.score>e.score',rows)
    db.commit(); n+=len(rows); print(os.path.basename(f),len(rows),n,flush=True)
print('total',db.execute('select count(*) from e').fetchone())
