# PunjabTrends - Daily Trending Articles
# Punjab + India + World - 3 alag JSON banega
# Roz savere 7 vaje GitHub Actions naal chalda hai
# Gemini Flash-Lite - FREE 500/day

import os
import json
import re
import time
import feedparser
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# ================= CONFIG =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODEL = "gemini-2.5-flash-lite"

# Kitne topics har section vich
TOP_N = 7  # 10 chahida tan 10 kar de

IST = ZoneInfo("Asia/Kolkata")
TODAY = datetime.now(IST)
DATE_STR = TODAY.strftime("%d %B %Y")  # 14 November 2026
DATE_FILE = TODAY.strftime("%Y-%m-%d")  # 2026-11-14
# Punjabi date layi - Blogger vich dikhayenge, yahan English rakha

# ================= RSS FEEDS =================
RSS_PUNJAB = [
    "https://www.ptcnews.tv/rssfeed/trending-in-punjabi",
    "https://punjab.news18.com/commonfeeds/v1/pan/rss/punjab.xml",
    "https://www.ptcnews.tv/rssfeed/punjab",
    "https://news.google.com/rss?hl=pa-IN&gl=IN%ceid=IN:pa",
]

RSS_INDIA = [
    "https://news.google.com/rss?hl=pa-IN&gl=IN%ceid=IN:pa",
    "https://punjab.news18.com/commonfeeds/v1/pan/rss/national.xml",
    "https://www.ptcnews.tv/rssfeed/punjabi-news-nation",
]

RSS_WORLD = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.ptcnews.tv/rssfeed/punjabi-news-world",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://rss.dw.com/rdf/rss-en-top",
    "https://news.google.com/rss?hl=pa-IN&gl=IN%ceid=IN:pa",
]

# ================= HELPERS =================
def clean_text(t):
    if not t:
        return ""
    t = re.sub(r'<[^>]+>', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def get_trending_topics(rss_list, max_topics=20):
    """RSS ton titles kaddo - duplicate hata ke"""
    seen = set()
    topics = []
    for url in rss_list:
        try:
            print(f"RSS padh reha: {url}")
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]:
                title = clean_text(entry.get("title", ""))
                # Chhota / bekar title chaddo
                if len(title) < 10 or len(title) > 120:
                    continue
                low = title.lower()
                if low in seen:
                    continue
                # Ad / live blog chaddo
                if any(x in low for x in ["live updates", "live:", "watch:", "video:"]):
                    continue
                seen.add(low)
                topics.append(title)
                if len(topics) >= max_topics:
                    return topics
        except Exception as e:
            print(f"RSS error {url}: {e}")
            continue
    return topics

def call_gemini(prompt):
    """Gemini API nu call karo"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7, "maxOutputTokens": 3500}
    }
    try:
        r = requests.post(url, json=payload, timeout=90)
        if r.status_code != 200:
            print(f"Gemini error {r.status_code}: {r.text[:500]}")
            return ""
        data = r.json()
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return text.strip()
    except Exception as e:
        print(f"Gemini call error: {e}")
        return ""

def clean_article(article):
    """** stars, # , extra date hatao"""
    if not article:
        return ""
    # ** bold hatao - Blogger vich ** dikhda si
    article = article.replace("**", "")
    article = article.replace("##", "").replace("###", "")
    # Shuru vich date line je hove tan hatao - Blogger vich date alag dikhayenge
    # Article de andar date line rehndi hai tan theek hai, heading wali date nahi chahidi
    lines = article.split("\n")
    # Pehli 2 lines vich je sirf date hove tan hatao
    cleaned_lines = []
    for i, line in enumerate(lines):
        s = line.strip()
        if i < 2 and re.match(r'^(14|15|16|17|18|19|20|21|22|23|24|25|26|27|28|29|30|31|1|2|3|4|5|6|7|8|9|10|11|12|13)\s', s) and len(s) < 40 and "ਸਤਿ" not in s:
            continue
        cleaned_lines.append(line)
    article = "\n".join(cleaned_lines)
    return article.strip()

