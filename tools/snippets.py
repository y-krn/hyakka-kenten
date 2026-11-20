#!/usr/bin/env python3
# 脚注に添える「記事の本文の1文」を作る（作り直しのときに使う）
#   技に使う事実（data/a の先出しの技：生年・成立年・標高・人口など数字のもの）について、その数字が出てくる本文の1文を探す
#   対象はよく読まれている記事（年1万回以上）だけ。データが重くなりすぎないように、1文は90字まで
#   使い方:
#     bzcat jawiki_content-…json.bz2 | python3 tools/snippets.py collect data out/sn_00.json   … 本文データ1区画ぶんを探す
#     python3 tools/snippets.py apply data out/sn_*.json                                     … 見つかった1文を data/a の各記事に sn として入れる
#   本文の引用なので、画面では出典（日本語版Wikipedia・CC BY-SA 4.0）を必ず添える
import json, gzip, os, re, sys, glob
PV_MIN = 10000
OK = re.compile(r'生まれ|成立|開始|公開|設立|発売|創刊|竣工|開業|開通|開館|創業|創建|建立|誕生|放送開始|標高|高さ|全高|人口|面積|長さ|全長|延長|重さ|体重|収容|深さ|周長|最大|作品')
UNIT = {'年': r'年', '標高': r'\s*(?:m|メートル)', '高さ': r'\s*(?:m|メートル|cm)', '全高': r'\s*(?:m|メートル|cm)', '人口': r'\s*人', '面積': r'\s*(?:km|平方キロ|ha|m²|㎢|平方メートル)',
        '長さ': r'\s*(?:km|m|キロ|メートル)', '全長': r'\s*(?:km|m|キロ|メートル)', '延長': r'\s*(?:km|m|キロ|メートル)', '体重': r'\s*(?:kg|キロ)', '重さ': r'\s*(?:kg|t|トン|キロ)', '収容': r'\s*人', '深さ': r'\s*(?:m|メートル)'}
NUM = re.compile(r'\d[\d,]*(?:\.\d+)?')
JUNK = re.compile(r'https?://|閲覧。|ISBN|\[\[|\]\]|{{|}}')
def facts(r):
    out = []
    for m in (r.get('f') or [None] * 8)[7] or []:
        d, sh = str(m[3]), str(m[2])
        if not OK.search(d) or '名前の音' in d: continue
        n = NUM.search(sh)
        if not n: continue
        unit = next((u for k, u in UNIT.items() if k in d and k != '年'), r'年' if re.search(r'\d{3,4}年', sh) else None)
        if not unit: continue
        out.append((d, n.group(0), unit))
    return out
def find(text, tok, unit):
    plain = tok.replace(',', '').split('.')[0]
    digs = r',?'.join(plain) if len(plain) <= 9 else re.escape(plain)
    pat = re.compile(r'(?<![\d.,])' + digs + r'(?:\.\d+)?' + unit)
    for s in re.split(r'(?<=。)', text):
        m = pat.search(s)
        if not m or JUNK.search(s): continue
        s = re.sub(r'^（\d{4}年\d{1,2}月）\s*', '', s.strip())   # 保守用の札の名残を除く
        s = re.sub(r'^ポータル\s+\S+\s+', '', s)   # ポータルへの案内の名残を除く
        if len(s) > 90:
            a = max(0, m.start() - 40); s = ('…' if a > 0 else '') + s[a:a + 88] + '…'
        return s
    return None
def load_targets(D):
    T = {}
    for f in glob.glob(os.path.join(D, 'a', '*.json.gz')):
        for t, r in json.load(gzip.open(f)).items():
            pv = next((e[5] for e in r.get('ext') or [] if e[0] == '_m' and len(e) > 5), 0)
            if pv >= PV_MIN:
                fs = facts(r)
                if fs: T[t] = fs
    return T
if sys.argv[1] == 'collect':
    D, out = sys.argv[2], sys.argv[3]; cache = sys.argv[4] if len(sys.argv) > 4 else None   # cache：対象の一覧を一度作って使い回す
    if cache and os.path.exists(cache): T = {t: [tuple(x) for x in v] for t, v in json.load(open(cache)).items()}
    else:
        T = load_targets(D)
        if cache: json.dump(T, open(cache, 'w'), ensure_ascii=False)
    R = {}; n = 0
    for l in sys.stdin:
        try: o = json.loads(l)
        except Exception: continue
        t = o.get('title')
        if t not in T: continue
        sn = {}
        for d, tok, unit in T[t]:
            s = find(o.get('text') or '', tok, unit)
            if s: sn[d] = s
        if sn: R[t] = sn; n += len(sn)
    json.dump(R, open(out, 'w'), ensure_ascii=False)
    print('対象', len(T), '見つかった記事', len(R), '1文', n, file=sys.stderr)
elif sys.argv[1] == 'apply':
    D = sys.argv[2]; R = {}
    for f in sys.argv[3:]: R.update(json.load(open(f)))
    k = 0
    for f in glob.glob(os.path.join(D, 'a', '*.json.gz')):
        o = json.load(gzip.open(f)); ch = False
        for t in o:
            if t in R: o[t]['sn'] = R[t]; ch = True; k += 1
        if ch:
            with gzip.open(f, 'wt', encoding='utf-8', compresslevel=9) as w: json.dump(o, w, ensure_ascii=False, separators=(',', ':'))
    print('1文を入れた記事', k, file=sys.stderr)
