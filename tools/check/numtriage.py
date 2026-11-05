# 数字の照合で「読み取り不確か」になった項目を、規則でふるい分ける
#   1. 書かれた数字のどれかが（単位を直せば）Wikidata と合う → 問題なし（何もしない）
#   2. 型の決まった書き方（中国の都市の万人書き、川の延長はkm、絵画の height はcm、車両の全高はmm、ft/in・lb の変換テンプレート）→ 日本語版の値に合わせる候補
#   3. 残りは、よく読まれている順に目で確かめる
#   使い方: python3 tools/check/numtriage.py 出力.jsonl 照合結果1.jsonl ...   → 出力.jsonl を tools/fixa_build.py に照合結果と一緒に渡す
import json,re,collections,sys
R=[json.loads(l) for f in sys.argv[2:] for l in open(f, encoding='utf-8')]
U=[r for r in R if r['st']=='読み取り不確か']
SC=[1,10,100,1000,1e4,1e5,1e6,1e8,0.1,0.01,0.001,1e-4,1e-6,0.3048,3.048e-4,1.852,0.0254,2.54e-5,1.609,0.4536,1e-3*0.4536]
def nums(raw): return [float(x.replace(',','')) for x in re.findall(r'\d[\d,]*(?:\.\d+)?',raw or '')]
def best(r,tol):
    wd=r['wd']
    if not wd: return None
    for n in nums(r.get('raw')):
        for sc in SC:
            if abs(n*sc-wd)/abs(wd)<=tol: return n*sc
    return None
out=collections.Counter(); rest=[]
for r in U:
    if r['why']=='天体の単位': r['tri']='そのまま（天体の単位）'
    elif best(r,0.005) is not None: r['tri']='問題なし（一致）'
    elif best(r,0.15 if r['k']=='p' else 0.05) is not None: r['tri']='問題なし（小さな差）'
    else: r['tri']='要確認'; rest.append(r)
    out[r['tri']]+=1
print(out)
c=collections.Counter(r['why'] for r in rest); print(c)
R=sorted(rest,key=lambda r:-r['pv'])

def num(raw):
    m=re.match(r'\s*[~約≈]?\s*(\d[\d,]*(?:\.\d+)?)\s*$', raw or ''); return float(m.group(1).replace(',','')) if m else None
def near(a,b,t): return b and abs(a-b)/abs(b)<=t
fixes=[]; st=collections.Counter(); left=[]
for r in R:
    raw=(r.get('raw') or '').strip(); f=(r.get('field') or ''); k=r['k']; wd=r['wd']; n=num(raw); done=None
    # A. 中国などの「万人」書き（population_total が小さい数）
    if k=='p' and n is not None and n<1e5 and wd>1e5 and 0.5<= n*1e4/wd <=2: done=('合わせる',n*1e4,'万人単位')
    # B. 指数表記 (9.393 ± 0.005)e20 kg
    elif re.search(r'e\d+', raw) and not re.search(r"''M''|M\s*[E⊕J☉]", raw):
        m=re.search(r'\(?\s*(\d+(?:\.\d+)?)\s*(?:±\s*[\d.]+)?\s*\)?\s*[e×]\s*10?\^?(\d+)', raw)
        if m:
            v=float(m.group(1))*10**int(m.group(2)); done=('問題なし',None,'指数表記') if near(v,wd,0.05) else None
    # C. 川・山脈などの「延長」（単位なしは km）
    if not done and f in ('延長','length','長さ') and n is not None and k=='l' and n>=1 and 0.33<=n/wd<=3: done=('合わせる',n,'延長はkm')
    # D. 絵画など height（単位なしは cm）／ 車両の全高（単位なしは mm）
    if not done and k=='h' and n is not None:
        if f=='height' and 0.33<= (n/100)/wd <=3: done=('合わせる',n/100,'heightはcm')
        elif f in ('全高','高さ') and n>=500 and 0.5<=(n/1000)/wd<=2: done=('合わせる',n/1000,'全高はmm')
    # E. 身長・体重の変換テンプレート
    if not done:
        m=re.search(r'\{\{フィートとcm[^|]*\|(\d+)\|(\d+)', raw)
        if m: v=(int(m.group(1))*12+int(m.group(2)))*0.0254; done=('問題なし',None,'ft/in') if near(v,wd,0.02) else ('合わせる',round(v,2),'ft/in')
        m=re.search(r'\{\{ポンドとkg[^|]*\|(\d+)', raw)
        if m: v=int(m.group(1))*0.4536; done=('問題なし',None,'lb') if near(v,wd,0.02) else ('合わせる',round(v,1),'lb')
    # F. 複数の値・別のテンプレートから数字を引くもの・天体の単位：Wikidata のまま
    if not done and re.search(r'plainlist|ubl|自治体人口|自治体面積|UN_Population|Population GER|solar mass|#expr', raw, re.I): done=('そのまま',None,'テンプレート')
    if done: st[done[0]]+=1; r['tri']=done; 
    else: left.append(r)
    if done and done[0]=='合わせる': fixes.append({**r,'st':'食い違い','jp':done[1],'raw':raw+' 〔'+done[2]+'〕'})
print(st, '残り', len(left)); print(collections.Counter(r['why'] for r in left))
json.dump(left,open(sys.argv[1]+'.left.json','w',encoding='utf-8'),ensure_ascii=False)   # 残り（よく読まれている順）。上のほうを目で確かめて、必要なら data/fix.json へ
with open(sys.argv[1],'w',encoding='utf-8') as fo:
    for x in fixes: fo.write(json.dumps(x,ensure_ascii=False)+'\n')
