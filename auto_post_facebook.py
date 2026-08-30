# -*- coding: utf-8 -*-
"""
auto_post_facebook.py — Facebookページ 無人デイリー投稿（ローカル実行版・SFW動画1本/実行）

既存 upload.py(GitHub Actions+Drive版) のローカル進化形:
  - 素材: tiktok-auto-uploader/approved_sfw.json（Claude目視SFW承認プール）を共用
    ※ファイル名NGワードより強い視覚ゲート。Metaはヌード即BANなのでここが生命線。
  - 投稿: Graph API 直接multipartアップロード（公開URL不要・ログイン窓不要・トークンだけ）
  - ガード: 1日上限/最小間隔/再投稿間隔/ジッター（TikTok版と同じ流儀）

必要な .env（このフォルダ、Git管理外）:
  FB_PAGE_ID=<ページ数値ID>
  FB_PAGE_ACCESS_TOKEN=<ページ長期アクセストークン>

使い方:
  python auto_post_facebook.py          # 通常（ジッター→ガード→投稿）
  python auto_post_facebook.py --now    # ジッター無し（テスト）
  python auto_post_facebook.py --file <path>
  python auto_post_facebook.py check    # トークン/ページ疎通確認（投稿しない）

exit: 0=成功/正常スキップ, 2=トークン未設定/失効, 1=失敗
"""
import os, sys, json, time, random, datetime

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
POSTED_LOG = os.path.join(HERE, "posted_facebook.json")
GRAPH = "https://graph.facebook.com/v21.0"
GRAPH_VIDEO = "https://graph-video.facebook.com/v21.0"

sys.path.insert(0, HERE)
from pool_loader import as_insights  # noqa: E402


def _load_dotenv(path=None):
    if path is None:
        path = os.path.join(HERE, ".env")
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    except Exception:
        pass


_load_dotenv()

APPROVED_LOG = os.path.abspath(os.path.join(
    HERE, os.environ.get("APPROVED_SFW_PATH",
                         r"..\tiktok-auto-uploader\approved_sfw.json")))


def _load_json(path, default):
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            print(f"WARNING: {os.path.basename(path)} を読めませんでした")
    return default


def load_posted():
    return _load_json(POSTED_LOG, {"files": []})


def save_posted(log):
    with open(POSTED_LOG, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def _norm(p):
    return os.path.normcase(os.path.abspath(p))


def load_approved_entries():
    d = _load_json(APPROVED_LOG, {})
    out = []
    for x in d.get("approved", []):
        if isinstance(x, dict) and x.get("path"):
            if "platforms" in x and "facebook" not in x["platforms"]:
                continue  # Approval for another platform is not Facebook permission.
            out.append({"path": x["path"], "category": x.get("category", "")})
        elif isinstance(x, str):
            out.append({"path": x, "category": ""})
    return out


def pick_video():
    metas = load_approved_entries()
    if not metas:
        print(f"承認プールが空です（{APPROVED_LOG}）→ 投稿スキップ")
        return None
    posted = load_posted()
    last_at = {}
    for e in posted.get("files", []):
        if isinstance(e, dict) and e.get("abspath"):
            n = _norm(e["abspath"])
            at = str(e.get("uploaded_at", ""))
            if n not in last_at or at > last_at[n]:
                last_at[n] = at
    fresh, reusable = [], []
    min_repost_days = int(os.environ.get("FB_MIN_REPOST_DAYS", "14"))
    now = datetime.datetime.now()
    for m in metas:
        if not os.path.exists(m["path"]):
            continue
        n = _norm(m["path"])
        if n not in last_at:
            fresh.append(m)
            continue
        try:
            dt = datetime.datetime.strptime(last_at[n], "%Y-%m-%d %H:%M:%S")
            if (now - dt).days >= min_repost_days:
                reusable.append(dict(m, last=last_at[n]))
        except Exception:
            pass
    if fresh:
        chosen = random.choice(fresh)
        print(f"選択(未投稿 {len(fresh)}/{len(metas)}): {os.path.basename(chosen['path'])}")
        return chosen
    if reusable:
        reusable.sort(key=lambda m: m.get("last", ""))
        chosen = reusable[0]
        print(f"全て投稿済み → 最古を再利用: {os.path.basename(chosen['path'])} (last={chosen.get('last')})")
        return chosen
    print(f"承認プール{len(metas)}本は全て{min_repost_days}日以内に投稿済み → スキップ")
    return None


CATEGORY_TAGS = {
    "pullups": ["懸垂", "calisthenics"],
    "training": ["筋トレ", "workout"],
}


def build_caption(video_path):
    """本文にURLは入れない（外部リンク入り投稿はリーチが絞られるため）。
    CTA(UTM付きURL)は投稿直後の1コメント目に回す → (caption, cta) を返す。
    タグは10個弱。"""
    ins = as_insights("safe_fitness", platform="facebook")
    templates = ins.get("recommended_templates") or ["今日も積み上げ💪 {hashtags}"]
    tags_all = [t for t in (ins.get("recommended_tags") or []) if t and " " not in t]
    ctas = ins.get("recommended_ctas") or []
    ng = [w.lower() for w in (ins.get("avoid_tags") or [])]

    tpl = random.choice(templates)
    category = os.path.basename(os.path.dirname(video_path)).lower()
    cat_tags = CATEGORY_TAGS.get(category, [])
    pool = [t for t in tags_all if t not in cat_tags]
    picked = cat_tags + random.sample(pool, min(7, len(pool)))
    picked = [t for t in picked if not any(n in t.lower() for n in ng)]
    hashtags = " ".join("#" + t for t in dict.fromkeys(picked))

    body = tpl.replace("{hashtags}", "").strip()
    # 1コメント目は必ず導線になるよう、URL入りCTAを優先して選ぶ
    linked = [c for c in ctas if "http" in c]
    cta = random.choice(linked or ctas) if ctas else ""
    caption = "\n\n".join(x for x in [body, hashtags] if x)
    low = caption.lower()
    if any(n in low for n in ng):
        caption = "今日も積み上げ💪\n\n" + hashtags
    return caption[:4000], cta


def _cred():
    page_id = os.environ.get("FB_PAGE_ID", "").strip()
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "").strip()
    return page_id, token


