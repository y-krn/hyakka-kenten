# データの作り方（メモ）

1. `extract_all.py`：Wikimediaの検索用データ（cirrus_search_index, jawiki_content）の各区画から、記事ごとの数量と補助情報を取り出す
2. `fetch_all.js` / `fetch_aux.js`（`wm_vm.js` を使用）：Wikidataから項目と、種類ごとの項目数・人物の作品数を取る（区切って実行、続きから再開できる）
3. `mkdb.py`：取った項目をSQLiteにまとめる
4. `targets.py`：補助データの検索対象を決める
5. `prep_full.py`（`GEN=1` で `gen_v2.js` / `gen5.js` も実行）：区画ごとに能力値と技を作る
6. `rv_global.py`：因縁（記事どうしの直接の関係）を全体で作る
7. `build_full.py`：公開用の `data/`（記事名のハッシュで4096個に分けた gzip ファイル）を作る
8. `mk_site.py`：試作ページ（`page_src.html`）から公開用の `index.html` を作る

Wikimedia APIへの問い合わせには、連絡先（このリポジトリの持ち主のGitHub）を含むUser-Agentを付けています。
