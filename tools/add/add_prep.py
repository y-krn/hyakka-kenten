# 記事を指定して追加する（2）：集めた材料から能力値と技を作り、公開用データに書き足す
# python3 add_prep.py <workdir> <repo_root>
#   workdir に fetch_one.js の出力と、extract_all.py で作った arts.jsonl / meta.jsonl があること
#   結果は workdir/report.json（記事ごとに 追加 / 収録しない理由 / すでにある / 見つからない）
import json, sys, os, re, math, gzip, subprocess, collections, time
W, ROOT = sys.argv[1], sys.argv[2]
TOOLS = os.path.join(ROOT, 'tools'); DATA = os.path.join(ROOT, 'data')
HID = re.compile(r'(記事|項目|ページ|スタブ|ウィキデータ|ウィキペディア|Webarchive|ISBN|Pages using|Infobox|Reflist|CS1|テンプレート|Kartographer|マイクロフォーマット|YouTube personality|プロジェクト|本名非公開|生年非公表|段組み|Taxonbar|LibriVox|OSM|Wikipedia|Template|Articles|Commons|画像提供依頼|告知|削除依頼|保護|要約)')
EXCL = {'Q3839081':'災害','Q171558':'事故','Q83267':'犯罪','Q2223653':'テロ攻撃','Q3199915':'大量虐殺','Q41397':'ジェノサイド','Q149086':'殺人','Q21480300':'大量銃撃事件','Q3241045':'アウトブレイク','Q44512':'エピデミック','Q12184':'パンデミック','Q124757':'暴動','Q350604':'武装紛争','Q198':'戦争','Q178561':'戦闘','Q645883':'軍事作戦','Q10737':'自殺'}
JP = re.compile(r'[ぁ-んァ-ヶ一-龯]'); SENS = re.compile(r'(事件|事故|災害|テロ|虐殺|殺人|戦争|死|犯罪)')
REL = {'P1889': None, 'P138': None, 'P155': '前のもの', 'P156': '次のもの', 'P1365': '先代', 'P1366': '後継', 'P22': '父', 'P25': '母', 'P40': '子', 'P3373': 'きょうだい', 'P26': '配偶者',
 'P1066': '師匠', 'P802': '弟子', 'P737': '影響を受けたもの', 'P144': '原作', 'P4969': '派生作品', 'P47': '隣接しているもの', 'P190': '姉妹都市', 'P460': '同じものとされることがあるもの',
 'P170': '作者', 'P50': '著者', 'P86': '作曲者', 'P57': '監督', 'P61': '発見・発明した人', 'P84': '設計者', 'P112': '創設者', 'P1327': '組んだ相手', 'P1346': '勝者'}
rj = lambda f: [json.loads(l) for l in open(os.path.join(W, f), encoding='utf-8') if l.strip()] if os.path.exists(os.path.join(W, f)) else []
E = {e['id']: e for e in rj('ents.jsonl')}
def idsj(e, p):
    out = []
    for s in ((e or {}).get('c') or {}).get(p) or []:
        v = (s.get('mainsnak') or {}).get('datavalue')
        if v and isinstance(v.get('value'), dict) and 'id' in v['value']: out.append(v['value']['id'])
    return out
memo = {}
def anc(q, d=0):
    if q in memo: return memo[q]
    s = set(); memo[q] = s
    if q in EXCL: s.add(EXCL[q])
    if d < 8:
        for x in idsj(E.get(q), 'P279'): s |= anc(x, d + 1)
    return s
def lj(q):
    l = ((E.get(q) or {}).get('l') or {}).get('ja')
    return l if l and JP.search(l) and not re.search(r'一覧|ウィキメディア', l) else None
def dj(q): return (((E.get(q) or {}).get('d') or {}).get('ja') or '')[:30]
def fnv(s):
    h = 0x811c9dc5; b = s.encode('utf-16-le')
    for i in range(0, len(b), 2): h ^= b[i] | (b[i + 1] << 8); h = (h * 0x01000193) & 0xffffffff
    return h
