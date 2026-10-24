# 全記事版の下準備：区画（shard）ごとに gen_v2.js が読める arts.jsonl / ents.jsonl / aux.json / gen_extra.json を作る
# python3 prep_full.py <data_dir>   （data_dir/all/arts_XX.jsonl, meta_XX.jsonl, data_dir/full/ents.db, full/aux_*.jsonl）
import json, sqlite3, re, sys, os, math, collections, glob
D = sys.argv[1]; only = sys.argv[2:]  # 区画を指定すればそれだけ
db = sqlite3.connect(os.path.join(D, 'full/ents.db'))
HID = re.compile(r'(記事|項目|ページ|スタブ|ウィキデータ|ウィキペディア|Webarchive|ISBN|Pages using|Infobox|Reflist|CS1|テンプレート|Kartographer|マイクロフォーマット|YouTube personality|プロジェクト|本名非公開|生年非公表|段組み|Taxonbar|LibriVox|OSM|Wikipedia|Template|Articles|Commons|画像提供依頼|告知|削除依頼|保護|要約)')
EXCL = {'Q3839081':'災害','Q171558':'事故','Q83267':'犯罪','Q2223653':'テロ攻撃','Q3199915':'大量虐殺','Q41397':'ジェノサイド','Q149086':'殺人','Q21480300':'大量銃撃事件','Q3241045':'アウトブレイク','Q44512':'エピデミック','Q12184':'パンデミック','Q124757':'暴動','Q350604':'武装紛争','Q198':'戦争','Q178561':'戦闘','Q645883':'軍事作戦','Q10737':'自殺'}
JP = re.compile(r'[ぁ-んァ-ヶ一-龯]')
SENS = re.compile(r'(事件|事故|災害|テロ|虐殺|殺人|戦争|死|犯罪)')
CACHE = {}
def get(q):
    if q in CACHE: return CACHE[q]
    r = db.execute('select j from e where id=?', (q,)).fetchone(); e = json.loads(r[0]) if r else None
    if len(CACHE) < 60000: CACHE[q] = e
    return e
def getmany(qs):
    out = {}; qs = list(qs)
    for i in range(0, len(qs), 900):
        part = qs[i:i+900]
        for q, j in db.execute('select id,j from e where id in (%s)' % ','.join('?'*len(part)), part): out[q] = j
    return out
def idsj(e, p):
    out = []
    for s in ((e or {}).get('c') or {}).get(p) or []:
        v = (s.get('mainsnak') or {}).get('datavalue')
        if v and isinstance(v.get('value'), dict) and 'id' in v['value']: out.append(v['value']['id'])
    return out
def allids(e):
    out = set()
    for p, ss in ((e or {}).get('c') or {}).items():
        for s in ss:
            v = (s.get('mainsnak') or {}).get('datavalue')
            if v and isinstance(v.get('value'), dict) and 'id' in v['value']: out.add(v['value']['id'])
    return out
memo = {}
def anc(q, d=0):
    if q in memo: return memo[q]
    s = set()
    if q in EXCL: s.add(EXCL[q])
    if d < 8:
        for x in idsj(get(q), 'P279'): s |= anc(x, d + 1)
    memo[q] = s; return s
# 補助データ（旧＋今回の検索）
old = json.load(open('/mnt/user-data/uploads/Downloads/wikibattler_work/big/aux.json'))
typeCnt = dict(old['typeCnt']); works = dict(old['works']); rev = dict(old['rev'])
AUXD = '/mnt/user-data/uploads/Downloads/wikibattler_work/full/'
for f, kind in [(AUXD + 'aux_type.jsonl', 't'), (AUXD + 'aux_works.jsonl', 'w')]:
    if not os.path.exists(f): continue
    for l in open(f):
        x = json.loads(l)
        if kind == 't': typeCnt[x[0]] = x[1]
        else: works[x[0]] = x[1]; rev[x[0]] = {'mil': x[3], 'wrk': x[2], 'wrkTotal': x[1]}
# 記事データ（全区画）を読み、P31の出現数（全体）を数える
shards = sorted(os.path.basename(f)[5:7] for f in glob.glob(os.path.join(D, 'all/arts_*.jsonl')))
cls_freq = collections.Counter(); P31 = {}
for sh in shards:
    for l in open(os.path.join(D, f'all/arts_{sh}.jsonl')):
        a = json.loads(l)
        if a['disamb'] or a['t'].endswith('一覧'): continue
        P31[a['q']] = None
qs = list(P31)
for i in range(0, len(qs), 50000):
    for q, j in getmany(qs[i:i+50000]).items():
        c = idsj(json.loads(j), 'P31'); P31[q] = c
        if c: cls_freq[c[0]] += 1
# 人物の作品数：検索していない人物は、収録記事のうち作者・出演などに名前があるものを数える（下限値）
WP = ['P50','P170','P86','P57','P175','P161','P725']
localW = collections.Counter()
for i in range(0, len(qs), 50000):
    for q, j in getmany(qs[i:i+50000]).items():
        e = json.loads(j)
        for p in WP:
            for x in set(idsj(e, p)): localW[x] += 1
