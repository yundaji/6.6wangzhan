import os
import re
import json
import asyncio
import requests
from bs4 import BeautifulSoup
from telegram import Bot

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SITE_URL = "https://video.sogou.com/list?listTab=film"
BASE_URL = "https://video.sogou.com"

SEEN_FILE = "seen_videos.json"
MAX_POSTS = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://video.sogou.com/",
}


def load_seen():
    if not os.path.exists(SEEN_FILE):
        return set()

    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except:
        return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, ensure_ascii=False, indent=2)


def get_html(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding
    return r.text


def full_url(url):
    if not url:
        return ""

    if url.startswith("//"):
        return "https:" + url

    if url.startswith("/"):
        return BASE_URL + url

    return url


def get_video_pages():
    html = get_html(SITE_URL)
    soup = BeautifulSoup(html, "html.parser")

    items = []

    for a in soup.find_all("a", href=True):
        title = a.get_text(strip=True)
        href = full_url(a.get("href"))

        if not title:
            img = a.find("img")
            if img:
                title = img.get("alt", "").strip()

        if not title:
            continue

        if "video.sogou.com" not in href:
            continue

        items.append({
            "title": title,
            "url": href
        })

    result = []
    used = set()

    for item in items:
        if item["url"] in used:
            continue

        used.add(item["url"])
        result.append(item)

    return result


def find_mp4_url(page_url):
    html = get_html(page_url)

    mp4_urls = []

    # 普通 mp4
    mp4_urls += re.findall(r'https?://[^"\']+?\.mp4[^"\']*', html)

    # 转义后的 mp4，例如 https:\/\/xxx.com\/video.mp4
    escaped_urls = re.findall(r'https?:\\/\\/[^"\']+?\.mp4[^"\']*', html)

    for url in escaped_urls:
        mp4_urls.append(url.replace("\\/", "/"))

    clean_urls = []

    for url in mp4_urls:
        if url not in clean_urls:
            clean_urls.append(url)

    if clean_urls:
        return clean_urls[0]

    return None


async def send_video_to_channel(title, page_url, video_url):
    bot = Bot(token=BOT_TOKEN)

    caption = (
        f"🎬 {title}\n\n"
        f"来源：搜狗视频\n"
        f"原页面：{page_url}"
    )

    await bot.send_video(
        chat_id=CHAT_ID,
        video=video_url,
        caption=caption[:1024],
        supports_streaming=True
    )


async def main():
    if not BOT_TOKEN:
        print("错误：没有设置 BOT_TOKEN")
        return

    if not CHAT_ID:
        print("错误：没有设置 CHAT_ID")
        return

    seen = load_seen()

    try:
        pages = get_video_pages()
    except Exception as e:
        print("抓取列表失败：", e)
        return

    print(f"找到 {len(pages)} 个视频页面")

    count = 0

    for item in pages:
        if count >= MAX_POSTS:
            break

        title = item["title"]
        page_url = item["url"]

        if page_url in seen:
            continue

        print("正在检查：", title, page_url)

        try:
            mp4_url = find_mp4_url(page_url)

            if not mp4_url:
                print("没有找到 mp4，跳过：", title)
                seen.add(page_url)
                continue

            print("找到 mp4：", mp4_url)

            await send_video_to_channel(title, page_url, mp4_url)

            print("发布成功：", title)

            seen.add(page_url)
            count += 1

        except Exception as e:
            print("发布失败：", title, e)

    save_seen(seen)

    print(f"完成，本次发布 {count} 个视频")


if __name__ == "__main__":
    asyncio.run(main())
