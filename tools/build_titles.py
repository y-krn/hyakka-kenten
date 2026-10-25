# 記事名だけの索引（候補の絞り込み用）を作る：data/t/<n>.json.gz に、対戦に出せる記事名の配列
# python3 build_titles.py <data_dir> [番号...]   番号を省くと全部
import json, gzip, os, sys
D = sys.argv[1]; ks = [int(x) for x in sys.argv[2:]] or range(json.load(open(os.path.join(D, 'meta.json')))['nb'])
os.makedirs(os.path.join(D, 't'), exist_ok=True)
for k in ks:
    d = json.loads(gzip.open(os.path.join(D, 'a', f'{k}.json.gz'), 'rt', encoding='utf-8').read())
    ts = sorted(t for t, r in d.items() if 'hold' not in r)
    open(os.path.join(D, 't', f'{k}.json.gz'), 'wb').write(gzip.compress(json.dumps(ts, ensure_ascii=False, separators=(',', ':')).encode(), 9, mtime=0))