print('main', len(qs), 'typeCnt', len(typeCnt), 'works(search)', len(works), 'localW', len(localW), flush=True)
def lj(q):
    l = ((get(q) or {}).get('l') or {}).get('ja')
    return l if l and JP.search(l) and not re.search(r'一覧|ウィキメディア', l) else None
def dj(q): return (((get(q) or {}).get('d') or {}).get('ja') or '')[:30]
for sh in (only or shards):
    out = os.path.join(D, 'full/gen', sh); os.makedirs(out, exist_ok=True)
    if os.path.exists(os.path.join(out, 'big_v2.json')): continue
    CACHE.clear()
    A = []; M = {}
    for l in open(os.path.join(D, f'all/arts_{sh}.jsonl')):
        a = json.loads(l); a['cats'] = [c for c in a['cats'] if not HID.search(c) or c == '存命人物']; a['grp'] = 'shard' + sh; a.pop('open', None); A.append(a)
    for l in open(os.path.join(D, f'all/meta_{sh}.jsonl')):
        m = json.loads(l); M[m['q']] = m
    main = [a['q'] for a in A]
    E = {q: j for q, j in getmany(main).items()}
    L1 = set()
    for j in E.values(): L1 |= allids(json.loads(j))
    E1 = getmany(L1 - set(E)); E.update(E1)
    L2 = set()
    for j in E1.values(): L2 |= allids(json.loads(j))
    E.update(getmany(L2 - set(E)))
    # クラスの上位を8段
    fr = set()
    for j in list(E.values()): fr |= set(idsj(json.loads(j), 'P279'))
    for _ in range(8):
        fr -= set(E)
        if not fr: break
        got = getmany(fr); E.update(got); fr = set()
        for j in got.values(): fr |= set(idsj(json.loads(j), 'P279'))
    with open(os.path.join(out, 'ents.jsonl'), 'w') as f:
        for j in E.values(): f.write(j + '\n')
    cls = {}
    with open(os.path.join(out, 'arts.jsonl'), 'w') as f:
        for a in A:
            f.write(json.dumps(a, ensure_ascii=False) + '\n')
            s = set()
            for c in (P31.get(a['q']) or []): s |= anc(c)
            if s: cls[a['q']] = sorted(s)
    W2 = {q: max(works.get(q, 0), localW[q]) for q in main if q in works or localW[q]}
    json.dump({'typeCnt': {q: typeCnt[q] for q in main if q in typeCnt}, 'rev': {q: rev[q] for q in main if q in rev}, 'works': W2, 'cls': cls, 'pvScale': 1.3e10, 'asof': '2026-10-18'}, open(os.path.join(out, 'aux.json'), 'w'))
    # 汎用技の素材
    G = {}
    for a in A:
        q = a['q']; e = json.loads(E[q]) if q in E else None; m = M.get(q, {}); g = {}
        x = idsj(e, 'P31')
        if x and lj(x[0]) and not SENS.search(lj(x[0])):
            g['c'] = lj(x[0]); g['cf'] = round(max(0, min(5, 4.6 - 1.15 * math.log10(max(1, cls_freq[x[0]] / 13.1)))), 2)  # 旧データ（約10.8万記事）と同じ尺度にそろえる
        red = [r for r in m.get('red', []) if r != a['t'] and not SENS.search(r)]
        if red: g['r'] = [len(m.get('red', []))] + red[:2]
        if m.get('ct'): g['ct'] = m['ct'][:7]
        if m.get('maint'): g['mt'] = m['maint']
        if m.get('coord'): g['co'] = m['coord']
        hs = [h for h in m.get('heads', []) if len(h) <= 14 and not SENS.search(h)]
        if len(hs) >= 2: g['h'] = hs[:3]
        cs = [c for c in a.get('cats', []) if c != '存命人物' and not re.search(r'\d{3,4}年(生|没)$', c) and not SENS.search(c) and len(c) <= 22]
        if len(cs) >= 2: g['cc'] = cs[:2]
        if m.get('ext'): g['x'] = m['ext']
        loc = [v for v in idsj(e, 'P131') if lj(v)]
        if loc: g['loc'] = [lj(loc[0]), dj(loc[0]), loc[0]]
        jobs = [v for v in idsj(e, 'P106') if lj(v)]
        if len(jobs) == 1: g['job'] = lj(jobs[0])
        G[q] = g
    json.dump(G, open(os.path.join(out, 'gen_extra.json'), 'w'), ensure_ascii=False)
    os.system(f'cp {D}/gen/k_fit.json {out}/')
    print(sh, 'arts', len(A), 'ents', len(E), 'cls', len(cls), flush=True)
    if os.environ.get('GEN'):
        rc = os.system(f'node --max-old-space-size=4500 {os.path.dirname(os.path.abspath(__file__))}/gen_v2.js {out} > {out}/gen.log 2>&1')
        print(sh, 'gen rc', rc, open(f'{out}/gen.log').read()[-300:], flush=True)
        if rc == 0: os.remove(os.path.join(out, 'ents.jsonl'))
