# ランダム（初期表示・ランダムボタン・おまかせ）に出さない記事を選ぶ。
#   性的な内容の記事。対戦から外すわけではなく、自分で名前を入れれば選べる。
#   性的指向・LGBT・医学一般は対象にしない。言葉の一部だけが一致する誤検出（サセックス、ピエロ、官能基 など）は避ける。
#   python3 tools/norand.py data  → data/norand.json（記事名の一覧）
import json, gzip, glob, re, os, sys
D = sys.argv[1] if len(sys.argv) > 1 else 'data'
K = r'(?<![ァ-ヶー])'   # 直前がカタカナでない（「サセックス」「ピエロ」などを避ける）
# 分類（Wikidataの種類）・カテゴリ・職業やジャンルに、これが含まれていたら外す
META = re.compile(r'AV女優|AV男優|ポルノ|アダルトゲーム|アダルトアニメ|アダルトビデオ|アダルト映画|成人向け|成人映画|ピンク映画|官能小説|エロゲ|エロ漫画|エロアニメ|エロ本|'
                  r'性風俗|風俗店|風俗嬢|ソープランド|売春|買春|援助交際|BDSM|フェティシズム|性行為|性交|近親相姦|性具|ストリップティーズ|ストリップ劇場|ストリッパー|'
                  r'ヌード写真|セクシー女優|' + K + r'セックス(?![ァ-ヶ])')
# 記事名に、これが含まれていたら外す
TITLE = re.compile(r'性交|体位|射精|自慰|オナニー|マスターベーション|フェラチオ|クンニ|獣姦|潮吹き|性具|バイブレータ|張形|アナル(?!ログ|ライ|ゴ)|オーガズム|'
                   r'陰茎|陰核|陰唇|陰部|陰毛|恥丘|膣|精液|乳首|性感|ペニスバンド|ラブホテル|ソープランド|売春|買春|援助交際|ポルノ|アダルト|AV女優|AV男優|18禁|'
                   r'成人映画|ピンク映画|性風俗|フェティシズム|BDSM|SMプレイ|エロゲ|エロ漫画|エロ本|官能小説|セクシー女優|' + K + r'セックス(?![ァ-ヶ])|' + K + r'エロ(?![ァ-ヶーイスン])')
IGNORE = re.compile(r'ロマンポルノ|ポルノグラフィティ')   # 映画史の一ジャンル・バンド名なので、手がかりにしない
ALLOW = {'ポルノグラフィティ', 'セックス・ピストルズ', 'Fate/stay night'}   # 一般に広く知られていて、ランダムに出ても差し支えないもの
out = []
for f in sorted(glob.glob(os.path.join(D, 'a', '*.json.gz'))):
    for t, r in json.loads(gzip.open(f).read()).items():
        if t in ALLOW: continue
        g = r.get('gen', {})
        meta = [g.get('c') or ''] + list(g.get('cc', [])) + [x for e in r.get('ext', []) if e[0] != '_m' and isinstance(e[2], list) for x in e[2] if isinstance(x, str)]
        sig = {m for m in meta if META.search(m) and not IGNORE.search(m)}
        # 人物は、手がかりが2つ以上あるときだけ（過去に一度だけ関わった俳優などを外さないため）
        if TITLE.search(t) or len(sig) >= (2 if r.get('p') else 1): out.append(t)
out.sort()
json.dump(out, open(os.path.join(D, 'norand.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('ランダムに出さない記事', len(out))
