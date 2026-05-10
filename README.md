# 一宮市 学校給食レシピアプリ

一宮市公式サイトで公開されている学校給食レシピ（PDF）を収集・解析し、スマホ・PCのブラウザで簡単に検索・閲覧できるWebアプリです。

レシピ提供：[一宮市教育委員会](https://www.city.ichinomiya.aichi.jp/kyouiku/gakkoukyuushoku/1000162/1001639.html)

## 起動方法（macOS）

`start.command` をダブルクリックすると、ローカルサーバーが起動して既定のブラウザでアプリが開きます。

または、ターミナルから:

```bash
cd ichinomiya_recipes/app
python3 -m http.server 8765
# ブラウザで http://localhost:8765/index.html を開く
```

ビルド作業は不要です（バニラHTML/CSS/JSのみ）。

## 機能

- **レシピ一覧**：カード形式で表示。カテゴリーアイコン付き
- **検索**：料理名・材料・本文で全文検索（空白区切りでAND検索）
- **カテゴリーフィルター**：汁物 / 煮物・いため物・丼物 / 揚げ物 / 焼き物 / 和え物 / ソース など
- **お気に入り**：右上の星ボタンで切り替え。LocalStorageに保存
- **レシピ詳細**：材料表・作り方ステップ・メモ・元のPDFリンク
- **📅 献立表マッチング**：「今日食べた○○がおいしかった」を解決する機能。
  - 右上の📅ボタンで開く
  - 日付・学校種別・食材キーワード（例：「ほうれん草 コーン」）から、その日に出た料理名を特定
  - 該当レシピが収録されていれば「レシピを見る」ボタンでワンクリック移動
  - 食材名は同義語自動展開（コーン↔とうもろこし、ほうれん草↔ほうれんそう など）
  - 過去 1 年分の献立データ（約 380 日分・約 1,900 品）を内蔵
- **レスポンシブデザイン**：スマホファースト
- **オフライン動作**：ファイル一式をホストすればCDN等に依存せず動作

## ディレクトリ構成

```
ichinomiya_recipes/
├── app/                    # 配布用Webアプリ（このフォルダごと配置すれば動く）
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   ├── data.js             # 118 件のレシピデータ（埋め込み）
│   └── menus.js            # 約 380 日分の献立データ（埋め込み）
├── data/
│   ├── index.html          # 元の一宮市ページ（取得時のスナップショット）
│   ├── pdf_list.json       # 抽出した PDF メタデータ一覧
│   ├── pdf_list.tsv
│   ├── recipes.json        # 解析後の構造化レシピデータ
│   ├── menu_pdf_list.json  # 献立表PDFメタデータ
│   └── menu_days.json      # 日別献立データ（学校種別×地域×日付）
├── downloads/
│   ├── recipes/            # レシピPDF（118 件）
│   └── menus/              # 献立表PDF（55 件）
├── scripts/                # 収集・解析スクリプト
│   ├── extract_pdf_list.py
│   ├── download_pdfs.py
│   ├── parse_pdfs.py
│   ├── download_menus.py
│   ├── parse_menus.py
│   └── build_data_js.py
├── start.command           # ダブルクリックで起動（macOS）
└── README.md
```

## データ更新フロー

新しいレシピがアップされたとき、データを更新するには：

```bash
# 1. 最新ページを取得
curl -L -A "Mozilla/5.0" \
  "https://www.city.ichinomiya.aichi.jp/kyouiku/gakkoukyuushoku/1000162/1001639.html" \
  -o data/index.html

# 2. PDFリストを抽出
python3 scripts/extract_pdf_list.py

# 3. 新しいPDFをダウンロード（既存のものはスキップ）
python3 scripts/download_pdfs.py

# 4. 解析してJSON生成
python3 scripts/parse_pdfs.py

# 5. 献立表PDFを取得・解析（毎月更新するなら）
python3 scripts/download_menus.py
python3 scripts/parse_menus.py

# 6. アプリ用データを生成
python3 scripts/build_data_js.py
```

## 解析品質について

118 件のうち **107 件 (約 91%)** で材料・作り方が完全に構造化されています。

残り 11 件は以下の理由で部分解析または未解析:
- **画像のみのPDF (5件)** — テキストレイヤーがないため抽出不可。元のPDFリンクから閲覧してください
- **多段組み・特殊レイアウト (約6件)** — 材料は取得できるが手順の順序が崩れる場合があります

すべてのレシピで「元のPDFを開く」ボタンが利用できます。

## デプロイ

`app/` フォルダの内容を任意の静的ホスティングにアップロードするだけでOKです：
- Vercel: `app` ディレクトリをそのまま `vercel deploy --prod`
- Netlify: ドラッグ&ドロップ
- GitHub Pages: `app/` をリポジトリのルートに配置
- 自前のWebサーバー: `app/` 以下を公開ディレクトリに置く

ビルドステップ・サーバーサイド処理は不要です。

## 注意事項

- レシピは一宮市教育委員会の著作物です。再配布する場合は出典を明記してください
- 分量は学校給食用です。家庭で作る際は人数や好みに合わせて調節してください
- スクレイピング時は適度な間隔（500ms）を空けて公式サイトに負担をかけないよう配慮しています

## 今後の拡張予定

- [x] ~~**献立表マッチング機能**~~（実装済み）
- [ ] **PWA化**：ホーム画面追加・オフライン対応
- [ ] **画像PDFのOCR**：未解析の5件をテキスト化
- [ ] **家庭用分量への換算機能**
- [ ] **同義語辞書の拡充**：献立検索の食材マッチングをより柔軟に

## 技術スタック

- 収集・解析: Python 3 (urllib, pdfplumber, pypdf)
- フロントエンド: HTML5 + CSS3 + Vanilla JS（ビルドステップなし）
- データ形式: JSON
- ストレージ: LocalStorage（お気に入り）
