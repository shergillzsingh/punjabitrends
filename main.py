# PunjabTrends - Daily Trending Articles - FINAL VERSION
# Punjab + India + World
# - RSS Hindi / English hove tan v Gemini Punjabi vich likhega
# - Topic v Punjabi vich hovega
# - Je RSS fail hove tan Fallback naal v article banega - items [] nahi aayega
# - Roz savere 7 vaje GitHub Actions naal chalda hai
# - Gemini Flash-Lite - FREE 500/day

import os
import json
import re
import time
import feedparser
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

# ================= CONFIG =================
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
MODELS = ["gemini-3.8-flash", "gemini-3-flash", "gemini-2.5-flash", "gemini-2.5-flash-lite"]

TOP_N = 10  # Har section vich kinne lekh - 10 chahide tan 10 kar de

IST = ZoneInfo("Asia/Kolkata")
TODAY = datetime.now(IST)
DATE_STR = TODAY.strftime("%d %B %Y")  # 14 November 2026
DATE_FILE = TODAY.strftime("%Y-%m-%d")  # 2026-11-14

# ================= RSS FEEDS - TERE WALE =================
RSS_PUNJAB = [
    "https://www.ptcnews.tv/rssfeed/trending-in-punjabi",
    "https://punjab.news18.com/commonfeeds/v1/pan/rss/punjab.xml",
    "https://www.ptcnews.tv/rssfeed/punjab",
    "https://www.bhaskar.com/rss-v1--category-1743.xml",
    "https://publish.tribuneindia.com/state/punjab/feed/",
    "https://raw.githubusercontent.com/bbc/world-service-rss/refs/heads/main/punjabi.md",
]

RSS_INDIA = [
    "https://www.bhaskar.com/rss-v1--category-1061.xml",
    "https://www.navjivanindia.com/stories.rss?section=india",
    "https://www.thehindu.com/news/national/feeder/default.rss",
    "https://indianexpress.com/section/india/feed/",
]

RSS_WORLD = [
    "https://www.bhaskar.com/rss-v1--category-1125.xml",
    "https://www.thehindu.com/news/international/feeder/default.rss",
    "https://indianexpress.com/section/world/feed/",
    "https://feeds.bbci.co.uk/news/world/rss.xml",
]

# ================= FALLBACK - Je RSS khali hove =================
FALLBACK = {
    "punjab": [
        "Punjab vich aaj da mausam",
        "Punjab di mandi vich fasal da bhav",
        "Punjab vich nasha khilaf action",
        "Chandigarh traffic challan",
        "Punjab school college ch chhuttiyan",
        "Punjab vich bijli pani di samasya",
        "Punjab de kisan di mang",
    ],
    "india": [
        "India vich aaj da mausam",
        "Delhi vich pradushan",
        "India cricket team da match",
        "Petrol diesel da rate",
        "India vich nayi yojana",
        "Sansad vich aaj di charcha",
        "India vich railway di khabar",
    ],
    "world": [
        "America vich aaj di vaddi khabar",
        "Duniya vich mausam da badlaav",
        "World cricket di khabar",
        "Canada vich Punjabi community",
        "UK vich aaj di khabar",
        "Australia vich Punjabi",
        "Duniya vich tel da rate",
    ],
}

# ================= HELPERS =================
def clean_text(t):
    if not t:
        return ""
    t = re.sub(r'<[^>]+>', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t

def get_trending_topics(rss_list, section):
    seen = set()
    topics = []
    for url in rss_list:
        try:
            print(f"RSS padh reha: {url}")
            feed = feedparser.parse(url)
            print(f"  -> Entries mile: {len(feed.entries)}")
            for entry in feed.entries[:15]:
                title = clean_text(entry.get("title", ""))
                if len(title) < 10 or len(title) > 120:
                    continue
                low = title.lower()
                if low in seen:
                    continue
                if any(x in low for x in ["live updates", "live:", "watch:", "video:"]):
                    continue
                seen.add(low)
                topics.append(title)
                if len(topics) >= TOP_N:
                    return topics
        except Exception as e:
            print(f"RSS error {url}: {e}")
            continue
    print(f"RSS ton topics mile: {len(topics)}")
    if len(topics) < 3:
        print(f"RSS khali hai, FALLBACK use kar reha: {section}")
        for t in FALLBACK.get(section, []):
            if t.lower() not in seen:
                topics.append(t)
            if len(topics) >= TOP_N:
                break
    return topics[:TOP_N]

def call_gemini(prompt):
    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={GEMINI_API_KEY}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 3500}
        }
        try:
            print(f"Gemini try: {model}")
            r = requests.post(url, json=payload, timeout=90)
            print(f"  -> Status: {r.status_code}")
            if r.status_code != 200:
                print(f"  -> Error: {r.text[:400]}")
                continue
            data = r.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            print(f"  -> Mil gaya: {len(text)} chars")
            return text.strip()
        except Exception as e:
            print(f"  -> Exception: {e}")
            continue
    print("Sab model fail ho gaye!")
    return ""

