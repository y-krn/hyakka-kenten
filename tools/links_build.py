# リンクのつながりを作る（百科ダンジョン用）：区画ごとのリンク先（links_extract.py の出力）から、
#   1) サイトに置くつながりのファイル data/l/NNNN.bin（1,024個。1つに振り分け4つ分）
#   2) 毎日のお題 data/dg/YYYY-MM.json（今日から DAYS 日分）
# を作る。記事の番号は「振り分け番号 × 1024 ＋ data/t の並び順」（ページ側の data/t と同じ並び）
# つながりは上限なし。収録している記事どうしだけ（転送ページは転送先に読み替える）
import sys, os, json, gzip, glob, datetime, hashlib
import numpy as np
D, OUT = sys.argv[1], sys.argv[2]; DAYS = int(os.environ.get('DAYS', '180'))
NB = 4096
def fnv(t):   # ページ側の fnv と同じ（UTF-16 の単位で数える）
    h = 0x811c9dc5
    for ch in t:
        o = ord(ch)
        for u in ([o] if o < 0x10000 else [0xD800 + ((o - 0x10000) >> 10), 0xDC00 + ((o - 0x10000) & 0x3FF)]):
            h ^= u; h = (h * 0x01000193) & 0xFFFFFFFF
    return h
T = [json.load(gzip.open(f'data/t/{k}.json.gz')) for k in range(NB)]
ID = {}
for k in range(NB):
    for i, t in enumerate(T[k]):
        assert fnv(t) % NB == k, ('振り分けが合わない', t)
        ID[t] = (k << 10) | i
order = [(k << 10) | i for k in range(NB) for i in range(len(T[k]))]; N = len(order)
idmap = np.full(NB << 10, -1, dtype=np.int32); idmap[np.array(order)] = np.arange(N, dtype=np.int32)   # 記事の番号 → 0〜N-1 の通し番号
print('収録している記事（data/t）', N, flush=True)
red = {}
for f in glob.glob(D + '/red_*.tsv.gz'):
    for line in gzip.open(f, 'rt', encoding='utf-8'):
        a, _, b = line.rstrip('\n').partition('\t')
        if b in ID: red[a] = ID[b]
adj = {}
for f in sorted(glob.glob(D + '/links_*.tsv.gz')):
    for line in gzip.open(f, 'rt', encoding='utf-8'):
        p = line.rstrip('\n').split('\t'); s = ID.get(p[0])
        if s is None: continue
        S = set()
        for x in p[1:]:
            j = ID.get(x)
            if j is None: j = red.get(x)
            if j is not None and j != s: S.add(j)
        adj[s] = np.array(sorted(S), dtype=np.int32)
E_ = sum(len(v) for v in adj.values()); print('つながり', E_, flush=True)
# 1) サイトに置くファイル：data/l/NNNN.bin（振り分け 4j〜4j+3）。各振り分け：記事数（可変長整数）、記事ごとに「本数・番号の差分」
def venc(a):   # 可変長整数（7ビットずつ、続きがあれば上の1ビットを立てる）をまとめて作る
    a = np.asarray(a, dtype=np.uint64); n = 1 + (a >= 1 << 7) + (a >= 1 << 14) + (a >= 1 << 21) + (a >= 1 << 28)
    pos = np.cumsum(n) - n; out = np.zeros(int(n.sum()), dtype=np.uint8)
    for b in range(5):
        m = n > b
        if not m.any(): break
        out[pos[m] + b] = (((a[m] >> np.uint64(7 * b)) & np.uint64(0x7f)) | ((n[m] > b + 1).astype(np.uint64) << np.uint64(7))).astype(np.uint8)
    return out.tobytes()