meta = json.load(open(os.path.join(DATA, 'meta.json'), encoding='utf-8')); NB = meta['nb']
BK = {}
def bucket(k):
    if k not in BK:
        p = os.path.join(DATA, 'a', f'{k}.json.gz'); BK[k] = json.loads(gzip.open(p, 'rt', encoding='utf-8').read()) if os.path.exists(p) else {}
    return BK[k]
dirty = set()
report = {}
titles = json.load(open(os.path.join(W, 'titles.json'), encoding='utf-8'))
for t, real in titles.items():
    if real is None: report[t] = ['見つからない', 'その名前の記事が日本語版Wikipediaにありません']
    elif real in bucket(fnv(real) % NB): report[t] = ['すでにある', real]
# --- gen_v2.js に渡す材料 ---
A = [a for a in rj('arts.jsonl') if a['t'] not in bucket(fnv(a['t']) % NB)]
M = {m['q']: m for m in rj('meta.jsonl')}
for a in A:
    a['cats'] = [c for c in a['cats'] if not HID.search(c) or c == '存命人物']; a['grp'] = 'add'; a.pop('open', None)
G = os.path.join(W, 'gen'); os.makedirs(G, exist_ok=True)
with open(os.path.join(G, 'arts.jsonl'), 'w', encoding='utf-8') as f:
    for a in A: f.write(json.dumps(a, ensure_ascii=False) + '\n')
os.system(f'cp {os.path.join(W, "ents.jsonl")} {G}/ && cp {os.path.join(TOOLS, "k_fit.json")} {G}/')
cls = {}
for a in A:
    s = set()
    for c in idsj(E.get(a['q']), 'P31'): s |= anc(c)
    if s: cls[a['q']] = sorted(s)
typeCnt = {x[0]: x[1] for x in rj('aux_type.jsonl')}
works, rev = {}, {}
for x in rj('aux_works.jsonl'): works[x[0]] = x[1]; rev[x[0]] = {'mil': x[3], 'wrk': x[2], 'wrkTotal': x[1]}
json.dump({'typeCnt': typeCnt, 'rev': rev, 'works': works, 'cls': cls, 'pvScale': 1.3e10, 'asof': meta.get('asof')}, open(os.path.join(G, 'aux.json'), 'w'))
CF = json.loads(gzip.open(os.path.join(TOOLS, 'add', 'cls_freq.json.gz'), 'rt').read())
GX = {}
for a in A:
    q = a['q']; e = E.get(q); m = M.get(q, {}); g = {}
    x = idsj(e, 'P31')
    if x and lj(x[0]) and not SENS.search(lj(x[0])):
        g['c'] = lj(x[0]); g['cf'] = round(max(0, min(5, 4.6 - 1.15 * math.log10(max(1, (CF['freq'].get(x[0], 0) + 1) / 13.1)))), 2)
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
    GX[q] = g
if A:
    r = subprocess.run(['node', os.path.join(TOOLS, 'gen_v2.js'), G], capture_output=True, text=True)
    if r.returncode: print(r.stderr[-2000:]); sys.exit(1)
    d = json.load(open(os.path.join(G, 'big_v2.json'), encoding='utf-8'))
else:
    d = {'F': [], 'DROP': [], 'HOLD': {}}
for grp, t, why in d.get('DROP', []):
    for k, v in titles.items():
        if v == t: report[k] = ['収録しない', why]
# --- 公開用のレコードにして書き足す（build_full.py と同じ変換） ---
K = 0.4
def tierW(w, c=[1, 1.5, 4, 19, 70]):
    if w < c[0]: return 0.5
    if w >= c[4]: return 5.0
    for k in range(4):
        if w < c[k + 1]: return k + 1 + math.log(w / c[k]) / math.log(c[k + 1] / c[k])
