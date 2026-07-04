# facebook-auto-uploader

Google Drive の「Facebookに出して安全な画像/動画」からランダムに1つ選び、
Facebook Graph API で **Facebookページへ無人自動投稿** する。
Instagram/Tumblr 自動投稿と同じ設計思想
（Drive→ランダム→タグ/キャプション自動生成→投稿→冪等ログ）。M国憲法「完全自動運営」準拠。

## Instagram版との違い（こちらが簡単）

Instagramは「公開URL化→コンテナ→publish」の2段階が必須だが、
Facebookは **ローカルファイルを直接multipartアップロードできる**（匿名ホスト不要）。

```
Drive(gdown, キー不要) → ランダム選択（露骨NSFW除外・投稿済み除外）
  → タグ/キャプション自動生成（content_pool safe_fitnessレーンで毎日自動最適化）
  → 画像: /{page-id}/photos に source
    動画: graph-video.facebook.com/{page-id}/videos に source（mp4/mov）
  → uploaded_facebook.json に記録（冪等: 同じ素材を二度出さない）
```

動画はFB側で非同期エンコードされるが、投稿自体はレスポンス時点で確定するので待機不要。

## ファイル構成

| ファイル | 役割 |
|---|---|
| `upload.py` | 本体（Drive→選択→投稿、NGワード/NSFWガード、LINE通知） |
| `pool_loader.py` | `dashboard/autonomy` の content_pool を読む（毎日自動最適化・全uploader共通） |
| `token_refresh.py` | 60日で切れるページトークンの点検・自動延長（月次） |
| `.github/workflows/facebook-post.yml` | JST 12:00/19:00 投稿 + 月次トークン点検 + 3回リトライ |
| `requirements.txt` | requests / gdown |

## セットアップ（初回のみ・人間の作業）

### 1. Facebookページとアプリを準備
1. 投稿先の **Facebookページ** を用意（個人タイムラインには投稿できない）
2. https://developers.facebook.com/apps/ でアプリ作成（用途: その他 / ビジネス）

### 2. ページアクセストークンを取得
1. https://developers.facebook.com/tools/explorer/ (Graph API Explorer) で自分のアプリを選び、
   権限 `pages_show_list` `pages_read_engagement` `pages_manage_posts` `publish_video`
   を付けてユーザートークンを発行
2. `GET /me/accounts` → 対象ページの `id`（＝**FB_PAGE_ID**）と `access_token`（＝ページトークン）を控える
3. ページトークンは短命。[デバッグツール](https://developers.facebook.com/tools/debug/accesstoken/)で
   長期トークン（60日）へ交換して **FB_PAGE_ACCESS_TOKEN** とする
   （以後の延長は `token_refresh.py` が月次で担当）

> 詳細な公式手順: https://developers.facebook.com/docs/pages-api/getting-started

### 3. GitHub Secrets を設定
リポジトリ → Settings → Secrets and variables → Actions → New repository secret

| Secret | 必須 | 内容 |
|---|---|---|
| `FB_PAGE_ID` | ✅ | Facebookページの数値ID（手順2-2） |
| `FB_PAGE_ACCESS_TOKEN` | ✅ | ページ長期アクセストークン（手順2-3） |
| `GDRIVE_FOLDER_ID_FACEBOOK` | ✅ | **安全素材だけ**を入れたDriveフォルダID（URL末尾） |
| `FB_APP_ID` / `FB_APP_SECRET` | 推奨 | トークン自動延長に使用（未設定なら手動更新） |
| `LINE_CHANNEL_TOKEN` / `LINE_USER_ID` | 任意 | 成否・トークン失効をLINE通知 |

> **GOOGLE_API_KEY は不要**（gdownでキーレス取得。憲法第4条）。

### 4. 動かす
`Actions → Facebook Auto Post → Run workflow` で手動実行してテスト。以後はcronで無人投稿。

## コンテンツ安全設計（重要）

FacebookはMeta共通で**ヌード/性的表現BAN**。本ブランドはアダルト路線だが、Facebookには
gif_factory の「**非エロ＝主要SNSに出して安全**」レーンの素材だけを出す:

- `GDRIVE_FOLDER_ID_FACEBOOK` には **安全素材専用フォルダ** を指定する（アダルトと分離）
- ファイル名に露骨語（nude/erotic/エロ/裸 等）を含む素材は自動スキップ
- キャプションは健全フィットネス路線 + Patreon/ハブサイト導線（UTM付きでGA4計測）
- content_pool の `safe_fitness` レーンで毎日自動最適化
- NGワード二重ガード（固有名詞は絶対に出さない: 憲法第4条）

## 制限・注意

- 動画の非resumableアップロードは **1GB / 20分まで**（GIF工場の短尺クリップなら余裕）
- Facebookはキャプション内リンクがクリック可能 → Patreon+ハブの直リンクを毎回入れる
  （Instagramと違いリンク誘導が効く媒体。ハッシュタグは10個程度が最適）
- トークンは60日で失効 → 月次 `token_refresh.py` が点検・延長（`FB_APP_ID/SECRET`設定時）。
  更新トークンのSecret反映は手動
- GitHub Actionsのscheduleはリポジトリが60日無活動だと自動停止する
  （本リポは content_pool の日次自動コミットがあるため通常は問題なし）
