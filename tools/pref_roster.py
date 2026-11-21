#!/usr/bin/env python3
# 都道府県の応援：選手の一覧（data/pref/roster.json）を作る
#   使い方: python3 tools/pref_roster.py <Wikidataの取得データのフォルダ（ents/*.jsonl があるところ）>
#   都道府県の決め方
#     人物 … 出生地（P19）から、所在地（P131）を都道府県までたどる
#     それ以外 … 記事自身の所在地（P131・P276）から都道府県までたどる。県境をまたぐものは関係する県すべてに入る
#     旧国名（土佐国など）は、今の県に読み替える
#   種類（人物・名所・自然・名物・文化）は、記事の分類（Wikidata の P31）で決める
#   並べ方：閲覧数に、被リンク数と記事の長さを混ぜた点数（一時的に読まれた記事が上に来すぎないように）
#   外すもの：扱わない記事（exclude/norand）、data/pref/ng.json、現職の可能性がある政治家（職業が政治家で1930年以降に生まれ、没年がない人）
#   手直し：data/pref/fix.json（add＝足す、drop＝外す）
import json, gzip, os, sys, re, math, glob, collections
PREF="北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県".split()
CITY={'札幌市':'北海道','仙台市':'宮城県','さいたま市':'埼玉県','千葉市':'千葉県','横浜市':'神奈川県','川崎市':'神奈川県','相模原市':'神奈川県','新潟市':'新潟県','静岡市':'静岡県','浜松市':'静岡県','名古屋市':'愛知県','京都市':'京都府','大阪市':'大阪府','堺市':'大阪府','神戸市':'兵庫県','岡山市':'岡山県','広島市':'広島県','北九州市':'福岡県','福岡市':'福岡県','熊本市':'熊本県'}
KUNI={'土佐国':'高知県','阿波国':'徳島県','讃岐国':'香川県','伊予国':'愛媛県','薩摩国':'鹿児島県','大隅国':'鹿児島県','日向国':'宮崎県','肥後国':'熊本県','豊後国':'大分県','筑前国':'福岡県','筑後国':'福岡県','肥前国':'佐賀県','長門国':'山口県','周防国':'山口県','安芸国':'広島県','備後国':'広島県','備前国':'岡山県','備中国':'岡山県','美作国':'岡山県','出雲国':'島根県','石見国':'島根県','隠岐国':'島根県','因幡国':'鳥取県','伯耆国':'鳥取県','播磨国':'兵庫県','但馬国':'兵庫県','淡路国':'兵庫県','山城国':'京都府','丹後国':'京都府','大和国':'奈良県','河内国':'大阪府','和泉国':'大阪府','紀伊国':'和歌山県','近江国':'滋賀県','伊勢国':'三重県','伊賀国':'三重県','志摩国':'三重県','尾張国':'愛知県','三河国':'愛知県','美濃国':'岐阜県','飛騨国':'岐阜県','駿河国':'静岡県','遠江国':'静岡県','伊豆国':'静岡県','甲斐国':'山梨県','信濃国':'長野県','越後国':'新潟県','佐渡国':'新潟県','越中国':'富山県','加賀国':'石川県','能登国':'石川県','越前国':'福井県','若狭国':'福井県','相模国':'神奈川県','安房国':'千葉県','上総国':'千葉県','下総国':'千葉県','常陸国':'茨城県','上野国':'群馬県','下野国':'栃木県','琉球王国':'沖縄県','琉球国':'沖縄県','蝦夷地':'北海道','平安京':'京都府','首里':'沖縄県'}
B_NAT=set('山 川 島 湖 火山 成層火山 活火山 山脈 岬 半島 湾 高原 峠 滝 島嶼群 日本の国立公園 国定公園 海峡 砂丘 渓谷 湿原 カルデラ 洞窟 鍾乳洞 海岸 干潟 池 沼 平野 盆地 カルデラ湖'.split())
B_CUL=set('まつり 祭り 郷土料理 料理 菓子 和菓子 食品 麺料理 ご当地キャラクター マスコット 伝統工芸品 工芸品 品種 日本酒 焼酎 ラーメン 民謡 踊り 年中行事 方言 ブランド 伝統芸能'.split())
# 補強（2026-11）：郷土の言い伝え・行事・特産の分類も名物・文化に入れる
B_CUL |= set('妖怪 化け狸 鬼 怪火 怪談 民話 民間信仰 神事 花火大会 ねぶた ダンスの種類 地域ブランド 地域団体商標 ご当地グルメ 食物 野菜 煮物 魚醤 珍味 ふりかけ 魚肉練り製品 デモニム'.split())
XC=re.compile('戦闘|戦役|の乱|一揆|事変|クーデター|反乱|謀反|演習|メーカー|製造|出版社|放送事業者|事務所|プロダクション|校|株式会社|競走|大会|都道府県|モノレール|リーグ|球団|シーズン|学校|学園|大学|カレッジ|駅|道路|街道|インターチェンジ|ジャンクション|パーキング|サービスエリア|道の駅|町丁|大字|字$|廃止|郡|選挙区|病院|企業|会社|鉄道|路線|系統|バス|営業所|警察|裁判所|検察|刑務所|駐屯地|基地|飛行場|空港|車両|信号場|ヤード|組織|政党|地区|地域|集落|街路|トンネル|研究所|図書館|ウマ|藩|支庁|官庁|役所|事業者|放送局|団体|チーム|クラブ|列車|停留場|港湾|ショッピング|商業|百貨店|ホテル|オフィス|銀行|工場|発電所|変電所|ダム|浄水|処分場|住宅|団地|墓|霊園|事件|事故|災害|戦い|合戦|戦争|慰霊|米軍|海兵隊|原子力|再処理|記念碑|地震|噴火|津波|台風|豪雨|空襲|爆発|火災|仇討|征伐|幕府|政府|博覧会')
CUL=re.compile('料理|寿司|菓子|麺|餅|鍋|丼|焼き|漬|茶|日本酒|焼酎|ワイン|ビール|牛|豚|鶏|魚介|果物|柑橘|梨|ブドウ|品種|米|味噌|醤油|祭|まつり|踊|神楽|舞|行事|芸能|工芸|焼き物|陶|磁器|織物|染|漆|人形|ご当地キャラクター|ゆるキャラ|マスコット|アイドルグループ|方言|民謡|食品|調味料|ラーメン|うどん|そば|カレー|スナック|駄菓子')
MYTH=re.compile('伝説上の人物|架空かもしれない人間|神話上の人物|日本の神|架空の人物')
PLX=re.compile('攻城戦|私鉄|方面隊|指数|市街地|島$|都道府県')
# 名物・文化から外すもの：新しい催し（映画祭・フェスティバル・展示会など）と博物館。伝統の祭り・行事は残す
MODERN = re.compile('映画祭|映像|フェスティバル|フェス$|フェア$|ショー|EXPO|エキスポ|コンテスト|グランプリ|マラソン|大会|ラリー|電車まつり|[A-Za-z]{2,}まつり|小径|肉祭|グルメ|B-1|サミット|コレクション|博$|館$')
EVC = re.compile('^(イベント|定期行事|映画祭|展覧会|博覧会|興行|ロック・フェスティバル|同人誌即売会|音楽祭|見本市|フェスティバル)$')
TRAD = re.compile('祭|まつり|踊|神事|花火|神楽|山笠|くんち|ねぶた|ねぷた|囃子|念仏')
MUSE = re.compile('博物館|美術館|資料館|記念館|館$')
def kind(c, t):
    if c == '日本語の方言' or re.search('(弁|方言|言葉|ことば|標準語)$', t): return '方言'
    return c or ''
