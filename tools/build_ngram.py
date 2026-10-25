# 部分一致の検索用：記事名の2文字ずつ（バイグラム）から記事名を引く索引を作る
#   data/g/<n>.json.gz : {バイグラム: [その2文字を含む記事の総数, [記事名（閲覧数の多い順に最大CAP件）]]}
#   表記ゆれを減らすため、NFKC・小文字・ひらがな→カタカナにそろえてから2文字に切る（ページ側も同じ）
# python3 build_ngram.py <data_dir>
import json, gzip, os, sys, unicodedata, collections
D = sys.argv[1]; CAP = 500
meta = json.load(open(os.path.join(D, 'meta.json'))); NB = meta['nb']
def fnv(s):
    h = 0x811c9dc5; b = s.encode('utf-16-le')
    for i in range(0, len(b), 2): h ^= b[i] | (b[i + 1] << 8); h = (h * 0x01000193) & 0xffffffff
    return h
def norm(s):
    s = unicodedata.normalize('NFKC', s).lower()
    return ''.join(chr(ord(c) + 0x60) if 'ぁ' <= c <= 'ゖ' else c for c in s)
def grams(t):
    n = norm(t); return {n[i:i + 2] for i in range(len(n) - 1)}
pv = []
for k in range(NB):
    d = json.loads(gzip.open(os.path.join(D, 'a', f'{k}.json.gz'), 'rt', encoding='utf-8').read())
    for t, r in d.items():
        if 'hold' in r: continue
        m = next((e for e in r['ext'] if e[0] == '_m'), None); pv.append((-(m[5] if m else 0), t))
pv.sort()
G = collections.defaultdict(list); CNT = collections.Counter()
for _, t in pv:
    for g in grams(t):
        CNT[g] += 1
        if len(G[g]) < CAP: G[g].append(t)
B = collections.defaultdict(dict)
for g, lst in G.items(): B[fnv(g) % NB][g] = [CNT[g], lst]
os.makedirs(os.path.join(D, 'g'), exist_ok=True); tot = 0
for k in range(NB):
    z = gzip.compress(json.dumps(B.get(k, {}), ensure_ascii=False, separators=(',', ':')).encode(), 9, mtime=0); tot += len(z)
    open(os.path.join(D, 'g', f'{k}.json.gz'), 'wb').write(z)
print('titles', len(pv), 'grams', len(G), 'gz bytes', tot, 'avg', tot // NB)
