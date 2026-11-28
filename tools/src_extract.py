# 正本に入れる、検索用ダンプ（cirrus, jawiki_content）からの取り出し：作り直しのたびにダンプを読み直さずに済むようにする
#   標準入力：展開済みの cirrus 区画
#   出力1（links）：記事名\tQ番号\tリンク先1\tリンク先2…（標準名前空間で Wikidata のある記事だけ。リンク先は記事名のまま）
#   出力2（red）  ：転送ページ名\t転送先の記事名
#   出力3（text） ：1行1記事の JSON {t, q, text}（脚注に添える本文の1文を探すため。Wikidata のある記事だけ）
# python3 src_extract.py <links.tsv> <red.tsv> <text.jsonl>
import sys, json
f1, f2, f3 = (open(p, 'w', encoding='utf-8') for p in sys.argv[1:4])
n = 0
for line in sys.stdin:
    if line.startswith('{"index"'): continue
    o = json.loads(line)
    if str(o.get('namespace')) != '0': continue
    t = o.get('title') or ''
    for r in (o.get('redirect') or []):
        if r.get('namespace') == 0 and r.get('title'): f2.write(r['title'].replace('\t', ' ') + '\t' + t + '\n')
    q = o.get('wikibase_item')
    if not q: continue
    L = [x.replace('_', ' ') for x in (o.get('outgoing_link') or []) if x and ':' not in x[:20]]
    f1.write(t + '\t' + q + '\t' + '\t'.join(L) + '\n')
    f3.write(json.dumps({'t': t, 'q': q, 'text': o.get('text') or ''}, ensure_ascii=False) + '\n')
    n += 1
print(n)
