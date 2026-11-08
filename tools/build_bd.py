# 「あなたの代表戦」で使う索引を、収録データ（data/a）から作る
#   data/bd/years.json.gz … 生まれた年・できた年ごとに、よく読まれている人（20件）・もの（10件）
#   --wikidata を付けると、Wikidata に生年月日と出生地を問い合わせて、次の2つも作る
#   data/bd/d/<月>.json.gz … 誕生日（月日）ごとに、よく読まれている人（15件）
#   data/bd/ymd/<年>.json.gz … 生年月日ごとに、その日に生まれた人（10件）。誕生日と生まれた年の両方を入れたとき用
#   data/bd/p/<番号>.json.gz … 出身地（日本語版の記事名）ごとに、そこで生まれた人の全員（よく読まれている順）。番号は記事名のFNVハッシュ % NBP
#     出生地の1つ上・2つ上の行政区画（例：北区 → 札幌市 → 北海道）にも数える
#   よく読まれている＝収録データにある1年間の閲覧数。人の並びは毎回この索引から作るので、遊ぶ人のブラウザは Wikipedia に問い合わせない
#   使い方: python3 tools/build_bd.py [--wikidata]
import json, gzip, os, glob, datetime, re, sys, time, urllib.request, urllib.parse
D = os.path.join(os.path.dirname(__file__), '..', 'data')
NOR = set(json.load(open(os.path.join(D, 'norand.json'))))
# 代表としておすすめしにくいもの（武器・反社会的勢力・事件など）は外す
NG = re.compile(r'銃|兵器|武器|爆弾|ミサイル|戦車|戦闘機|軍艦|弾薬|ヤクザ|暴力団|犯罪|事件|殺人|テロ|死刑|詐欺|性的|ポルノ|AV女優|アダルト')
Y0, Y1 = 1900, datetime.date.today().year
NBP = 256
UA = 'hyakka-kenten-build/1.0 (https://github.com/y-krn/hyakka-kenten)'

def fnv(s):
    h = 2166136261
    for ch in s:
        h ^= ord(ch); h = (h * 16777619) & 0xffffffff
    return h

def dump(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, 'wt', encoding='utf-8') as w: json.dump(obj, w, ensure_ascii=False, separators=(',', ':'))

# ---------- 収録データを読む ----------
P, O, H = {}, {}, {}   # 年→人, 年→もの, QID→(閲覧数, 記事名, 表示名, 年)
# 確認中（保留）の記事は入れない（対戦に戻した記事 data/unhold.json は入れる）。ページ側で1人ずつ確かめなくて済むように
_U = json.load(open(os.path.join(D, 'unhold.json'), encoding='utf-8')) if os.path.exists(os.path.join(D, 'unhold.json')) else {}
def held(t, r):
    if 'hold' not in r: return False
    return not (t in _U.get('記事', {}) or re.sub(r'（[^（）]*年[^（）]*）$', '', str(r['hold'])) in _U.get('理由', {}))
for f in glob.glob(os.path.join(D, 'a', '*.json.gz')):
    for t, r in json.load(gzip.open(f)).items():
        ff = r.get('f') or []
        if len(ff) < 9 or t in NOR or held(t, r): continue
        if str(ff[6] if len(ff) > 6 else '').startswith('存命人物') and re.search('天皇|皇族|内親王|親王|皇后|皇太子|上皇|秋篠宮|宮家', ' '.join([t, *((r.get('gen') or {}).get('cc') or [])])): continue   # 存命の皇族は、代表戦・ゆかりの人に出さない
        g = r.get('gen') or {}
        if NG.search(' '.join([t, g.get('c') or '', *(g.get('cc') or [])])): continue
        pv = next((e[5] or 0 for e in (r.get('ext') or []) if e[0] == '_m'), 0)
        if pv <= 0: continue
        human = g.get('c') == 'ヒト'
        y = ff[8] if isinstance(ff[8], int) else None
        if human and ff[2]: H[ff[2]] = (pv, t, ff[0], y)
        if y is not None and Y0 <= y <= Y1: (P if human else O).setdefault(y, []).append((pv, t, ff[0]))
out = {}
for y in range(Y0, Y1 + 1):
    p = sorted(P.get(y, []), reverse=True)[:20]; o = sorted(O.get(y, []), reverse=True)[:10]
    if p or o: out[y] = {'p': [[t, n] for _, t, n in p], 'o': [[t, n] for _, t, n in o]}
dump(os.path.join(D, 'bd', 'years.json.gz'), out)
print('years', len(out), '人物', len(H))
if '--wikidata' not in sys.argv: sys.exit(0)

