# アルバムなどの記事の「〜の一部」の召喚相手が、歌手のアルバム一覧（「◯◯の時系列順のアルバム」「◯◯のディスコグラフィ」）のとき、
# 歌手本人の記事に差し替える（一覧の記事は選手から外しているので、技の中でも一覧が駆けつけないようにする）
#   ・一覧の名前から歌手名（◯◯）を取り出し、収録されている記事のうち、音楽の分類（歌手・バンド・音楽グループなど）か人（ヒト）のものだけに差し替える
#   ・同じ名前の人が何人もいるときは、括弧のない名前（いちばん知られている人）を選ぶ。括弧に音楽の言葉がある記事（「UA (歌手)」など）があれば、そちらを選ぶ
#   ・決めきれない（同じ名前のバンドが2つある など）・収録されていないときは、そのままにする
#   ・技の名前（親分召喚）・種類・威力は変えない。召喚相手の名前・説明・番号と、事実の表の文（「アーティスト：◯◯」）だけを変える
# 使い方: python3 tools/artist_summon.py   （data/a/*.json.gz を書き換える。何度動かしても同じ結果）
import gzip, glob, json, re, collections
ex = set(json.load(open('data/exclude.json', encoding='utf-8')))
files = sorted(glob.glob('data/a/*.json.gz'))
info, base = {}, collections.defaultdict(list)
for f in files:
    for t, rec in json.loads(gzip.open(f).read().decode('utf-8')).items():
        if t in ex: continue
        info[t] = (rec['f'][2], (rec.get('gen') or {}).get('c') or '', rec['f'][1])
        m = re.match(r'^(.+?) \((.+)\)$', t)
        if m: base[m.group(1)].append(t)
MUS = re.compile(r'歌手|バンド|グループ|ユニット|デュオ|ミュージシャン|音楽|作曲家|シンガー|アーティスト|ラッパー|アイドル|演奏家|ピアニスト|ギタリスト|オーケストラ|楽団|合唱|DJ|ボーカリスト|アンサンブル')
PAT = re.compile(r'^(.+?)の(?:(?:シングル|アルバム)の)?(?:時系列順のアルバム|ディスコグラフィー?)$')
def resolve(x):
    ok = [t for t in [x] + base.get(x, []) if t in info and (MUS.search(info[t][1]) or info[t][1] == 'ヒト')]
    mus = [t for t in ok if t != x and MUS.search(t[len(x):])]   # 括弧に音楽の言葉がある記事
    if len(mus) == 1: return mus[0]
    if x in ok and not mus: return x
    return ok[0] if len(ok) == 1 else None
cache, n_mv, n_files = {}, 0, 0
for f in files:
    raw = gzip.open(f).read().decode('utf-8'); d = json.loads(raw); changed = False
    for t, rec in d.items():
        F = rec['f']
        for mv in F[7]:
            if mv[0] != 'SUMMON' or mv[1] != '親分召喚': continue
            m = PAT.match(mv[2])
            if not m: continue
            if mv[2] not in cache: cache[mv[2]] = resolve(m.group(1))
            a = cache[mv[2]]
            if not a: continue
            q, _, disp = info[a]
            oldq = [x[2] for x in mv[7]] if len(mv) > 7 and isinstance(mv[7], list) else []
            mv[2], mv[3] = disp, 'アーティスト：' + disp
            if len(mv) > 7: mv[7] = [[a, '', q]]
            if isinstance(F[-1], list): F[-1] = [q if x in oldq else x for x in F[-1]]   # 「〜の一部」の番号の一覧（相手がその一員か、仲間図鑑）も歌手にそろえる
            n_mv += 1; changed = True
    if changed:
        n_files += 1
        with open(f, 'wb') as fo, gzip.GzipFile(fileobj=fo, mode='wb', compresslevel=9, mtime=0) as w: w.write(json.dumps(d, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
print(f'差し替えた召喚 {n_mv}（ファイル {n_files}）、歌手 {len([v for v in cache.values() if v])}、差し替えなかった一覧 {len([v for v in cache.values() if not v])}')
