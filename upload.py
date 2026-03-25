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

PATREON_LINK = "https://www.patreon.com/cw/MuscleLove"
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


# ===== Google Drive =====

def list_gdrive_images(folder_id):
    """Google DriveフォルダからAPIで画像一覧を取得"""
    api_key = os.environ.get("GOOGLE_API_KEY", "")
    if api_key:
        return _list_via_api(folder_id, api_key)
    else:
        return _list_via_gdown(folder_id)


def _list_via_api(folder_id, api_key):
    """Google Drive API v3で画像一覧を取得"""
    url = "https://www.googleapis.com/drive/v3/files"
    query = f"'{folder_id}' in parents and trashed = false"
    params = {
        "q": query,
        "key": api_key,
        "fields": "files(id,name,mimeType)",
        "pageSize": 1000,
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    files = resp.json().get("files", [])

    images = []
    for f in files:
        ext = os.path.splitext(f["name"])[1].lower()
        if ext in IMAGE_EXTENSIONS:
            images.append({
                "id": f["id"],
                "name": f["name"],
                "url": f"https://drive.google.com/uc?export=download&id={f['id']}",
            })
    return images


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

def generate_tags(image_name):
    """ファイル名からハッシュタグを生成（Facebookは10個程度が最適）"""
    tags = list(BASE_TAGS)
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


def build_caption(image_name, tags):
    """投稿キャプションを生成"""
    hashtags = ' '.join([f'#{t}' for t in tags])
    template = random.choice(CAPTION_TEMPLATES)
    caption = template.format(
        hashtags=hashtags,
        patreon=PATREON_LINK,
    )
    # NGワードチェック
    for ng in NG_WORDS:
        if ng in caption:
            print(f"NG word detected: {ng}")
            return None
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
    if not FB_PAGE_ID or not FB_PAGE_ACCESS_TOKEN:
        print("Error: FB_PAGE_ID or FB_PAGE_ACCESS_TOKEN not set")
        print("Set these environment variables:")
        print("  FB_PAGE_ID=your_facebook_page_id")
        print("  FB_PAGE_ACCESS_TOKEN=your_page_access_token")
        return 1

    if not GDRIVE_FOLDER_ID:
        print("Error: GDRIVE_FOLDER_ID_FACEBOOK not set")
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

    # タグ・キャプション生成
    tags = generate_tags(image["name"])

    # トレンドタグ追加（trending.pyが存在すれば）
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'x-auto-uploader'))
        from trending import get_trending_tags
        trend_tags = get_trending_tags(max_tags=3)
        if trend_tags:
            seen = {t.lower() for t in tags}
            for t in trend_tags:
                if t.lower() not in seen:
                    tags.append(t)
                    seen.add(t.lower())
    except ImportError:
        print("trending.py not found, skipping trend tags")

    caption = build_caption(image["name"], tags)
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