# ---------- Wikidata：生年月日（日の精度のもの）と出生地 ----------
Q = '''SELECT ?item ?dob ?prec ?pobT ?parT ?par2T WHERE {
 VALUES ?item { %s }
 OPTIONAL { ?item p:P569 ?st. ?st psv:P569 ?tv; wikibase:rank ?rk. ?tv wikibase:timeValue ?dob; wikibase:timePrecision ?prec. FILTER(?rk != wikibase:DeprecatedRank) }
 OPTIONAL { ?item wdt:P19 ?pob.
   OPTIONAL { ?pa schema:about ?pob; schema:isPartOf <https://ja.wikipedia.org/>; schema:name ?pobT }
   OPTIONAL { ?pob wdt:P131 ?par. ?pb schema:about ?par; schema:isPartOf <https://ja.wikipedia.org/>; schema:name ?parT.
     OPTIONAL { ?par wdt:P131 ?par2. ?pc schema:about ?par2; schema:isPartOf <https://ja.wikipedia.org/>; schema:name ?par2T } } }
}'''
def sparql(qids):
    body = urllib.parse.urlencode({'query': Q % ' '.join('wd:' + q for q in qids), 'format': 'json'}).encode()
    for k in range(6):
        try:
            req = urllib.request.Request('https://query.wikidata.org/sparql', data=body, headers={'User-Agent': UA, 'Accept': 'application/sparql-results+json', 'Content-Type': 'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(req, timeout=90) as r: return json.load(r)['results']['bindings']
        except Exception as e:
            wait = 10 * (k + 1); print('  再試行', k + 1, e, f'{wait}秒待つ', flush=True); time.sleep(wait)
    raise SystemExit('Wikidata に問い合わせできませんでした')

qids = sorted(H, key=lambda q: -H[q][0])[:int(os.environ.get('BD_MAX') or 200000)]   # よく読まれている20万人まで（全員だと1時間半かかる）
if os.environ.get('BD_LIMIT'): qids = qids[:int(os.environ['BD_LIMIT'])]   # 試しに少しだけ動かすとき
DAY, PLACE, YMD = {}, {}, {}
B = 500
t0 = time.time()
for i in range(0, len(qids), B):
    rows = sparql(qids[i:i + B]); dob, pl = {}, {}
    for b in rows:
        q = b['item']['value'].rsplit('/', 1)[1]
        if 'dob' in b and b.get('prec', {}).get('value') == '11':
            m = re.match(r'^(\d{4})-(\d\d)-(\d\d)', b['dob']['value'])
            if m and int(m.group(1)) >= 1600: dob.setdefault(q, set()).add((int(m.group(1)), int(m.group(2)), int(m.group(3))))
        for k in ('pobT', 'parT', 'par2T'):
            if k in b: pl.setdefault(q, set()).add(b[k]['value'])
    for q, ds in dob.items():
        if len(ds) != 1: continue   # 誕生日の記録が食い違う人は使わない
        (yy, mm, dd), = ds; pv, t, n, y = H[q]; DAY.setdefault(f'{mm}/{dd}', []).append((pv, t, n, yy))
        if Y0 <= yy <= Y1: YMD.setdefault(yy, {}).setdefault(f'{mm}/{dd}', []).append((pv, t, n))
    for q, ps in pl.items():
        pv, t, n, y = H[q]
        for p in ps: PLACE.setdefault(p, []).append((pv, t, n, y))
    if (i // B) % 25 == 0: print(f'  {min(i + B, len(qids))}/{len(qids)}  {int(time.time() - t0)}秒  誕生日{len(DAY)}日 出身地{len(PLACE)}か所', flush=True)
    time.sleep(1)   # 続けざまに送らない

for mm in range(1, 13):
    dump(os.path.join(D, 'bd', 'd', f'{mm}.json.gz'), {k: [[t, n, y] for _, t, n, y in sorted(v, reverse=True)[:15]] for k, v in DAY.items() if k.startswith(f'{mm}/')})
for yy, days in YMD.items():
    dump(os.path.join(D, 'bd', 'ymd', f'{yy}.json.gz'), {k: [[t, n] for _, t, n in sorted(v, reverse=True)[:10]] for k, v in days.items()})
PB = {}
for p, v in PLACE.items():
    if len(v) < 2: continue
    PB.setdefault(fnv(p) % NBP, {})[p] = [[t, n, y] for _, t, n, y in sorted(v, reverse=True)]   # 全員（よく読まれている順）。「この辺の記事」のゆかりの人で全員を出す
for k in range(NBP): dump(os.path.join(D, 'bd', 'p', f'{k}.json.gz'), PB.get(k, {}))
json.dump({'nbp': NBP, 'asof': datetime.date.today().isoformat()}, open(os.path.join(D, 'bd', 'meta.json'), 'w'))
print('誕生日', len(DAY), '日', '出身地', sum(len(x) for x in PB.values()), 'か所', int(time.time() - t0), '秒')