def check():
    page_id, token = _cred()
    if not page_id or not token:
        print("NEEDS_TOKEN: .env に FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN を設定してください")
        return 2
    try:
        r = requests.get(f"{GRAPH}/{page_id}",
                         params={"fields": "id,name,followers_count", "access_token": token},
                         timeout=30)
        d = r.json()
    except Exception as e:
        print(f"疎通失敗: {e}")
        return 1
    if "error" in d:
        print(f"NEEDS_TOKEN: APIエラー: {d['error'].get('message')}")
        return 2
    print(f"OK: ページ「{d.get('name')}」(id={d.get('id')}, followers={d.get('followers_count')})")
    return 0


def post_video_api(video_path, caption):
    page_id, token = _cred()
    if not page_id or not token:
        print("NEEDS_TOKEN: .env に FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN を設定してください")
        return "TOKEN"
    size_mb = os.path.getsize(video_path) / 1e6
    print(f"Step: 動画アップロード（{size_mb:.1f}MB, 直接multipart）")
    try:
        with open(video_path, "rb") as f:
            r = requests.post(
                f"{GRAPH_VIDEO}/{page_id}/videos",
                data={"description": caption, "access_token": token},
                files={"source": (os.path.basename(video_path), f, "video/mp4")},
                timeout=1200,
            )
        d = r.json()
    except Exception as e:
        print(f"アップロード失敗: {e}")
        return "FAIL"
    if "error" in d:
        err = d["error"]
        print(f"APIエラー: code={err.get('code')} {err.get('message')}")
        if err.get("code") in (190, 102, 104):   # 190=token失効
            return "TOKEN"
        return "FAIL"
    vid = d.get("id")
    print(f"  投稿成功: video_id={vid}")
    return "OK:" + str(vid)


def post_first_comment(object_id, message):
    """投稿直後の1コメント目にCTAリンクを置く（本文に入れるとリーチが落ちるため）。"""
    _, token = _cred()
    try:
        d = requests.post(f"{GRAPH}/{object_id}/comments",
                          data={"message": message, "access_token": token},
                          timeout=60).json()
    except Exception as e:
        print(f"  コメント投稿に失敗（投稿自体は成功）: {e}")
        return None
    if "error" in d:
        print(f"  コメント投稿に失敗（投稿自体は成功）: {d['error'].get('message')}")
        return None
    print(f"  1コメント目にCTA設置: {d.get('id')}")
    return d.get("id")


def _post(video_path, category=""):
    caption, cta = build_caption(video_path)
    print(f"動画   : {os.path.basename(video_path)}")
    print(f"caption: {caption.replace(chr(10), ' / ')}")
    status = post_video_api(video_path, caption)
    if status.startswith("OK:"):
        if cta:
            post_first_comment(status[3:], cta)
        log = load_posted()
        log["files"].append({
            "file": os.path.basename(video_path),
            "abspath": video_path,
            "category": category,
            "video_id": status[3:],
            "caption": caption,
            "first_comment": cta,
            "uploaded_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
        save_posted(log)
        print(f"完了。累計投稿: {len(log['files'])}")
        return 0
    if status == "TOKEN":
        return 2
    return 1


def run(only_file=None, now=False):
    if only_file:
        if not os.path.exists(only_file):
            print(f"ファイルがありません: {only_file}")
            return 1
        return _post(only_file)

    log = load_posted()
    posts = [str(e.get("uploaded_at", "")) for e in log.get("files", [])
             if isinstance(e, dict) and e.get("uploaded_at")]
    today = time.strftime("%Y-%m-%d")
    today_n = sum(1 for a in posts if a.startswith(today))
    max_per_day = int(os.environ.get("FB_MAX_PER_DAY", "2"))
    if today_n >= max_per_day:
        print(f"本日は既に{today_n}件投稿済み（上限{max_per_day}）→ スキップ")
        return 0
    min_gap = int(os.environ.get("FB_MIN_GAP_MIN", "300"))
    if posts:
        try:
            last_dt = datetime.datetime.strptime(max(posts), "%Y-%m-%d %H:%M:%S")
            gap = (datetime.datetime.now() - last_dt).total_seconds() / 60
            if gap < min_gap:
                print(f"直近投稿から{gap:.0f}分（最小{min_gap}分）→ スキップ")
                return 0
        except Exception:
            pass

    jitter = int(os.environ.get("FB_JITTER_MIN", "12"))
    if not now and jitter > 0:
        wait_s = random.randint(0, jitter * 60)
        print(f"ジッター待機 {wait_s // 60}分{wait_s % 60}秒")
        time.sleep(wait_s)

    chosen = pick_video()
    if not chosen:
        return 0
    return _post(chosen["path"], chosen.get("category", ""))


def main():
    args = sys.argv[1:]
    if args and args[0] == "check":
        sys.exit(check())
    only = None
    now = "--now" in args
    if "--file" in args:
        i = args.index("--file")
        if i + 1 < len(args):
            only = args[i + 1]
    sys.exit(run(only_file=only, now=now))


if __name__ == "__main__":
    main()
