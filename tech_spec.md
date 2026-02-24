# Circle Room 技術仕様書 (Technical Specification)

「Circle Room」は、大学内の新歓活動やサークル情報を一元管理し、学生同士の交流を促進するためのWebアプリケーションです。

## 1. プロジェクト概要
- **目的**: 大学サークルの新歓情報、イベント告知、DM機能による直接的な問い合わせを可能にする。
- **ターゲット**: サークルを探している新入生・在学生、および部員を募集しているサークル団体。

## 2. 技術スタック
- **Backend**: Python 3.x / Django 5.x
- **Database**: SQLite3 (開発用) / PostgreSQL (推奨)
- **Frontend**: 
  - HTML5 / Django Template Engine
  - CSS: Tailwind CSS (CDN/JIT)
  - UI Icons: Material Symbols Outlined
  - Fonts: Plus Jakarta Sans, Noto Sans JP
- **Auth**: Django 組み込み認証系 + カスタム Signup 画面

## 3. ディレクトリ構成
```text
okadainsta/
├── config/              # プロジェクト設定 (Settings, URLs, WSGI)
├── core/                # メインアプリケーション
│   ├── migrations/      # DB移行ファイル
│   ├── static/          # 静的ファイル (CSS/JS)
│   ├── forms.py         # フォーム定義 (Post, Profile, Circle)
│   ├── models.py        # データベースモデル
│   ├── urls.py          # アプリケーションルーティング
│   └── views.py         # ビュー（ロジック）
├── templates/           # HTMLテンプレート
│   ├── core/            # アプリメイン画面、パーツ
│   └── registration/    # 認証関連 (Login, Signup)
├── media/               # ユーザーアップロード画像
└── manage.py            # Django管理コマンド
```

## 4. データモデル (Data Model)
主要的なモデル構成は以下の通りです：

| モデル名 | 説明 | 主要フィールド |
| :--- | :--- | :--- |
| **User** | Django標準ユーザー | username, password, email |
| **Profile** | ユーザープロフ | display_name, school_year, bio, avatar |
| **Circle** | サークル詳細情報 | name, activity_days, members_count, sns_link |
| **Post** | 募集・イベント投稿 | title, circle_name, event_at, category, status |
| **Conversation** | メッセージ会話 | participants, is_group, post |
| **Message** | 個別メッセージ | conversation, sender, body |
| **Notification** | 通知 | notif_type, text, is_read |
| **Tag** | 投稿タグ | name |

## 5. 主要機能
### 5.1 タイムライン・検索
- カテゴリ（スポーツ、音楽等）やタグによる投稿の絞り込み。
- 人気順、保存数順、新着順でのソート。
- イベント日時を過ぎると自動的に「終了」ステータスへ移行するロジック。

### 5.2 認証システム
- モダンなダークテーマを採用したログイン及び新規登録画面。
- `UserCreationForm` を拡張したサインアップフロー。
- ログイン状況に応じたヘッダー及びプロフィールタブの動的表示。

### 5.3 ダイレクトメッセージ (DM)
- 特定の投稿に基づいた問い合わせスレッドの生成。
- リアルタイムではないが、未読カウントと通知機能を備えたメッセージ交換。

### 5.4 プロフィール・サークル管理
- 個人プロフィールの編集。
- サークル代表者によるサークル基本情報の管理。

## 6. UI/UX デザイン方針
- **テーマ**: ダークモード標準（iOS/モダンウェブスタイル）。
- **色彩**: 背景色 `#101f22` (background-dark)、アクセントカラー `#0dccf2` (primary)。
- **アニメーション**: Tailwindによるホバーエフェクト、マイクロインタラクション。
- **モバイルファースト**: スマートフォンでの閲覧を最適化したシングルカラム・ボトムナビゲーション形式。