PREF = PREF.split() if isinstance(PREF, str) else PREF
TOP = 30
RAW = sys.argv[1]
POLI = {'Q82955', 'Q486839', 'Q1055894', 'Q193391'}   # 政治家・国会議員・地方議員・外交官 … 職業がこれらで存命なら外す
def ids(cl, p):
    out = []
    for s in (cl or {}).get(p, []) or []:
        if s.get('rank') == 'deprecated': continue
        v = ((s.get('mainsnak') or {}).get('datavalue') or {}).get('value')
        if isinstance(v, dict) and v.get('id'): out.append((s.get('rank'), v['id']))
    pref = [q for r, q in out if r == 'preferred']   # 「推奨」があればそれだけ（今の所在地）
    return pref or [q for r, q in out]
# 1) 取得データから、たどるのに要る部分だけを読む
E = {}
for f in sorted(glob.glob(os.path.join(RAW, 'ents', '*.jsonl'))):
    for l in open(f, encoding='utf-8'):
        e = json.loads(l); cl = e.get('c') or {}
        E[e['id']] = (ids(cl, 'P31'), ids(cl, 'P131') or ids(cl, 'P276'), ids(cl, 'P19'), ids(cl, 'P106'), 'P570' in cl, (e.get('l') or {}).get('ja') or '')
