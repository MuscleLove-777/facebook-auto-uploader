# -*- coding: utf-8 -*-
"""
Facebook ページ画像自動アップロード（GitHub Actions用）
Google Driveから画像取得 → ランダム1枚投稿 → アップロード済みを記録
Facebook Graph API（公式）使用
"""
import sys
import json
import os
import random
import time
from datetime import datetime, timezone, timedelta
import requests

JST = timezone(timedelta(hours=9))

# --- 環境変数 ---
FB_PAGE_ID = os.environ.get("FB_PAGE_ID", "")
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
GDRIVE_FOLDER_ID = os.environ.get("GDRIVE_FOLDER_ID_FACEBOOK", "")
GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

PATREON_LINK = "https://www.patreon.com/c/MuscleLove?utm_source=facebook&utm_medium=autopost"
HUB_LINK = "https://musclelove-777.github.io/?utm_source=facebook&utm_medium=autopost"
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
UPLOADED_LOG = "uploaded_facebook.json"

# --- NGワード（絶対に投稿しない） ---
NG_WORDS = ['アツロウ', 'あつろう', 'atsuro', 'Atsuro', 'ATSURO']

# --- タグマッピング ---
CONTENT_TAG_MAP = {
    'training': ['筋トレ', 'workout', 'training', 'gym', 'fitness', '筋トレ女子', 'gymgirl'],
    'workout': ['筋トレ', 'workout', 'training', 'gym', 'fitness', '筋トレ女子', 'gymgirl'],
    'pullups': ['懸垂', 'pullups', 'backworkout', 'calisthenics', 'tonedbody'],
    'posing': ['ポージング', 'posing', 'bodybuilding', 'physique', 'musclebeauty', '筋肉美'],
    'flex': ['フレックス', 'flex', 'muscle', 'bodybuilding', '腕フェチ', 'musclebeauty'],
    'muscle': ['筋肉', 'muscle', 'muscular', 'fitness', '筋肉美', 'musclebeauty'],
    'bicep': ['上腕二頭筋', 'biceps', 'arms', 'muscle', '腕フェチ', 'armfetish'],
    'abs': ['腹筋', 'abs', 'sixpack', 'core', 'tonedbody', 'fitchick'],
    'leg': ['脚トレ', 'legs', 'quads', 'legday', 'thickfit', 'thicc'],
    'back': ['背中', 'back', 'lats', 'backday', 'tonedbody'],
    'squat': ['スクワット', 'squat', 'legs', 'legday', 'thickfit', 'thicc'],
    'deadlift': ['デッドリフト', 'deadlift', 'powerlifting', 'strongwomen'],
    'bench': ['ベンチプレス', 'benchpress', 'chest', 'fitchick'],
    'bikini': ['ビキニ', 'bikini', 'bikinifitness', 'figurecompetitor', 'musclebeauty', 'fitchick'],
    'competition': ['大会', 'competition', 'bodybuilding', 'contest', 'physique'],
    'armpit': ['ワキフェチ', 'armpitfetish', 'armpit', 'フェチ'],
    'tan': ['褐色美女', 'tanned', 'tanbody', '褐色', 'darktan'],
    'thick': ['むちむち', 'thicc', 'thickfit', 'curvy', 'voluptuous'],
}

BASE_TAGS = [
    'musclegirl', 'muscularwoman', 'femalemuscle', 'strongwomen',
    'fbb', 'fitnessmotivation', 'gymgirl', 'thicc', 'thickfit',
    'musclebeauty', 'tonedbody', 'fitchick',
    '筋肉女子', '筋トレ女子', 'マッスル女子',
    '筋肉美', 'AI美女', 'むちむち', '褐色美女',
]

