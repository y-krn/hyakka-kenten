# リンクのつながり（試し）：区画ごとのリンク先を集め、収録している記事どうしのつながりだけにして、大きさを測る
#   収録している記事は data/a の記事名。転送ページ経由のリンクは転送先に読み替える。同じリンクは1本にまとめる
#   出力：大きさの見積もり（ログ）と、試しの成果物（記事番号どうしのつながり。番号は記事名の並び順）
import sys, json, gzip, glob, os, collections
D = sys.argv[1]; OUT = sys.argv[2]; os.makedirs(OUT, exist_ok=True)
titles = []
for f in sorted(glob.glob('data/a/*.json.gz')): titles.extend(json.load(gzip.open(f)).keys())
titles = sorted(set(titles)); ID = {t: i for i, t in enumerate(titles)}; N = len(titles)
print('収録している記事', N, flush=True)
red = {}
for f in glob.glob(D + '/red_*.tsv.gz'):
    for line in gzip.open(f, 'rt', encoding='utf-8'):
        a, _, b = line.rstrip('\n').partition('\t')
        if b in ID: red[a] = ID[b]
print('転送ページ', len(red), flush=True)
adj = [None] * N; raw = 0; kept = 0; arts = 0
for f in sorted(glob.glob(D + '/links_*.tsv.gz')):
    for line in gzip.open(f, 'rt', encoding='utf-8'):
        p = line.rstrip('\n').split('\t'); s = ID.get(p[0])
        if s is None: continue
        arts += 1; raw += len(p) - 1; S = set()
        for x in p[1:]:
            j = ID.get(x)
            if j is None: j = red.get(x)
            if j is not None and j != s: S.add(j)
        kept += len(S); adj[s] = sorted(S)
print('リンクを読んだ記事', arts, '元のリンク', raw, '収録どうし', kept, flush=True)
indeg = [0] * N
for L in adj:
    if L:
        for j in L: indeg[j] += 1
def vbytes(L):
    b = bytearray(); prev = -1
    for j in L:
        d = j - prev; prev = j
        while d >= 0x80: b.append((d & 0x7f) | 0x80); d >>= 7
        b.append(d)
    return bytes(b)
def size(cap):
    buf = bytearray()
    for L in adj:
        if not L: buf.append(0); continue
        if cap and len(L) > cap: L = sorted(sorted(L, key=lambda j: -indeg[j])[:cap])
        v = vbytes(L); n = len(L)
        while n >= 0x80: buf.append((n & 0x7f) | 0x80); n >>= 7
        buf.append(n); buf += v
    return len(buf), len(gzip.compress(bytes(buf), 6)), bytes(buf)
deg = sorted(len(L or []) for L in adj)
q = lambda r: deg[min(len(deg) - 1, int(len(deg) * r))]
res = {'articles': N, 'with_links': arts, 'raw_links': raw, 'edges': kept, 'deg_p50': q(.5), 'deg_p90': q(.9), 'deg_p99': q(.99), 'deg_max': deg[-1], 'zero': sum(1 for d in deg if d == 0)}
for cap in (0, 100, 50, 30):
    r, g, b = size(cap); res['bytes_cap%d' % cap] = r; res['gz_cap%d' % cap] = g
    if cap == 50: open(OUT + '/adj_cap50.bin.gz', 'wb').write(gzip.compress(b, 6))
open(OUT + '/titles.txt', 'w', encoding='utf-8').write('\n'.join(titles))
print('CHJSON' + json.dumps(res, ensure_ascii=False), flush=True)