print('項目', len(E), file=sys.stderr)
PQ = {}
for q, v in E.items():
    if 'Q50337' in v[0] and v[5] in PREF: PQ[q] = v[5]   # 日本の都道府県
for q, n in (('Q1490', '東京都'), ('Q1037393', '北海道')): PQ.setdefault(q, n)
print('都道府県の項目', len(PQ), file=sys.stderr)
memo = {}
def prefs_of(q, depth=0):
    if q in PQ: return {PQ[q]}
    if q in memo: return memo[q]
    if depth > 7: return set()
    memo[q] = set()
    v = E.get(q); out = set()
    if v:
        if v[5] in KUNI: out = {KUNI[v[5]]}
        else:
            for x in v[1]: out |= prefs_of(x, depth + 1)
            if len(out) > 1: out = set()   # 途中の場所が複数の県にまたがる（「山陰地方」など）なら、そこからはたどらない
    memo[q] = out
    return out
# 都道府県名で始まるカテゴリ（「岡山県の郷土料理」など）。所在地を持たない名物・祭りの手がかりにする
PRX = re.compile('^(' + '|'.join(PREF) + ')(の郷土料理|の食文化|の祭り|の伝統工芸品|の銘菓|のご当地キャラクター|の民謡|の方言|の伝統芸能|の年中行事|の無形民俗文化財|の文化(?!財|施設|団体|人|賞)|の土産菓子|の麺料理|の花火大会|の妖怪|の行事・イベント|の地域ブランド)')
def bucket(c, co):
    if c == 'ヒト' or MYTH.search(c or ''): return '人物'
    if c in B_NAT: return '自然'
    if (c in B_CUL or CUL.search(c or '')) and not XC.search(c or ''): return '名物・文化'
    if c and (c.endswith('区') or c in ('日本の市', '日本の町', '日本の村', '中核市', '特例市', '政令指定都市', '特別区')): return None   # まちは選手にしない
    if co and c and not XC.search(c) and not PLX.search(c): return '名所'
    return None
def load(p):
    o = json.load(open(p, encoding='utf-8')); return set(o if isinstance(o, list) else o)
