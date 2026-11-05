# 自動の訂正表（data/fixa/<番号>.json）を作る
#   入力：数字の照合（.github/workflows/numcheck.yml）の実行記録から取り出した結果（1行1項目の JSON。「NC\t」の後ろ）
#   日本語版の情報欄から確実に読めて、Wikidata と違うもの（小さな差・食い違い）だけを、日本語版の値に合わせる
#   手で書く訂正表（data/fix.json）にある記事は、そちらが優先なので入れない
#   主要作品の並べ直し（tools/check/works.mjs の「WK」の行の JSON）も一緒に渡せる
#   使い方: python3 tools/fixa_build.py 結果1.jsonl 結果2.jsonl ...
import json, os, re, sys

# 照合で「確実に読めた」とされたものでも、次のどれかに当たるものは入れない（全記事の照合を目で確かめて見つけた読み違いの型）
UNIT = re.compile(r'\d[\d,.]*\s*(km|m|mm|kg|t|トン|ha|km2|人|ft|kn|kt|ノット|in|メートル|キロメートル)(?![a-z])', re.I)
def doubtful(r):
    raw = r.get('raw') or ''; wd, jp = r['wd'], r['jp']
    if raw.startswith('|') or re.search(r'\|\s*[^|=\s]+\s*=', raw): return '情報欄の別の項目が混ざっている'
    if "''M''" in raw or '±' in raw or re.search(r'M\s*[J☉⊕]|木星質量|太陽質量', raw): return '天体の単位'
    if '千' in raw: return '千の付いた書き方'
    if r['k'] == 'p' and re.match(r'^\D{0,3}\d{1,3}\.\d{3}(?!\d)', raw) and not re.search('[万億]', raw): return '人口に小数点（欧州の桁区切りの疑い）'
    if wd and jp and (max(abs(wd), abs(jp)) / max(min(abs(wd), abs(jp)), 1e-12) > 300): return '300倍を超えるずれ（万人単位などの読み違いの疑い）'
    if len(UNIT.findall(raw)) >= 2 and not re.search(r'[（(]約?\s*[\d,.]+\s*(km/h|m|ft|km)', raw): return '数字が複数ある'
    return None

LAB = {'e': '標高', 'h': '高さ', 'm': '重さ', 'a': '面積', 'p': '人口', 'l': '長さ', 'd': '深さ', 's': '速さ'}
NB = 256
def fnv(t):
    h = 0x811c9dc5
    for c in t.encode('utf-16-le').decode('utf-16-le'):
        for u in ([ord(c)] if ord(c) < 0x10000 else [0xD800 + ((ord(c) - 0x10000) >> 10), 0xDC00 + ((ord(c) - 0x10000) & 0x3FF)]):
            h ^= u; h = (h * 0x01000193) & 0xFFFFFFFF   # ページの fnv と同じ（UTF-16 の単位で計算する）
    return h

root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..')
hand = json.load(open(os.path.join(root, 'data', 'fix.json'), encoding='utf-8'))
out = [dict() for _ in range(NB)]; n = 0
for path in sys.argv[1:]:
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line: continue
        r = json.loads(line)
        if 'it' in r and 'st' not in r:   # 主要作品の並べ直し（tools/check/works.mjs の「WK」の行）
            if r['t'] not in hand: out[fnv(r['t']) % NB].setdefault(r['t'], {})['主要作品'] = r['it']; n += 1
            continue
        if r['st'] not in ('小さな差', '食い違い') or r.get('fixed') or r['t'] in hand: continue
        if doubtful(r): continue
        v = r.get('jp')
        if not isinstance(v, (int, float)) or v != v or v <= 0 and r['k'] != 'e': continue   # 0 以下（標高を除く）は比べ合いで割り算が壊れるので入れない
        out[fnv(r['t']) % NB].setdefault(r['t'], {})[LAB[r['k']]] = float(f'{v:.6g}'); n += 1
d = os.path.join(root, 'data', 'fixa'); os.makedirs(d, exist_ok=True)
for k in range(NB):
    json.dump(dict(sorted(out[k].items())), open(os.path.join(d, f'{k}.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print('項目', n, '記事', sum(len(o) for o in out))
