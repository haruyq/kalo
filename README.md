# KALPA: Cosmic Symphony Overlay

KALPA: Cosmic Symphony向けの[**tosu**](https://github.com/tosuapp/tosu)互換メモリリーダー。

## 使い方

1. 圧縮フォルダを展開し、使用するオーバーレイを `overlays/<オーバーレイ名>/`に配置（tosu の `static/` と同じ形式）
2. KALPAを起動してから`kalo.exe`を起動
3. ブラウザで`http://127.0.0.1:24050/`を開くと、オーバーレイの一覧が表示
4. OBSで、ブラウザソースのURLに`http://127.0.0.1:24050/<オーバーレイ名>/`を指定

ポートを変える場合は `kalo.exe 24060` のように指定できます。

## PPとSP

KALPAにはosu!に存在するppシステムと似たようなものがSP(Stella Point)として実装されているため、**ppエンドポイントにはSPが返されます。**

| 用途 | 取得先 |
|---|---|
| 現在の状態 | `/json/sp` |
| 任意の譜面・精度のSP | `/api/calculate/sp?mapId=&acc=&lunatic=`（`acc`の代わりに`rate`（0〜1000000）`mapId` の代わりに `level` も可。省略時はプレイ中または選択中の譜面） |
| v1 / v2 のJSON | `gameplay.sp` / `play.sp`、`profile.sp` |
| StreamCompanion Token | `spIfMapEndsNow`、`spIfRestFced`、`spAllPerfect`、`spBest`、`spProfileAfter`、`spProfileDelta`、`spProfile4K`、`spProfile5K` |

## 対応しているAPI

| 形式 | WebSocket | HTTP |
|---|---|---|
| tosu v1 (gosumemory) | `/ws` | `/json` |
| tosu v2 | `/websocket/v2`、`/websocket/v2/precise`、`/websocket/commands` | `/json/v2`、`/json/v2/precise` |
| StreamCompanion | `/tokens` | `/json/sc`、`/backgroundImage` |

ジャケットは`/Songs/<ファイル名>`、`/files/beatmap/<ファイル名>`、`/backgroundImage`で取得できます。KALPAに存在しない値（hit error、UR、modなど）は空または0です。Lunaticは難易度名（例: `COSMOS Lv18 LUNATIC`）に含まれます。

HTTP API のパラメータと応答は、起動中に `http://127.0.0.1:24050/docs` で確認できます。

## ソースから実行・ビルドする

[uv](https://docs.astral.sh/uv/)が必要です。

```
uv run kalo                       # 起動（ポート指定: uv run kalo 24060）
uv run python tests/test_core.py  # ゲーム不要のチェック
uv run build.py                   # dist/kalo.exe と配布用 zip を作成
```

| 場所 | 役割 |
|---|---|
| `src/kalo/app.py` | アプリの組み立て（ルーター登録とオーバーレイ配信） |
| `src/kalo/routers/` | エンドポイント：`state.py`（状態のJSON / WebSocket）、`calculate.py`（SP計算）、`files.py`（ジャケット）、`overlays.py`（一覧ページ） |
| `src/kalo/tosu.py` | 読み取った状態を tosu v1 / v2 / StreamCompanion / SPの形式に変換 |
| `src/kalo/stellar.py` | SP の計算式 |
| `src/kalo/game/` | ゲームのメモリ読み取り（`memory.py`、`reader.py`）とジャケット取得（`covers.py`） |