EX = load('data/exclude.json') | load('data/norand.json')
NG = set(json.load(open('data/pref/ng.json', encoding='utf-8'))['記事'])
FIX = json.load(open('data/pref/fix.json', encoding='utf-8'))
# 2) 収録記事ごとに、都道府県と種類と点数を決める
R = collections.defaultdict(lambda: collections.defaultdict(list)); cnt = collections.Counter()
for fn in sorted(os.listdir('data/a')):
    for t, r in json.load(gzip.open(os.path.join('data/a', fn))).items():
        if t in EX or t in NG or t in FIX.get('drop', []): continue
        g = r.get('gen') or {}; f = r['f']; q = f[2]; c = g.get('c', '')
        b = bucket(c, g.get('co'))
        ccp = {m.group(1) for m in (PRX.match(x) for x in g.get('cc') or []) if m}
        if not b and ccp and not XC.search(c or ''): b = '名物・文化'
        if not b or b == '名所' and re.search('鉄道|学校|高等学校|大学|中学校|小学校|駅伝|選挙', t): continue
        if b == '名物・文化' and (MODERN.search(t) or EVC.search(c or '') and not TRAD.search(t) or MUSE.search(c or '')): continue   # 新しい催し・博物館は名物にしない（伝統の祭りは残す）
        if b == '名物・文化' and re.search('検定|学校|協議会|プロジェクト|委員会|実行委員|協会|組合|賞$|一覧|^.{1,3}県の', t): continue   # 名物・文化に紛れる、試験・団体・一覧など
        v = E.get(q)
        if not v: cnt['取得データなし'] += 1; continue
        if b == '人物':
            ps = set()
            for x in v[2]: ps |= prefs_of(x)
            by = f[8] if len(f) > 8 and isinstance(f[8], int) else None
            if POLI & set(v[3]) and not v[4] and (by is None or by >= 1930): cnt['政治家として外した'] += 1; continue
        else:
            ps = set()
            for x in v[1]: ps |= prefs_of(x)
            if len(ps) > 4: ps = set()
            if not ps and ccp:
                if len(ccp) > 1: continue   # 所在地がなく、いくつもの県のカテゴリにあるもの（ふつうの「ちゃんぽん」など）は、どこの名物とも言えない
                ps = ccp
                if b == '名所': b = '名物・文化'
        if not ps: continue
        m = next((e for e in r.get('ext') or [] if e[0] == '_m'), [0] * 6)
        pv, ln, bl = (m[5] if len(m) > 5 else 0), (m[2] if len(m) > 2 else 0), (m[3] if len(m) > 3 else 0)
        sc = math.log10(pv + 1) + 0.7 * math.log10(bl + 1) + 0.4 * math.log10(ln + 1)
        cnt[b] += 1
        if len(ps) > 1: cnt['複数の県'] += 1
        for p in ps: R[p][b].append((sc, t, kind(c, t)))
# 3) 手直しを足して、上位を残す
for t, a in (FIX.get('add') or {}).items():
    for p in a['都道府県']:
        if all(t != x[1] for x in R[p][a['種類']]): R[p][a['種類']].append((99, t, '手直し'))
def pick(xs):   # 同じ種類が並びすぎないように：方言は1つまで、ほかの分類は3つまで
    out, n = [], collections.Counter()
    for sc, t, k in sorted(xs, reverse=True):
        if k and n[k] >= (1 if k == '方言' else 3): continue
        n[k] += 1; out.append(t)
        if len(out) >= TOP: break
    return out
out = {p: {b: pick(R[p][b]) if b == '名物・文化' else [t for _, t, _ in sorted(R[p][b], reverse=True)[:TOP]] for b in ('人物', '名所', '自然', '名物・文化') if R[p][b]} for p in PREF}
os.makedirs('data/pref', exist_ok=True)
json.dump(out, open('data/pref/roster.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
# サーバー用：記事名 → 代表になっている県（PREF の並びの番号）の対応表。記事名のハッシュで64個に分け、サーバーは要る分だけ読む
#   ハッシュは FNV-1a（32ビット）を記事名の文字（コードポイント）ごとに。Worker の prefShard と同じ計算
def shard(t):
    h = 2166136261
    for ch in t: h = ((h ^ ord(ch)) * 16777619) & 0xffffffff
    return h % 64
MAP = [dict() for _ in range(64)]
for i, p in enumerate(PREF):
    for L in out[p].values():
        for t in L:
            v = MAP[shard(t)].setdefault(t, [])
            if i not in v: v.append(i)
os.makedirs('data/pref/map', exist_ok=True)
for k, m in enumerate(MAP): json.dump(m, open('data/pref/map/%02d.json' % k, 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
# 共有カード用：県ごとに、種類ごとの1位の代表（サーバーが ?pref=県名 のページの説明文に使う）
json.dump({p: {b: L[0] for b, L in out[p].items() if L} for p in PREF}, open('data/pref/card.json', 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
print(dict(cnt))
print('種類ごとの最少', {b: min((len(R[p][b]), p) for p in PREF) for b in ('人物', '名所', '自然', '名物・文化')})
for p in PREF:
    print(p, '｜'.join(b + '：' + '、'.join(out[p].get(b, [])[:4]) for b in ('人物', '名所', '自然', '名物・文化')))
