# -*- coding: utf-8 -*-
"""
token_refresh_local.py — ローカル版トークン自動更新（.env を直接書き換える）

役割:
  1. 現在の FB_PAGE_ACCESS_TOKEN の残日数を確認
  2. 残り14日未満（または --force）なら
       短期ユーザートークン → 長期ユーザートークン（60日）→ ページトークン（無期限）
     を取り直して .env を更新
  3. トークン値は一切標準出力に出さない（画面・ログに残さない）

使い方:
  python token_refresh_local.py             # 定期実行（残日数チェックのみ→必要なら更新）
  python token_refresh_local.py --bootstrap # クリップボードのユーザートークンから初期発行
  python token_refresh_local.py --check     # 状態表示のみ

必要な .env:
  FB_APP_ID / FB_APP_SECRET / FB_PAGE_ID / FB_PAGE_ACCESS_TOKEN

exit: 0=OK, 1=失敗, 2=設定不足
"""
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
ENV = os.path.join(HERE, ".env")
GRAPH = "https://graph.facebook.com/v21.0"
JST = timezone(timedelta(hours=9))


def load_env():
    d = {}
    if os.path.exists(ENV):
        with open(ENV, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    d[k.strip()] = v.strip()
    return d


def save_env(updates):
    with open(ENV, encoding="utf-8") as f:
        text = f.read()
    for k, v in updates.items():
        if re.search(rf"(?m)^{k}=", text):
            text = re.sub(rf"(?m)^{k}=.*$", f"{k}={v}", text)
        else:
            text = text.rstrip("\n") + f"\n{k}={v}\n"
    with open(ENV, "w", encoding="utf-8") as f:
        f.write(text)


def days_left(token):
    """残日数。無期限なら 999、失効・不正なら -1。"""
    try:
        d = requests.get(f"{GRAPH}/debug_token",
                         params={"input_token": token, "access_token": token},
                         timeout=30).json().get("data", {})
    except Exception as e:
        print(f"debug_token 失敗: {e}")
        return -1
    if not d.get("is_valid"):
        return -1
    exp = d.get("expires_at", 0)
    if not exp:
        return 999
    return (datetime.fromtimestamp(exp, tz=JST) - datetime.now(JST)).days


def clipboard_token():
    out = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                         capture_output=True, text=True, encoding="utf-8").stdout.strip()
    return out if out.startswith("EAA") else ""


def issue(user_token, env):
    """短期ユーザートークン → 長期ユーザートークン → ページトークン。"""
    r = requests.get(f"{GRAPH}/oauth/access_token", timeout=30, params={
        "grant_type": "fb_exchange_token",
        "client_id": env.get("FB_APP_ID", ""),
        "client_secret": env.get("FB_APP_SECRET", ""),
        "fb_exchange_token": user_token,
    }).json()
    if "error" in r:
        print(f"長期化に失敗: {r['error'].get('message')}")
        return None
    long_user = r["access_token"]
    p = requests.get(f"{GRAPH}/{env['FB_PAGE_ID']}", timeout=30,
                     params={"fields": "access_token", "access_token": long_user}).json()
    if "error" in p or not p.get("access_token"):
        print(f"ページトークン取得に失敗: {p.get('error', {}).get('message')}")
        return None
    return p["access_token"]


def main():
    args = sys.argv[1:]
    env = load_env()
    token = env.get("FB_PAGE_ACCESS_TOKEN", "")

    if "--check" in args:
        if not token:
            print("トークン未設定")
            return 2
        n = days_left(token)
        print("無期限トークン（更新不要）" if n == 999 else
              ("失効している" if n < 0 else f"残り {n} 日"))
        return 0

    if not env.get("FB_APP_ID") or not env.get("FB_APP_SECRET"):
        print("FB_APP_ID / FB_APP_SECRET が未設定（.env）")
        return 2

    if "--bootstrap" in args:
        ut = clipboard_token()
        if not ut:
            print("クリップボードに短期ユーザートークンがありません")
            return 2
        new = issue(ut, env)
        if not new:
            return 1
        save_env({"FB_PAGE_ACCESS_TOKEN": new})
        subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value ' '"])
        n = days_left(new)
        print("更新完了: " + ("無期限" if n == 999 else f"残り {n} 日"))
        return 0

    if not token:
        print("FB_PAGE_ACCESS_TOKEN が未設定")
        return 2
    n = days_left(token)
    if n == 999:
        print("無期限トークン。更新不要。")
        return 0
    if n >= 14:
        print(f"残り {n} 日。更新不要。")
        return 0

    print(f"残り {n} 日 → 更新する")
    new = issue(token, env)   # ページトークンでも fb_exchange_token は通る
    if not new:
        print("自動更新に失敗。ブラウザで再取得してから --bootstrap を実行すること。")
        return 1
    save_env({"FB_PAGE_ACCESS_TOKEN": new})
    n2 = days_left(new)
    print("更新完了: " + ("無期限" if n2 == 999 else f"残り {n2} 日"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