RT = json.load(open(os.path.join(W, 'reltitles.json'), encoding='utf-8')) if os.path.exists(os.path.join(W, 'reltitles.json')) else {}
added = 0
for o in range(len(d['F'])):
    f = d['F'][o]; t = d['TI'][o][0][:]; src_ = d['TI'][o][1]; so = str(o)
    q = d['QT'].get(so, {})
    if 'p' in q and src_[2] == 'd' and 'h' not in q:
        t[2] = 2.0; f[7] = [m for m in f[7] if m[1] != '標高落とし']
    x = d['X2'].get(so)
    if x and x[5] >= 1:
        tw = tierW(x[5])
        if tw - 0.53 > t[1]: t[1] = tw - 0.53
    s = sum(t); fct = (8 + K * (s - 8)) / s if s > 0 else 1
    t = [min(5, v * fct) for v in t]
    f[3] = [round(80 + 10 * t[0]), round(24 + 2 * t[1]), round(7 + 3 * t[2]), round(10 + 4 * t[3])]
    rec = {'f': f, 'ext': d['EXT'][so]}
    if q: rec['qt'] = q
    if x: rec['wp'] = x[:5]
    if GX.get(f[2]): rec['gen'] = GX[f[2]]
    if so in d['HOLD']: rec['hold'] = d['HOLD'][so]
    if d['PERSON'][o]: rec['p'] = 1
    # 因縁：関係の先が収録済みなら、両方の記事に書く
    rv = {}; isEv = str(f[6]).startswith('歴史上')
    c = (E.get(f[2]) or {}).get('c') or {}
    for p in REL:
        for v in idsj(E.get(f[2]), p):
            tt = RT.get(v)
            if not tt: continue
            k2 = fnv(tt) % NB; other = bucket(k2).get(tt)
            if not other or (v in rv and p != 'P1889'): continue
            oEv = str(other['f'][6]).startswith('歴史上')
            txt = 'Wikidataに、両者は「互いに異なるもの」と明記されている' if p == 'P1889' else 'Wikidataで直接つながっている、歴史上の因縁の相手' if (isEv or oEv) else \
                  f[0] + 'の名前の由来は' + other['f'][0] if p == 'P138' else 'Wikidataで、' + f[0] + 'の「' + REL[p] + '」は' + other['f'][0]
            rv[v] = txt; other.setdefault('rv', {})[f[2]] = txt; dirty.add(k2)
    if rv: rec['rv'] = rv
    k = fnv(f[1]) % NB; bucket(k)[f[1]] = rec; dirty.add(k); added += 1
    for kk, v in titles.items():
        if v == f[1]: report[kk] = ['確認中として追加' if 'hold' in rec else '追加', f[1] + '（' + ' / '.join(f'{n}{v2}' for n, v2 in zip(['HP', '攻撃', '防御', '速さ'], f[3])) + '）']
for k in dirty:
    raw = json.dumps(BK[k], ensure_ascii=False, separators=(',', ':')).encode()
    open(os.path.join(DATA, 'a', f'{k}.json.gz'), 'wb').write(gzip.compress(raw, 9, mtime=0))
    ts = sorted(t for t, r in BK[k].items() if 'hold' not in r)   # 候補の絞り込み用の記事名索引も更新
    os.makedirs(os.path.join(DATA, 't'), exist_ok=True)
    open(os.path.join(DATA, 't', f'{k}.json.gz'), 'wb').write(gzip.compress(json.dumps(ts, ensure_ascii=False, separators=(',', ':')).encode(), 9, mtime=0))
if added:
    meta['n'] = meta['n'] + added; meta['hold'] = meta.get('hold', 0) + sum(1 for v in report.values() if v[0] == '確認中として追加')
    meta['build'] = time.strftime('%Y%m%d%H%M')
    json.dump(meta, open(os.path.join(DATA, 'meta.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
NOWD = {d['title'] for d in rj('cirrus.jsonl') if not d.get('wikibase_item')}
for t, v in titles.items():
    if t in report: continue
    if v in NOWD: report[t] = ['まだ追加できない', 'この記事にはWikidataの項目がまだ付いていません。新しい記事は数日〜数週間で付くことが多いので、しばらくしてからもう一度送ってください']
    else: report[t] = ['収録しない', '一覧・曖昧さ回避のページなど、対戦に出せない記事です']
json.dump(report, open(os.path.join(W, 'report.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps({'added': added, 'files': len(dirty)}, ensure_ascii=False))
