import json,sqlite3,glob,collections
db=sqlite3.connect('full/ents.db')
def ids(e,p):
    return [s['mainsnak']['datavalue']['value']['id'] for s in (e.get('c') or {}).get(p,[]) if s.get('mainsnak',{}).get('datavalue') and isinstance(s['mainsnak']['datavalue'].get('value'),dict) and 'id' in s['mainsnak']['datavalue']['value']]
main={}; 
for f in sorted(glob.glob('all/arts_*.jsonl')):
    for l in open(f):
        a=json.loads(l)
        if a['disamb'] or a['t'].endswith('一覧'): continue
        main[a['q']]=a['pop']
print('main',len(main))
p31=collections.Counter(); persons=[]
cur=db.cursor(); qs=list(main)
for i in range(0,len(qs),900):
    for q,j in cur.execute('select id,j from e where id in (%s)'%','.join('?'*len(qs[i:i+900])),qs[i:i+900]):
        e=json.loads(j); c=ids(e,'P31')
        if 'Q5' in c: persons.append((main[q],q))
        else:
            for x in set(c): p31[x]+=1
T=[q for q in p31 if q in main]
print('typeTargets',len(T),'persons',len(persons))
persons.sort(reverse=True)
json.dump({'types':T,'persons':[q for _,q in persons]},open('full/targets.json','w'))