# キャプションテンプレート（Facebookは長文OK・ハッシュタグ少なめが効果的）
CAPTION_TEMPLATES = [
    "筋肉は裏切らない。\n毎日の積み重ねが、この身体を作る。\n\n{hashtags}\n\nMore content on Patreon\n{patreon}",
    "圧倒的フィジーク。\nトレーニングの成果がここに。\n\n{hashtags}\n\nPatreonで限定コンテンツ公開中\n{patreon}",
    "She didn't come to play.\n本気で鍛えた身体は美しい。\n\n{hashtags}\n\nFull gallery on Patreon\n{patreon}",
    "鍛え抜かれた美。\nEarned, not given.\n\n{hashtags}\n\nMore on Patreon\n{patreon}",
    "むちむち最強伝説。\nThick & powerful.\n\n{hashtags}\n\nExclusive content on Patreon\n{patreon}",
    "Fuerza y belleza.\n筋肉美の極み。\n\n{hashtags}\n\nPatreonで全作品を公開中\n{patreon}",
    "褐色ボディの破壊力。\nUnstoppable.\n\n{hashtags}\n\nCheck out Patreon for more\n{patreon}",
    "Iron therapy.\n筋トレは最高の自己投資。\n\n{hashtags}\n\nFull collection on Patreon\n{patreon}",
    "魅せる筋肉。\nBuilt to impress.\n\n{hashtags}\n\nMore content on Patreon\n{patreon}",
    "この仕上がり、見て。\nPeak form.\n\n{hashtags}\n\nExclusive gallery on Patreon\n{patreon}",
    "Stronger every day.\n日々進化し続ける身体。\n\n{hashtags}\n\nPatreonで限定公開中\n{patreon}",
    "美は努力の結晶。\nNo shortcuts.\n\n{hashtags}\n\nMore on Patreon\n{patreon}",
]

# NSFWキーワード検出用
NSFW_KEYWORDS = ['nsfw', 'sexy', 'adult', 'bikini', 'erotic', 'hot', 'エロ']


def _load_pool():
    """content_poolからsafe_fitnessインサイトをロード。失敗時は{}（ハードコードで動く）。"""
    try:
        from pool_loader import as_insights
        return as_insights("safe_fitness", platform="facebook")
    except Exception as e:
        print(f"pool_loader unavailable (using hardcoded): {e}")
        return {}


# ===== Google Drive =====

def list_gdrive_images(folder_id):
    """Google Driveフォルダからgdownで画像一覧を取得（GOOGLE_API_KEY不使用: 憲法第4条）"""
    return _list_via_gdown(folder_id)


def _list_via_gdown(folder_id):
    """gdownでフォルダ内ファイル一覧を取得（APIキー不要）"""
    import gdown
    dl_dir = "images"
    os.makedirs(dl_dir, exist_ok=True)
    url = f"https://drive.google.com/drive/folders/{folder_id}"
    print(f"Downloading from Google Drive: {url}")
    try:
        gdown.download_folder(url, output=dl_dir, quiet=False, remaining_ok=True)
    except Exception as e:
        print(f"Download error: {e}")
        return []

    images = []
    for root, dirs, filenames in os.walk(dl_dir):
        for fname in filenames:
            ext = os.path.splitext(fname)[1].lower()
            if ext in IMAGE_EXTENSIONS:
                fpath = os.path.join(root, fname)
                images.append({
                    "id": None,
                    "name": fname,
                    "local_path": fpath,
                })
    return images


# ===== タグ・キャプション生成 =====

def generate_tags(image_name, pool=None):
    """ファイル名からハッシュタグを生成（Facebookは10個程度が最適）"""
    pool = pool or {}
    # Pool由来タグを優先、ハードコードBASE_TAGSをフォールバック
    base = pool.get("recommended_tags", BASE_TAGS)
    tags = list(base)
    name_lower = image_name.lower().replace('-', ' ').replace('_', ' ')
    matched = set()
    for keyword, keyword_tags in CONTENT_TAG_MAP.items():
        if keyword in name_lower:
            for t in keyword_tags:
                if t not in matched:
                    tags.append(t)
                    matched.add(t)
    seen = set()
    unique_tags = []
    for t in tags:
        if t.lower() not in seen:
            seen.add(t.lower())
            unique_tags.append(t)
    # Facebookはハッシュタグ少なめが効果的（10個程度）
    return unique_tags[:10]


