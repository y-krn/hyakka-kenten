# 百科ダンジョンの「宝の扉」に入る記事の一覧（武器になる物・食べ物）を作る
#   収録データの分類（gen.c）から、手に持てる物を「w」、食べ物を「f」にする。1年間の閲覧数が2万以上の、よく知られた記事だけ
#   python3 tools/build_dgitems.py data  → data/dgitems.json  [[記事名, 種類（w/f）, 分類], ...]（閲覧数の多い順）
import json, gzip, glob, re, os, sys
D = sys.argv[1] if len(sys.argv) > 1 else 'data'
W = re.compile(r'刀|剣|槍|弓|銃|砲|武器|兵器|斧|ナイフ|ハンマー|ミサイル|戦車|爆弾|棍|鎌|盾|鎧|甲冑|手裏剣|鞭|弾薬|鈍器|道具|工具|器具|楽器|機械|装置|自動車|車両|航空機|艦|船|家具|衣服|衣類|帽子|靴|スポーツ用品|玩具|おもちゃ|文房具|食器|家電|カメラ|時計|電話|鞄|傘')
FD = re.compile(r'料理|食品|食べ物|菓子|麺|飲料|飲み物|酒|果物|果実|野菜|パン|丼|寿司|茶|コーヒー|スープ|ラーメン|カレー|うどん|蕎麦|そば|調味料|チーズ|食材|和菓子|洋菓子|デザート|グルメ|主食|ご当地')
NG = re.compile(r'ヒト|人物|企業|会社|ブランド|店|番組|曲|アルバム|映画|作品|漫画|小説|ゲーム|雑誌|キャラクター|チェーン|製造|メーカー|者$|団体|組織|施設|駅|路線|産業|工場|博物館|リーグ|チーム|連隊|部隊|クラブ|大会|機能クラス')
NR = set(json.load(open(os.path.join(D, 'norand.json')))) if os.path.exists(os.path.join(D, 'norand.json')) else set()
out = []
for f in sorted(glob.glob(os.path.join(D, 'a', '*.json.gz'))):
    for t, r in json.loads(gzip.open(f).read()).items():
        if r.get('hold') or t in NR or r.get('p'): continue
        c = (r.get('gen') or {}).get('c') or ''
        if not c or NG.search(c): continue
        k = 'w' if W.search(c) else 'f' if FD.search(c) else None
        if not k: continue
        m = next((e for e in r.get('ext', []) if e[0] == '_m'), None); pv = (m[5] or 0) if m else 0
        if pv >= 20000: out.append((pv, t, k, c))
out.sort(key=lambda x: (-x[0], x[1]))
json.dump([[t, k, c] for _, t, k, c in out], open(os.path.join(D, 'dgitems.json'), 'w'), ensure_ascii=False, separators=(',', ':'))
print('宝の扉の記事', len(out), '（武器になる物', sum(1 for x in out if x[2] == 'w'), '・食べ物', sum(1 for x in out if x[2] == 'f'), '）')
