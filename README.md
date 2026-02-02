# Discord 提出管理 Bot

Render でホスティングする Discord Bot です。画像の提出とその承認プロセスを管理します。

## 機能

### `/up [画像]` コマンド
- ユーザーが画像を提出するコマンド
- 画像はチャンネルA（指定した確認用チャンネル）にシークレットメッセージとして投稿されます
- 投稿には以下の情報が含まれます：
  - 提出者の名前
  - 提出時刻
  - 「確認済み」ボタン

### 承認プロセス

#### パターン1: 確認済みボタンを押す
1. 管理者が「確認済み」ボタンを押す
2. チャンネルB（受理済み投稿用チャンネル）に画像、名前、提出時刻が投稿される
3. 提出者にDMで「受理されました」と通知

#### パターン2: リプライで理由を送る
1. 管理者がチャンネルAの投稿にリプライで拒否理由を記入
2. チャンネルBには投稿されない
3. 提出者にDMで「受理されませんでした」と理由が通知される

## セットアップ

### 1. Discord Bot の作成

1. [Discord Developer Portal](https://discord.com/developers/applications) にアクセス
2. "New Application" をクリックして Bot を作成
3. "Bot" タブで Bot を追加
4. "TOKEN" をコピー（後で使用）
5. "Privileged Gateway Intents" で以下を有効化：
   - MESSAGE CONTENT INTENT
   - SERVER MEMBERS INTENT

### 2. Bot の招待

OAuth2 > URL Generator で以下を選択：
- Scopes: `bot`, `applications.commands`
- Bot Permissions: 
  - Send Messages
  - Embed Links
  - Attach Files
  - Read Message History
  - Use Slash Commands
  - Manage Messages

生成された URL からサーバーに Bot を招待します。

### 3. チャンネル ID の取得

1. Discord の設定 > 詳細設定 > 開発者モードを有効化
2. チャンネルを右クリック > "ID をコピー"
3. チャンネルA（確認用）とチャンネルB（受理済み）の ID を取得

### 4. Render でのデプロイ

#### 4.1 GitHub にプッシュ

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/discord-bot.git
git push -u origin main
```

#### 4.2 Render でサービスを作成

1. [Render](https://render.com/) にアクセスしてログイン
2. "New +" > "Web Service" をクリック
3. GitHub リポジトリを接続
4. 設定：
   - **Name**: 任意の名前
   - **Environment**: Python 3
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `python bot.py`
   - **Instance Type**: Free

#### 4.3 環境変数の設定

Render のダッシュボードで "Environment" タブを開き、以下の環境変数を追加：

| Key | Value |
|-----|-------|
| `DISCORD_TOKEN` | Bot のトークン |
| `CHANNEL_A_ID` | チャンネルA（確認用）の ID |
| `CHANNEL_B_ID` | チャンネルB（受理済み）の ID |

#### 4.4 デプロイ

"Create Web Service" をクリックしてデプロイを開始します。

## 使い方

### ユーザー側
1. Discord で `/up` コマンドを入力
2. 画像ファイルを選択して送信
3. DM で結果を待つ

### 管理者側
1. チャンネルAで提出を確認
2. 承認する場合: 「確認済み」ボタンをクリック
3. 却下する場合: メッセージにリプライで理由を記入

## 注意事項

- Render の Free プランでは、15分間アクセスがないとスリープ状態になります
- Bot がスリープから復帰するまで数秒かかる場合があります
- 24時間稼働させたい場合は有料プランを検討してください

## トラブルシューティング

### Bot がオンラインにならない
- Render のログを確認
- 環境変数が正しく設定されているか確認
- Bot トークンが有効か確認

### コマンドが表示されない
- Bot の招待時に `applications.commands` スコープが含まれているか確認
- Bot が起動してから数分待つ（コマンド同期に時間がかかる場合があります）

### ボタンが反応しない
- Bot に必要な権限があるか確認
- チャンネル ID が正しいか確認
