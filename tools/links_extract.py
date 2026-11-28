# リンクのつながり（試し）：標準入力（展開済みの cirrus 区画）から、記事ごとのリンク先と、転送ページの対応を書き出す
#   出力1：記事名\tリンク先1\tリンク先2…（標準名前空間で Wikidata のある記事だけ）
#   出力2：転送ページ名\t転送先の記事名
import sys, json
f1 = open(sys.argv[1], 'w', encoding='utf-8'); f2 = open(sys.argv[2], 'w', encoding='utf-8')
n = 0
for line in sys.stdin:
    if line.startswith('{"index"'): continue
    o = json.loads(line)
    if str(o.get('namespace')) != '0': continue
    t = o.get('title') or ''
    for r in (o.get('redirect') or []):
        if r.get('namespace') == 0 and r.get('title'): f2.write(r['title'].replace('\t', ' ') + '\t' + t + '\n')
    if not o.get('wikibase_item'): continue
    L = [x.replace('_', ' ') for x in (o.get('outgoing_link') or []) if x and ':' not in x[:20]]
    f1.write(t + '\t' + '\t'.join(L) + '\n'); n += 1
print(n)