def make_article(topic, section):
    """Ik topic layi Punjabi Gurmukhi vich article banao"""
    if section == "punjab":
        scope = "Sirf Punjab naal sambandh rakh. Punjab da impact zaroor dass."
        avoid = "India ya Duniya de hor topics na pa."
    elif section == "india":
        scope = "Sirf India naal sambandh rakh. Punjab de topics na pa. Punjab te ki asar pavega, oh v dass."
        avoid = "Punjab de local topics na pa."
    else:
        scope = "Sirf Duniya (International) naal sambandh rakh. India-Punjab de local topics na pa. Punjab / India te ki asar pavega, oh v dass."
        avoid = "India-Punjab de local topics na pa."

    prompt = f"""
Tusi ik Punjabi news writer ho. Heth likhe Trending Topic te Gurmukhi Punjabi vich ik saada, saaf-suthra article likho.

Topic: {topic}
Section: {section} - {scope} {avoid}

Zaroori niyam:
1. Boli: Sirf Gurmukhi Punjabi. Roman Punjabi bilkul na varteo.
2. ** , ## , # , * - kade v na varteo. Bold layi ** na pao.
3. Shuru vich date ya heading na pao. Sidha "Sat Sri Akal Dosto!" naal shuru karo.
4. Article di lambai: 350-450 shabd.
5. Structure:
   - Para 1: Ki hoya? Ki trending hai te kyon?
   - Para 2: Background - Pehlan ki si, hun ki hai?
   - Para 3: Dooje passe ki kehnde ne? Dooji dhir / virodhi pakh ki kehnda?
   - Para 4: Dooje states / deshan naal tulna - othe ki hoya?
   - Para 5: Punjab te ki asar? Kitna safal ya asafal?
   - Para 6: Agge ki hovega? What next?
6. Gallan saaf, saadi bhasha vich. Koi jhoothi khabar na banao. Je pakki jaankari na hove tan "hun tak mili jaankari mutabik" likho.
7. Sirf article da text deo. Koi heading, date, ya ** na deo.
"""
    raw = call_gemini(prompt)
    time.sleep(2)  # Rate limit ton bachan layi
    return clean_article(raw)

def build_section(section_name, rss_list, output_file):
    print(f"\n========== {section_name.upper()} ==========")
    topics = get_trending_topics(rss_list, max_topics=TOP_N + 10)
    print(f"Topics mile: {len(topics)}")

    # Je RSS fail hove tan purani file ton topics le lo (fallback)
    if len(topics) < 3:
        print("RSS ton ghat topics mile, purani file check kar reha...")
        try:
            with open(output_file, "r", encoding="utf-8") as f:
                old = json.load(f)
                topics = [x["topic"] for x in old.get("items", [])][:TOP_N]
        except:
            topics = []

    items = []
    for topic in topics[:TOP_N]:
        print(f"Article bana reha: {topic}")
        article = make_article(topic, section_name)
        if not article or len(article) < 200:
            print(f"  -> Chhota / khali article, skip: {topic}")
            continue
        items.append({"topic": topic, "article": article})
        print(f"  -> Ho gaya ({len(article)} chars)")

    data = {
        "date": DATE_STR,
        "date_file": DATE_FILE,
        "section": section_name,
        "updated": TODAY.strftime("%Y-%m-%d %H:%M IST"),
        "items": items
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved: {output_file} - {len(items)} articles")

    # Archive - purane din de article rahenge
    os.makedirs(f"archive/{section_name}", exist_ok=True)
    with open(f"archive/{section_name}/{DATE_FILE}.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data

def main():
    print(f"Start: {TODAY} - Punjab + India + World")
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY nahi mili! GitHub Secrets vich pao.")
        return

    build_section("punjab", RSS_PUNJAB, "today_punjab.json")
    build_section("india", RSS_INDIA, "today_india.json")
    build_section("world", RSS_WORLD, "today_world.json")

    print("\nSab ho gaya! 3 files ban gayian:")
    print("- today_punjab.json")
    print("- today_india.json")
    print("- today_world.json")

if __name__ == "__main__":
    main()