def clean_article(article):
    if not article:
        return ""
    article = article.replace("**", "").replace("##", "").replace("###", "")
    return article.strip()

def translate_topic_to_punjabi(topic):
    """Hindi / English Topic nu Gurmukhi Punjabi vich badlo"""
    prompt = f"""
Heth likhe Topic nu Gurmukhi Punjabi vich anuvad karo.
Topic Hindi ya English vich ho sakda hai.

Topic: {topic}

Niyam:
1. Sirf Gurmukhi Punjabi vich likho. Don't use Roman Punjabi.
2. Sirf 1 line deo - sirf Punjabi Topic. Koi ** , ## , heading, ya vyakhya na deo.
3. Jivein: "Delhi Mein Pradushan Badha" -> "ਦਿੱਲੀ ਵਿੱਚ ਪ੍ਰਦੂਸ਼ਣ ਵਧਿਆ"
"""
    punjabi_topic = call_gemini(prompt)
    if punjabi_topic:
        punjabi_topic = punjabi_topic.split("\n")[0].strip()
        punjabi_topic = punjabi_topic.replace("**", "").replace("##", "").strip()
        if 5 < len(punjabi_topic) < 120:
            return punjabi_topic
    return topic

def make_article(topic, section):
    if section == "punjab":
        scope = "Sirf Punjab naal sambandh rakh. Punjab da impact zaroor dass."
    elif section == "india":
        scope = "Sirf India naal sambandh rakh. Punjab de local topics na pa. Punjab te ki asar pavega, oh v dass."
    else:
        scope = "Sirf Duniya (International) naal sambandh rakh. India-Punjab de local topics na pa. Punjab / India te ki asar pavega, oh v dass."

    prompt = f"""
Tusi ik Punjabi news writer ho. Heth likhe Trending Topic te Gurmukhi Punjabi vich ik saada, saaf-suthra article likho.
Topic: {topic}
Section: {section} - {scope}

Zaroori niyam:
1. Topic Hindi ya English vich v ho sakda hai - tusi usnu padh ke Gurmukhi Punjabi vich samjhao. 
2. Boli: Sirf Gurmukhi Punjabi. Don't use Roman Punjabi.
3. ** , ## , # , * - kade v na varteo. Bold layi ** na pao.
4. Shuru vich date ya heading na pao. Sidha "Topic" naal shuru karo.
5. Article di lambai: 350-450 shabd.
6. Structure:
   - Para 1: What Happened? Why this topic in trending?
   - Para 2: Background - Pehlan ki si, hun ki hai?
   - Para 3: What peoples/opponets says about this topic,
   - Para 4: Dooje states / deshan naal tulna - othe ki hoya related to this topic.
   - Para 5: Punjab te ki asar? successfull or unsuccessfull
   - Para 6: Agge ki hovega? What next?
7. Koi jhoothi khabar na banao. Je pakki jaankari na hove tan "hun tak mili jaankari mutabik" likho.
8. Sirf article da text deo. Koi heading, date, ya ** na deo.
"""
    raw = call_gemini(prompt)
    time.sleep(2)
    return clean_article(raw)

def build_section(section_name, rss_list, output_file):
    print(f"\n========== {section_name.upper()} ==========")
    topics = get_trending_topics(rss_list, section_name)
    print(f"Final topics: {topics}")
    items = []
    for topic in topics[:TOP_N]:
        print(f"Article bana reha: {topic}")
        # Pehlan Topic nu Punjabi vich kar lo - Hindi / English -> Punjabi
        punjabi_topic = translate_topic_to_punjabi(topic)
        print(f"  -> Punjabi Topic: {punjabi_topic}")
        topic = punjabi_topic
        article = make_article(topic, section_name)
        if not article or len(article) < 200:
            print(f"  -> Chhota/khali, dobara try: {topic}")
            article = make_article(topic, section_name)
        if not article or len(article) < 200:
            print(f"  -> Fer v khali, chhota article bana reha taan items [] na hove")
            article = f"Sat Sri Akal Dosto! Aaj hai {DATE_STR}. Aao gall karde haan {topic} baare. Ajjkal social media ton lai ke chaah de khokheyaan tak ise gall di charcha hai. Hun tak mili jaankari mutabik eh mudda lokan vich kaafi charcha vich hai. Punjab de lokan te isda sidha asar penda hai. Agge ki hovega, eh aoun wale dina vich pata lagega. Tusi is baare ki sochde ho, comment vich zaroor dasso."
        items.append({"topic": topic, "article": article})
        print(f"  -> Ho gaya ({len(article)} chars)")
        time.sleep(1)

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
    print(f"API Key hai? {bool(GEMINI_API_KEY)} - Length: {len(GEMINI_API_KEY) if GEMINI_API_KEY else 0}")
    if not GEMINI_API_KEY:
        print("ERROR: GEMINI_API_KEY nahi mili! GitHub Settings > Secrets vich pao.")
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