def build_caption(image_name, tags, pool=None):
    """投稿キャプションを生成（pool優先、ハードコードフォールバック）"""
    pool = pool or {}
    hashtags = ' '.join([f'#{t}' for t in tags])

    # テンプレ: pool由来優先、ハードコードフォールバック
    templates = pool.get("recommended_templates", CAPTION_TEMPLATES)
    template = random.choice(templates)

    # Pool由来テンプレは{hashtags}のみ、ハードコードは{hashtags}+{patreon}
    try:
        caption = template.format(hashtags=hashtags, patreon=PATREON_LINK)
    except KeyError:
        caption = template.format(hashtags=hashtags)

    # CTA: pool由来1本を追加（ハブリンクは常に付与）
    ctas = pool.get("recommended_ctas", [])
    if ctas:
        caption += "\n\n" + random.choice(ctas)
    else:
        caption += f"\n\nMore on Patreon\n{PATREON_LINK}"

    # 計測可能なブログ導線を必ず1本入れる（GA4流入計測の生命線）
    caption += f"\n\nAll sites & gallery hub\n{HUB_LINK}"

    # NGワードチェック（pool由来NG + ハードコードNG）
    ng_words = list(pool.get("avoid_tags", [])) + NG_WORDS
    seen_ng = set()
    for ng in ng_words:
        if ng not in seen_ng and ng in caption:
            print(f"NG word detected: {ng}")
            return None
        seen_ng.add(ng)
    return caption


def is_nsfw(image_name):
    """ファイル名からNSFWコンテンツかどうか判定"""
    name_lower = image_name.lower()
    return any(kw in name_lower for kw in NSFW_KEYWORDS)


# ===== Facebook Graph API =====

def post_photo_by_url(image_url, caption):
    """画像URLを指定してFacebookページに写真を投稿"""
    url = f"{GRAPH_API_BASE}/{FB_PAGE_ID}/photos"
    params = {
        "url": image_url,
        "message": caption,
        "access_token": FB_PAGE_ACCESS_TOKEN,
    }
    print("Posting photo to Facebook...")
    resp = requests.post(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    post_id = data.get("post_id") or data.get("id")
    print(f"Posted! post_id={post_id}")
    return post_id


def post_photo_by_file(file_path, caption):
    """ローカルファイルをFacebookページにアップロード投稿"""
    url = f"{GRAPH_API_BASE}/{FB_PAGE_ID}/photos"
    params = {
        "message": caption,
        "access_token": FB_PAGE_ACCESS_TOKEN,
    }
    with open(file_path, "rb") as f:
        files = {"source": (os.path.basename(file_path), f, "image/jpeg")}
        print("Uploading photo to Facebook...")
        resp = requests.post(url, params=params, files=files)
    resp.raise_for_status()
    data = resp.json()
    post_id = data.get("post_id") or data.get("id")
    print(f"Posted! post_id={post_id}")
    return post_id


# ===== アップロードログ管理 =====

def load_uploaded_log():
    if os.path.exists(UPLOADED_LOG):
        with open(UPLOADED_LOG, 'r') as f:
            return json.load(f)
    return []


def save_uploaded_log(log):
    with open(UPLOADED_LOG, 'w') as f:
        json.dump(log, f, indent=2)


# ===== LINE通知 =====

def notify_line(message):
    """LINE通知を送信"""
    token = os.environ.get("LINE_CHANNEL_TOKEN", "")
    user_id = os.environ.get("LINE_USER_ID", "")
    if not token or not user_id:
        return
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}",
    }
    body = {
        "to": user_id,
        "messages": [{"type": "text", "text": message}],
    }
    try:
        requests.post(url, headers=headers, json=body)
    except Exception:
        pass


# ===== メイン =====

