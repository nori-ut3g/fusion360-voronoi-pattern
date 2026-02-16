# Fusion 360 ボロノイパターンジェネレーター

板金パーツやレーザーカット用に、平面にボロノイ軽量化穴パターンを生成する Fusion 360 アドインです。

![ボロノイパターンプレビュー](docs/preview.png)
<!-- 実際のスクリーンショットに差し替えてください -->

## 特徴

- 任意の平面にボロノイセルパターンを生成
- パラメータ調整可能：シード数、リブ幅、エッジマージン、角丸め半径
- マウントホール除外ゾーン（円形エッジを選択して保護）
- マウントホール付近の密度勾配オプション（強度確保）
- ランダムシードによる再現可能なパターン
- 純 Python 実装 — 外部依存なし

## インストール

1. リポジトリをクローン:
   ```bash
   git clone https://github.com/nori-ut3g/fusion360-voronoi-pattern.git
   ```

2. `VoronoiPattern` フォルダを Fusion 360 のアドインディレクトリにコピーまたはシンボリックリンク:

   **Windows:**
   ```
   %APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\
   ```

   **macOS:**
   ```
   ~/Library/Application Support/Autodesk/Autodesk Fusion 360/API/AddIns/
   ```

3. Fusion 360 を起動 → ツール → アドイン → **VoronoiPattern** を有効化

## 使い方

1. 平面を持つデザインを開く（例：板金パーツ）
2. **ツール** → **Voronoi Pattern** を選択
3. パターンを適用する**平面**を選択
4. （オプション）除外する**円形エッジ**（マウントホール）を選択
5. パラメータを調整:

   | パラメータ | デフォルト | 説明 |
   |---|---|---|
   | Seed Count | 40 | ボロノイセルの数（10〜200） |
   | Min Rib Width | 3.0 mm | 穴間の最小リブ幅 |
   | Edge Margin | 5.0 mm | 面の端からのマージン |
   | Corner Radius | 1.0 mm | 穴の角の丸め半径（0で直線） |
   | Random Seed | 42 | パターン再現用の乱数シード |
   | Density Gradient | On | マウントホール付近のセル密度を上げる |

6. **OK** をクリック → ボロノイパターンのスケッチが作成される
7. **押し出し → カット** で穴を開ける

## アルゴリズム概要

1. **シード生成**: 面の境界内にランダム点を配置（マージン・除外ゾーンを考慮）
2. **ドロネー三角分割**: Bowyer-Watson アルゴリズムでシード点を三角分割
3. **ボロノイ双対変換**: ドロネー三角形の外接円中心からボロノイセルを構成
4. **クリッピング＆オフセット**: マージン境界でクリップし、リブ幅の半分だけ内側にオフセット
5. **角丸め**: 鋭角をフィレット（円弧）で置換
6. **スケッチ描画**: 最終パターンを選択面のスケッチに描画

境界のセルが正しく閉じるよう、ミラーポイントを境界外に追加しています。

## スタンドアロンテスト

アルゴリズムモジュール（`lib/`）は Fusion 360 に依存せず、単独でテスト可能です:

```bash
pip install pytest matplotlib
cd tests
pytest -v
```

パターンの視覚的プレビュー:

```bash
python tests/visualize.py
```

## プロジェクト構成

```
VoronoiPattern/           # Fusion 360 アドインフォルダ
├── VoronoiPattern.py     # アドインのエントリポイント
├── VoronoiPattern.manifest
├── lib/
│   ├── voronoi.py        # Bowyer-Watson ドロネー → ボロノイ
│   ├── polygon.py        # クリッピング、オフセット、角丸め
│   ├── seed_generator.py # シード点生成
│   └── sketch_drawer.py  # Fusion スケッチ描画
├── config/
│   └── defaults.json     # デフォルトパラメータ
└── resources/            # アイコン
tests/
├── test_voronoi.py
├── test_polygon.py
├── test_seed_generator.py
└── visualize.py          # matplotlib プレビュー
```

## 制限事項

- 平面のみ対応（曲面は未対応）
- シード数は最大約 200（それ以上はパフォーマンスが低下する可能性あり）
- スケッチジオメトリのみ作成 — 押し出しカットは手動で実行

## ライセンス

[MIT](LICENSE)
