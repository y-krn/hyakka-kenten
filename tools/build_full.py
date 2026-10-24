# 全記事版：各区画の big_v2.json を、公開用の小さなファイル群に分ける
# python3 build_full.py <gen_dir> <out_dir> [NB]
#   out/a/<n>.json : 記事名のハッシュで NB 個に振り分けた {記事名: レコード}
#   out/meta.json  : 件数・時点・振り分け数・おまかせ用の人気記事
import json, sys, math, os, glob, collections, gzip
G, OUT = sys.argv[1], sys.argv[2]; NB = int(sys.argv[3]) if len(sys.argv) > 3 else 4096
os.makedirs(os.path.join(OUT, 'a'), exist_ok=True)
def fnv(s):   # JS側と同じ：UTF-16の各単位で FNV-1a 32bit
    h = 0x811c9dc5
    b = s.encode('utf-16-le')
    for i in range(0, len(b), 2):
        h ^= b[i] | (b[i + 1] << 8); h = (h * 0x01000193) & 0xffffffff
    return h
K = 0.4
def tierW(w, c=[1, 1.5, 4, 19, 70]):
    if w < c[0]: return 0.5
    if w >= c[4]: return 5.0
    for k in range(4):
        if w < c[k + 1]: return k + 1 + math.log(w / c[k]) / math.log(c[k + 1] / c[k])
B = collections.defaultdict(dict); POP = []; n = 0; nhold = 0; asof = None
RVG = json.load(open(os.path.join(os.path.dirname(os.path.abspath(G)), 'rv.json'))) if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(G)), 'rv.json')) else None
for sd in sorted(glob.glob(os.path.join(G, '*', 'big_v2.json'))):
    d = json.load(open(sd)); asof = d['asof']; d.pop('DROP', None)
    GX = json.load(open(os.path.join(os.path.dirname(sd), 'gen_extra.json')))
    rvq = collections.defaultdict(dict)
    for k, v in d['RV'].items():
        a, b = map(int, k.split(','))
        rvq[a][d['F'][b][2]] = v; rvq[b][d['F'][a][2]] = v
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
        r = {'f': f, 'ext': d['EXT'][so]}
        if q: r['qt'] = q
        if x: r['wp'] = x[:5]
        if GX.get(f[2]): r['gen'] = GX[f[2]]
        if so in d['HOLD']: r['hold'] = d['HOLD'][so]; nhold += 1
        if d['PERSON'][o]: r['p'] = 1
        rv = RVG.get(f[2]) if RVG is not None else rvq.get(o)
        if rv: r['rv'] = rv
        B[fnv(f[0]) % NB][f[0]] = json.dumps(r, ensure_ascii=False, separators=(',', ':')); n += 1   # メモリ節約のため文字列で持つ
        pv = next((e[5] for e in d['EXT'][so] if e[0] == '_m'), 0)
        if so not in d['HOLD']: POP.append((pv, f[0]))
    print(os.path.basename(os.path.dirname(sd)), len(d['F']), flush=True)
tot = 0; totz = 0
for k in range(NB):
    s = '{' + ','.join(json.dumps(t, ensure_ascii=False) + ':' + v for t, v in B.get(k, {}).items()) + '}'
    raw = s.encode(); tot += len(raw)
    gz = gzip.compress(raw, 9, mtime=0); open(os.path.join(OUT, 'a', f'{k}.json.gz'), 'wb').write(gz); totz += len(gz)   # GitHub Pagesの容量に収めるため圧縮して置く
POP.sort(reverse=True)
json.dump({'n': n, 'hold': nhold, 'asof': asof, 'nb': NB, 'popular': [t for _, t in POP[:3000]]}, open(os.path.join(OUT, 'meta.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('articles', n, 'hold', nhold, 'bytes', tot, 'gz', totz, 'avg/file', tot // NB, totz // NB)
