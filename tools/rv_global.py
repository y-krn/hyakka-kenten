# 因縁（ライバル関係）を全記事まとめて作り直す。区画をまたぐ組み合わせも拾い、
# 「分類（P31）」のようなありふれたつながりは数えず、人や物どうしの直接の関係だけにする。
# python3 rv_global.py <data_dir>  → full/rv.json {QID: {相手QID: 説明}}
import json, sqlite3, glob, os, sys, collections
D = sys.argv[1]
db = sqlite3.connect(os.path.join(D, 'full/ents.db'))
# 因縁として扱う関係（日本語の言い方）
REL = {'P1889': None, 'P138': None,
 'P155': '前のもの', 'P156': '次のもの', 'P1365': '先代', 'P1366': '後継',
 'P22': '父', 'P25': '母', 'P40': '子', 'P3373': 'きょうだい', 'P26': '配偶者',
 'P1066': '師匠', 'P802': '弟子', 'P737': '影響を受けたもの', 'P144': '原作', 'P4969': '派生作品',
 'P47': '隣接しているもの', 'P190': '姉妹都市', 'P460': '同じものとされることがあるもの',
 'P170': '作者', 'P50': '著者', 'P86': '作曲者', 'P57': '監督', 'P61': '発見・発明した人', 'P84': '設計者', 'P112': '創設者',
 'P1327': '組んだ相手', 'P1346': '勝者', 'P1411': 'ノミネートされた賞'}
REL.pop('P1411')
INFO = {}   # QID → (タイトル, 歴史上の出来事か)
for f in sorted(glob.glob(os.path.join(D, 'full/gen/*/big_v2.json'))):
    d = json.load(open(f))
    for r in d['F']: INFO[r[2]] = (r[0], str(r[6]).startswith('歴史上'))
print('keep', len(INFO), flush=True)
RV = collections.defaultdict(dict)
qs = list(INFO); n = 0
for i in range(0, len(qs), 900):
    part = qs[i:i + 900]
    for q, j in db.execute('select id,j from e where id in (%s)' % ','.join('?' * len(part)), part):
        c = (json.loads(j).get('c') or {})
        for p in REL:
            for s in c.get(p) or []:
                v = (s.get('mainsnak') or {}).get('datavalue')
                v = v and isinstance(v.get('value'), dict) and v['value'].get('id')
                if not v or v == q or v not in INFO: continue
                a, b = INFO[q], INFO[v]
                if p != 'P1889' and (v in RV[q]): continue
                if p == 'P1889': t = 'Wikidataに、両者は「互いに異なるもの」と明記されている'
                elif a[1] or b[1]: t = 'Wikidataで直接つながっている、歴史上の因縁の相手'
                elif p == 'P138': t = a[0] + 'の名前の由来は' + b[0]
                else: t = 'Wikidataで、' + a[0] + 'の「' + REL[p] + '」は' + b[0]
                RV[q][v] = t; RV[v][q] = t; n += 1
print('pairs', n, 'articles', len(RV), flush=True)
json.dump(RV, open(os.path.join(D, 'full/rv.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
c = collections.Counter(t.split('の「')[1].split('」')[0] if 'の「' in t else t[:14] for d in RV.values() for t in d.values())
print(c.most_common(20))
