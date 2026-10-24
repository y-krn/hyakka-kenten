# 標準入力（展開済みのcirrus区画）から arts と meta2 を同時に書き出す
import sys, json, re
SEC = re.compile(r'^==[^=].*?[^=]==\s*$', re.M)
IMG = re.compile(r'([^|\[\]=\n{}:]+\.(?:jpe?g|png|svg|gif|tiff?|webp))', re.I)
DIS = re.compile(r'Template:(Aimai|曖昧さ回避|人名の曖昧さ回避|地名の曖昧さ回避)')
MAINT = {'出典の明記':'出典','要出典範囲':'出典','要出典':'出典','出典の明記/dateHandler':'出典','独自研究':'独自研究','特筆性':'特筆性','正確性':'正確性','宣伝':'宣伝','未検証':'未検証','更新':'更新','観点':'観点','単一の出典':'単一の出典','一次資料':'一次資料','大言壮語':'大言壮語','言葉を濁さない':'言葉を濁す','雑多な内容の箇条書き':'雑多','Wikify':'整形','スタブ':'スタブ','Substub':'スタブ'}
SKIPH = re.compile(r'^(脚注|注釈|出典|参考文献|関連項目|外部リンク|関連文献|参考資料|注|補注|脚注・出典|出典・脚注|外部サイト)$')
d1, d2 = sys.argv[1], sys.argv[2]
n = 0
with open(d1,'w',encoding='utf-8') as out, open(d2,'w',encoding='utf-8') as out2:
    for line in sys.stdin:
        if line.startswith('{"index"'): continue
        o = json.loads(line)
        if str(o.get('namespace')) != '0' or not o.get('wikibase_item'): continue
        st = o.get('source_text') or ''
        imgs = {m.strip().lower() for m in IMG.findall(st)}
        tpl = o.get('template') or []
        rec = {
            't': o['title'], 'q': o['wikibase_item'], 'pid': int(o['page_id']),
            'cats': o.get('category') or [],
            'sec': len(SEC.findall(st)), 'out': len(o.get('outgoing_link') or []),
            'inl': int(o.get('incoming_links') or 0), 'bytes': int(o.get('text_bytes') or 0),
            'pop': float(o.get('popularity_score') or 0), 'ds': o.get('defaultsort') or None,
            'open': (o.get('opening_text') or '')[:300], 'img': len(imgs),
            'disamb': any(DIS.search(t) for t in tpl), 'ct': o.get('create_timestamp'),
        }
        out.write(json.dumps(rec, ensure_ascii=False) + '\n')
        tpl = [t.replace('Template:','') for t in (o.get('template') or []) if t.startswith('Template:')]
        maint = sorted({v for t in tpl for k,v in MAINT.items() if t==k or t.startswith(k+'/') or (k=='スタブ' and t.endswith('stub'))})
        info = [t for t in tpl if t.startswith('Infobox') and '/' not in t][:1]
        co = o.get('coordinates') or []
        coord = None
        for c in co:
            if c.get('primary') and c.get('coord'):
                coord = [round(c['coord']['lat'],3), round(c['coord']['lon'],3)]; break
        topics = []
        for w in (o.get('weighted_tags') or []):
            m = re.match(r'classification\.prediction\.articletopic/([^|]+)\|(\d+)', w)
            if m: topics.append((int(m.group(2)), m.group(1)))
        topics = [t for s,t in sorted(topics, reverse=True)[:2]]
        ext = [u for u in (o.get('external_link') or []) if 'google.co.jp/search' not in u and 'google.com/search' not in u]
        rec = {'q': o['wikibase_item'], 'red': [r['title'] for r in (o.get('redirect') or []) if r.get('namespace')==0][:50],
               'ext': len(ext), 'maint': maint, 'info': info[0] if info else None, 'coord': coord, 'topic': topics,
               'heads': [h for h in (o.get('heading') or []) if not SKIPH.match(h)][:12], 'ct': (o.get('create_timestamp') or '')[:10], 'ts': (o.get('timestamp') or '')[:10]}
        out2.write(json.dumps(rec, ensure_ascii=False)+'\n')
        n += 1
print(n)
