# 生まれた年・できた年ごとの「よく読まれている記事」の索引を作る（誕生日の代表戦の「同い年」で使う）
#   data/a/*.json.gz を読み、1900年〜今年について、人物の上位20件・人物以外の上位10件を data/bd/years.json.gz に書く
#   使い方: python3 tools/build_bd.py
import json, gzip, os, glob, datetime, re
# 代表としておすすめしにくいもの（武器・反社会的勢力・事件など）は外す
NG = re.compile(r'銃|兵器|武器|爆弾|ミサイル|戦車|戦闘機|軍艦|弾薬|ヤクザ|暴力団|犯罪|事件|殺人|テロ|死刑|詐欺|性的|ポルノ|AV女優|アダルト')
D = os.path.join(os.path.dirname(__file__), '..', 'data')
NOR = set(json.load(open(os.path.join(D, 'norand.json'))))
Y0, Y1 = 1900, datetime.date.today().year
P, O = {}, {}
for f in glob.glob(os.path.join(D, 'a', '*.json.gz')):
    for t, r in json.load(gzip.open(f)).items():
        ff = r.get('f') or []
        if len(ff) < 9 or not isinstance(ff[8], int) or not (Y0 <= ff[8] <= Y1) or t in NOR: continue
        pv = 0; job = ''
        for e in r.get('ext') or []:
            if e[0] == '_m': pv = e[5] or 0
            elif e[0] == 'P106' and e[2]: job = e[2][0] if isinstance(e[2][0], str) else e[2][0][0]
        if pv <= 0: continue
        g = r.get('gen') or {}
        if NG.search(' '.join([t, g.get('c') or '', *(g.get('cc') or [])])): continue
        human = g.get('c') == 'ヒト'
        (P if human else O).setdefault(ff[8], []).append((pv, t, ff[0], job if human else ''))
out = {}
for y in range(Y0, Y1 + 1):
    p = sorted(P.get(y, []), reverse=True)[:20]; o = sorted(O.get(y, []), reverse=True)[:10]
    if p or o: out[y] = {'p': [[t, n, j] for _, t, n, j in p], 'o': [[t, n] for _, t, n, _ in o]}
os.makedirs(os.path.join(D, 'bd'), exist_ok=True)
with gzip.open(os.path.join(D, 'bd', 'years.json.gz'), 'wt', encoding='utf-8') as w: json.dump(out, w, ensure_ascii=False, separators=(',', ':'))
print('years', len(out), os.path.getsize(os.path.join(D, 'bd', 'years.json.gz')))
