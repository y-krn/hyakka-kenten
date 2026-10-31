# 仲間図鑑のデータを作る：各記事の「召喚」技（所属先・生みの親・名前の由来・シリーズ・戦争の両陣営）を逆にたどり、
# 同じ相手につながる記事を「一門」としてまとめる。
#   python3 tools/build_fam.py data          → data/fam/<n>.json.gz と data/fam/featured.json を作る
import json, gzip, glob, os, sys, re, collections
D = sys.argv[1] if len(sys.argv) > 1 else 'data'
NB = 512                     # 振り分けるファイルの数
CAP = 400                    # 1つの一門に載せる記事の上限（よく読まれている順）
def fnv(s):
    h = 0x811c9dc5; b = s.encode('utf-16-le')
    for i in range(0, len(b), 2): h ^= b[i] | (b[i + 1] << 8); h = (h * 0x01000193) & 0xffffffff
    return h
KIND = {'親分召喚': 'p', '生みの親召喚': 'c', '本家召喚': 'o', 'シリーズ召喚': 's', '両陣営召喚': 'w'}
excl = set(json.load(open(os.path.join(D, 'exclude.json')))) if os.path.exists(os.path.join(D, 'exclude.json')) else set()
fam = {}
for f in sorted(glob.glob(os.path.join(D, 'a', '*.json.gz'))):
    for t, r in json.loads(gzip.open(f).read()).items():
        if r.get('hold') or t in excl: continue
        pv = next((e[5] for e in r.get('ext', []) if e[0] == '_m'), 0)
        for mv in r['f'][7]:
            if mv[0] != 'SUMMON' or len(mv) < 8 or mv[1] not in KIND: continue
            for name, desc, q in mv[7]:
                key = KIND[mv[1]] + q
                g = fam.setdefault(key, {'k': KIND[mv[1]], 'q': q, 'n': name, 'd': desc, 'm': {}})
                g['m'][t] = [t, r['f'][0], pv]   # 記事名・表示名・1年間の閲覧数
out = collections.defaultdict(dict); nf = nm = 0
for key, g in fam.items():
    if len(g['m']) < 2: continue
    ms = sorted(g['m'].values(), key=lambda x: -x[2])
    out[fnv(key) % NB][key] = {'k': g['k'], 'q': g['q'], 'n': g['n'], 'd': g['d'], 'c': len(ms), 'm': ms[:CAP]}; nf += 1; nm += len(ms)
os.makedirs(os.path.join(D, 'fam'), exist_ok=True)
tot = 0
for k in range(NB):
    b = json.dumps(out.get(k, {}), ensure_ascii=False, separators=(',', ':')).encode()
    z = gzip.compress(b, 9, mtime=0); open(os.path.join(D, 'fam', f'{k}.json.gz'), 'wb').write(z); tot += len(z)
# 今日の一門の候補：ほどよい大きさで、年や年代の一覧のような機械的なものは除く
BORING = re.compile(r'(年代|世紀|年|月|日)$|^紀元前|^\d')
# ランダムに出さない記事（tools/norand.py）が中心の一門は、今日の一門にも出さない
NR = set(json.load(open(os.path.join(D, 'norand.json')))) if os.path.exists(os.path.join(D, 'norand.json')) else set()
def tame(g): ms = list(g['m']); return g['n'] not in NR and sum(t in NR for t in ms) < 0.3 * len(ms)
feat = [[key, g['n'], len(g['m'])] for key, g in fam.items() if tame(g)
        and 8 <= len(g['m']) <= 60 and g['k'] in 'pcos' and not BORING.search(g['n'])
        and sorted((x[2] for x in g['m'].values()), reverse=True)[0] >= 20000]
feat.sort()
json.dump({'nb': NB, 'featured': feat}, open(os.path.join(D, 'fam', 'featured.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('一門', nf, '延べ記事', nm, '圧縮後', tot // 1024, 'KB', '今日の一門の候補', len(feat))