os.makedirs(OUT + '/l', exist_ok=True); tot = 0; EMPTY = np.zeros(0, dtype=np.int32)
for j in range(NB // 4):
    parts = []
    for k in range(4 * j, 4 * j + 4):
        seq = [np.array([len(T[k])])]
        for i in range(len(T[k])):
            L = adj.get((k << 10) | i, EMPTY); seq.append(np.array([len(L)])); seq.append(np.diff(np.r_[-1, L]) - 1)
        parts.append(venc(np.concatenate(seq)))
    b = b''.join(parts); open(f'{OUT}/l/{j}.bin', 'wb').write(b); tot += len(b)
print('つながりのファイル', NB // 4, '個', tot, 'バイト', flush=True)
# 2) 毎日のお題：入口（よく読まれている記事）から、最短4〜5リンクのよく読まれている記事を目的地の候補にする
indptr = np.zeros(N + 1, dtype=np.int64); cnt = np.zeros(N, dtype=np.int64)
for s, L in adj.items(): cnt[idmap[s]] = len(L)
indptr[1:] = np.cumsum(cnt); indices = np.zeros(int(indptr[-1]), dtype=np.int32)
for s, L in adj.items():
    a = indptr[idmap[s]]; indices[a:a + len(L)] = idmap[L]
del adj
meta = json.load(open('data/meta.json')); POP = [t for t in meta.get('popular', []) if t in ID]
ng = set(json.load(open('data/norand.json'))) | set(json.load(open('data/exclude.json')))
CLS = {}
for f in glob.glob('data/a/*.json.gz'):
    for t, r in json.load(gzip.open(f)).items():
        if r.get('hold'): ng.add(t)
        CLS[t] = (r.get('gen') or {}).get('c', '')
POP = [t for t in POP if t not in ng]; POPD = {int(idmap[ID[t]]) for t in POP}
title = lambda d: T[order[d] >> 10][order[d] & 1023]
H = lambda s: int(hashlib.sha1(s.encode()).hexdigest()[:8], 16)
def bfs(src, maxd=5):
    dist = np.full(N, -1, dtype=np.int8); par = np.full(N, -1, dtype=np.int32); dist[src] = 0; f = np.array([src], dtype=np.int32)
    for d in range(1, maxd + 1):
        st = indptr[f]; ln = indptr[f + 1] - st; tl = int(ln.sum())
        if tl == 0: break
        rep = np.repeat(f, ln); off = np.repeat(st - np.cumsum(np.r_[0, ln[:-1]]), ln) + np.arange(tl); nb = indices[off]
        m = dist[nb] == -1; nb = nb[m]; rep = rep[m]
        u, first = np.unique(nb, return_index=True); dist[u] = d; par[u] = rep[first]; f = u
    return dist, par
def path(par, g):
    p = [g]
    while par[p[-1]] >= 0: p.append(int(par[p[-1]]))
    return [title(x) for x in reversed(p)]
os.makedirs(OUT + '/dg', exist_ok=True)
jst = datetime.datetime.utcnow() + datetime.timedelta(hours=9); months = {}
for k in range(DAYS):
    day = (jst + datetime.timedelta(days=k)).strftime('%Y-%m-%d'); opts = []
    for a in range(12):
        if len(opts) >= 2: break
        s = POP[H(f'dg-start/{day}/{a}') % len(POP)]
        if any(o['s'] == s for o in opts): continue
        dist, par = bfs(int(idmap[ID[s]]))
        cands = [int(d) for d in np.nonzero((dist == 4) | (dist == 5))[0] if int(d) in POPD]
        cands.sort(key=lambda d: H(f'dg-goal/{day}/{title(d)}')); G = []
        for g in cands:
            p = path(par, g)
            if CLS.get(p[-1]) and CLS.get(p[-1]) in (CLS.get(p[0]), CLS.get(p[1])): continue   # 目的地は、入口・最初の一歩と違う分類（近すぎるお題を避ける）
            G.append(p)
            if len(G) >= 8: break
        if G: opts.append({'s': s, 'g': G})
    months.setdefault(day[:7], {})[day] = opts
    if k % 20 == 0: print(day, [(o['s'], len(o['g']), len(o['g'][0]) - 1) for o in opts], flush=True)
for m, v in months.items(): json.dump(v, open(f'{OUT}/dg/{m}.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('お題', DAYS, '日分', flush=True)
