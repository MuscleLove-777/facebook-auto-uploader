# -*- coding: utf-8 -*-
"""
Facebook ページアクセストークン自動更新スクリプト

Facebookのページアクセストークンは60日で期限切れになる。
このスクリプトを定期実行（月1回など）してトークンを延長する。

使い方:
  python token_refresh.py
"""
import os
import sys
import requests
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))
GRAPH_API_VERSION = "v21.0"


def refresh_token(current_token):
    """長期トークンを更新（60日延長）"""
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": os.environ.get("FB_APP_ID", ""),
        "client_secret": os.environ.get("FB_APP_SECRET", ""),
        "fb_exchange_token": current_token,
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    new_token = data["access_token"]
    expires_in = data.get("expires_in", 0)
    expires_days = expires_in // 86400
    print(f"Token refreshed! Expires in {expires_days} days")
    return new_token


def check_token_info(token):
    """トークンの有効性と期限を確認"""
    url = f"https://graph.facebook.com/debug_token"
    params = {
        "input_token": token,
        "access_token": token,
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json().get("data", {})

    is_valid = data.get("is_valid", False)
    expires_at = data.get("expires_at", 0)

    if expires_at > 0:
        expire_date = datetime.fromtimestamp(expires_at, tz=JST)
        days_left = (expire_date - datetime.now(JST)).days
        print(f"Token valid: {is_valid}")
        print(f"Expires: {expire_date.strftime('%Y-%m-%d %H:%M JST')}")
        print(f"Days left: {days_left}")
        return days_left
    else:
        print(f"Token valid: {is_valid}")
        print("No expiration (never expires)")
        return 999


def get_page_token(user_token, page_id):
    """ユーザートークンからページアクセストークンを取得"""
    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{page_id}"
    params = {
        "fields": "access_token",
        "access_token": user_token,
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()
    page_token = data.get("access_token")
    if page_token:
        print(f"Page token obtained for page {page_id}")
    return page_token


def main():
    token = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
    if not token:
        print("Error: FB_PAGE_ACCESS_TOKEN not set")
        return 1

    print(f"Checking token... ({datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')})")
    days_left = check_token_info(token)

    if days_left < 14:
        print("\nToken expiring soon! Refreshing...")
        app_id = os.environ.get("FB_APP_ID", "")
        app_secret = os.environ.get("FB_APP_SECRET", "")
        if not app_id or not app_secret:
            print("Error: FB_APP_ID and FB_APP_SECRET required for refresh")
            print("Set these in GitHub Secrets or environment variables")
            return 1
        new_token = refresh_token(token)
        print(f"\nNew token (first 20 chars): {new_token[:20]}...")
        print("Update FB_PAGE_ACCESS_TOKEN in GitHub Secrets with this new token!")
        return 0
    else:
        print(f"\nToken OK. No refresh needed.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