def main():
    # 認証チェック
    missing_secrets = []
    if not FB_PAGE_ID:
        missing_secrets.append("FB_PAGE_ID")
    if not FB_PAGE_ACCESS_TOKEN:
        missing_secrets.append("FB_PAGE_ACCESS_TOKEN")
    if not GDRIVE_FOLDER_ID:
        missing_secrets.append("GDRIVE_FOLDER_ID_FACEBOOK")

    if missing_secrets:
        print("=" * 60)
        print("ERROR: 必須シークレットが未設定です")
        print("=" * 60)
        print()
        print("以下のシークレットをGitHub Secretsに設定してください:")
        print("  リポジトリ → Settings → Secrets and variables → Actions")
        print("  → New repository secret")
        print()
        secret_descriptions = {
            "FB_PAGE_ID": "FacebookページID（ページ設定 → 透明性 で確認可能）",
            "FB_PAGE_ACCESS_TOKEN": "ページアクセストークン（Graph API Explorerで取得）",
            "GDRIVE_FOLDER_ID_FACEBOOK": "Google DriveフォルダID（フォルダURL末尾の文字列）",
        }
        for secret in missing_secrets:
            desc = secret_descriptions.get(secret, "")
            print(f"  [ ] {secret}: {desc}")
        print()
        print("トークン取得手順: https://developers.facebook.com/tools/explorer/")
        return 1

    now = datetime.now(JST)
    print(f"Facebook Auto Uploader")
    print(f"Page ID: {FB_PAGE_ID[:5]}...")
    print(f"Time: {now.strftime('%Y-%m-%d %H:%M JST')}")
    print()

    # Google Driveから画像一覧取得
    images = list_gdrive_images(GDRIVE_FOLDER_ID)
    if not images:
        print("No images found!")
        return 0

    # 未アップロード画像をフィルタ
    uploaded_log = load_uploaded_log()
    available = [img for img in images if img["name"] not in uploaded_log]
    if not available:
        print("All images already uploaded!")
        return 0

    print(f"Available: {len(available)} / Total: {len(images)}")

    # ランダムに1枚選択
    image = random.choice(available)
    print(f"Selected: {image['name']}")

    # content_pool ロード（毎日自動最適化: 憲法第3条）
    pool = _load_pool()
    if pool:
        print(f"Pool loaded: {pool.get('updated_at_jst', '?')}")

    # タグ・キャプション生成（pool優先、ハードコードフォールバック）
    tags = generate_tags(image["name"], pool)
    caption = build_caption(image["name"], tags, pool)
    if caption is None:
        print("Caption contains NG words, skipping!")
        return 1

    print(f"Tags: {', '.join(tags)}")
    print(f"Caption:\n{caption}\n")

    # Facebook投稿
    try:
        if image.get("url"):
            post_id = post_photo_by_url(image["url"], caption)
        elif image.get("local_path"):
            post_id = post_photo_by_file(image["local_path"], caption)
        else:
            print("Error: No image URL or local path available")
            return 1

        if not post_id:
            print("Post failed!")
            notify_line(f"[Facebook] 投稿失敗\n{now.strftime('%Y-%m-%d %H:%M JST')}")
            return 1

        # 成功 → ログ保存
        uploaded_log.append(image["name"])
        save_uploaded_log(uploaded_log)
        remaining = len(available) - 1
        print(f"\nSuccess! Remaining: {remaining}")
        notify_line(
            f"[Facebook] 投稿成功\n"
            f"画像: {image['name']}\n"
            f"残り: {remaining}枚\n"
            f"{now.strftime('%Y-%m-%d %H:%M JST')}"
        )
        return 0

    except requests.exceptions.HTTPError as e:
        print(f"HTTP Error: {e}")
        if e.response is not None:
            print(f"Status: {e.response.status_code}")
            print(f"Response: {e.response.text}")
        notify_line(f"[Facebook] HTTPエラー: {e}\n{now.strftime('%Y-%m-%d %H:%M JST')}")
        return 1
    except Exception as e:
        print(f"Error: {e}")
        notify_line(f"[Facebook] エラー: {e}\n{now.strftime('%Y-%m-%d %H:%M JST')}")
        return 1


if __name__ == '__main__':
    sys.exit(main())
