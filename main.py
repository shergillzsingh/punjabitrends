import os
import feedparser
import json
import time
import re
from datetime import datetime
from google import genai
from google.genai import types

# --- 1. API KEY ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY not found!")
    exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)

# --- 2. MODELS (ਸਿਰਫ਼ ਅਸਲੀ ਤੇ ਚੱਲਣ ਵਾਲੇ ਮਾਡਲ) ---
MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-3-flash",
    "gemini-2.5-flash",
    "gemini-3.8-flash",
]

# --- 3. RSS LINKS ---
RSS_PUNJAB = [
    "https://punjab.news18.com/commonfeeds/v1/pan/rss/punjab.xml",
    "https://publish.tribuneindia.com/state/punjab/feed/",
    "https://feeds.bbci.co.uk/punjabi/rss.xml",
    "https://www.ptcnews.tv/rssfeed/punjab",
    "https://www.bhaskar.com/rss-v1--category-1743.xml",
]
RSS_INDIA = [
    "https://www.thehindu.com/news/national/feeder/default.rss",
    "https://www.bhaskar.com/rss-v1--category-1061.xml",
    "https://indianexpress.com/section/india/feed/",
    "https://www.navjivanindia.com/stories.rss?section=india",
]
RSS_WORLD = [
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.thehindu.com/news/international/feeder/default.rss",
    "https://www.bhaskar.com/rss-v1--category-1125.xml",
    "https://indianexpress.com/section/world/feed/",
]

# --- 4. CATEGORY RULES ---
CATEGORY_RULES = {
    "punjab": {
        "allowed": "ONLY news that happened IN Punjab, or is directly about Punjab people, Punjab government, Punjab politics, Punjab cities.",
        "blocked": "DO NOT include pure Delhi / Mumbai / World news where Punjab is not mentioned at all.",
    },
    "india": {
        "allowed": "ONLY news that happened IN India (outside Punjab), or is about India national government.",
        "blocked": "DO NOT include Punjab-only local news and DO NOT include pure World news.",
    },
    "world": {
        "allowed": "ONLY news that happened OUTSIDE India. USA, UK, China, Pakistan, Russia, Ukraine, etc.",
        "blocked": "DO NOT include Punjab news. DO NOT include India news.",
    }
}

# --- 5. SYSTEM PROMPT ---
SYSTEM_PROMPT = """
ਤੁਸੀਂ ਇੱਕ ਤਜਰਬੇਕਾਰ ਪੰਜਾਬੀ ਖੋਜੀ ਪੱਤਰਕਾਰ (Investigative Journalist) ਅਤੇ ਵਿਸ਼ਲੇਸ਼ਕ ਹੋ।
ਭਾਸ਼ਾ: ਸਿਰਫ਼ ਸ਼ੁੱਧ, ਸਰਲ ਅਤੇ ਬੋਲਚਾਲ ਵਾਲੀ ਪੰਜਾਬੀ (ਗੁਰਮੁਖੀ ਲਿਪੀ)। ਕੋਈ ਅੰਗਰੇਜ਼ੀ ਜਾਂ ਹਿੰਦੀ ਸ਼ਬਦ ਨਾ ਵਰਤੋ (ਸਿਰਫ਼ ਲੋੜ ਪੈਣ 'ਤੇ ਖਾਸ ਨਾਮ ਜਿਵੇਂ ED, SIT, NATO ਲਿਖ ਸਕਦੇ ਹੋ)।
ਅੰਦਾਜ਼: ਗੰਭੀਰ, ਤੱਥਾਂ 'ਤੇ ਆਧਾਰਿਤ, ਪਰ ਆਮ ਲੋਕਾਂ ਨੂੰ ਆਸਾਨੀ ਨਾਲ ਸਮਝ ਆਉਣ ਵਾਲੀ ਕਹਾਣੀ ਵਰਗੀ ਸ਼ੈਲੀ। ਹਰ ਪੁਆਇੰਟ ਪਿਛਲੇ ਪੁਆਇੰਟ ਨਾਲ ਜੁੜਿਆ ਹੋਣਾ ਚਾਹੀਦਾ ਹੈ।
ਅੰਦਰੂਨੀ ਕੋਟਸ: JSON ਟੁੱਟਣ ਤੋਂ ਬਚਾਉਣ ਲਈ ਪੰਜਾਬੀ ਵਾਕਾਂ ਦੇ ਅੰਦਰ ਡਬਲ ਕੋਟਸ (") ਦੀ ਥਾਂ ਸਿੰਗਲ ਕੋਟਸ (') ਵਰਤੋ।
"""

def clean_html(raw_html):
    """HTML ਟੈਗਸ ਹਟਾ ਕੇ ਸਾਫ਼ ਟੈਕਸਟ ਕੱਢਣ ਲਈ"""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return " ".join(cleantext.split())

def get_trending_topics(rss_list):
    all_entries = []
    for url in rss_list:
        try:
            feed = feedparser.parse(url)
            print(f"RSS OK: {url} - Found {len(feed.entries)} entries")
            for entry in feed.entries[:25]:
                title = entry.get('title', '').strip()
                summary = clean_html(entry.get('summary', '') or entry.get('description', ''))
                if title:
                    all_entries.append({
                        "title": title,
                        "summary": summary[:400]  # ਖ਼ਬਰ ਦੀ ਅਸਲੀ ਡਿਟੇਲ (400 ਅੱਖਰਾਂ ਤੱਕ)
                    })
        except Exception as e:
            print(f"RSS Failed: {url} - {e}")
            continue
            
    topics = []
    seen = set()
    for item in all_entries:
        low = item["title"].lower().strip()
        if low in seen:
            continue
        seen.add(low)
        count = 0
        w1 = set(re.findall(r'\w+', low))
        for item2 in all_entries:
            w2 = set(re.findall(r'\w+', item2["title"].lower()))
            if w1 and w2 and len(w1 & w2) / max(len(w1), 1) > 0.5:
                count += 1
        topics.append({
            "count": count,
            "title": item["title"],
            "details": item["summary"]
        })
        
    topics = sorted(topics, key=lambda x: x["count"], reverse=True)
    return topics[:25]

def safe_wait(seconds=12):
    print(f"Waiting {seconds} sec to avoid Rate Limit...")
    time.sleep(seconds)

def extract_json(text):
    text = text.strip()
    match = re.search(r'\[.*\]', text, re.DOTALL)
    if match:
        text = match.group(0)
    return json.loads(text)

# --- 6. AI CALL ---
def call_ai(category, topics, count_needed=5):
    today_date = datetime.now().strftime("%d %B %Y")
    news_feed_text = ""
    for t in topics:
        news_feed_text += f"\n- HEADLINE (Score {t['count']}): {t['title']}\n  DETAILS FROM NEWS: {t['details']}\n"

    rules = CATEGORY_RULES[category]

    prompt = f"""
    Today's Date: {today_date}
    INPUT News Data for category: {category}.
    
    CATEGORY FILTER:
    ALLOWED: {rules['allowed']}
    BLOCKED: {rules['blocked']}

    TASK:
    1. Pick the top {count_needed} MOST IMPORTANT trending news from the list below.
    2. Combine the provided 'DETAILS FROM NEWS' (for today's latest facts) with your own deep knowledge (for past history, exact numbers/votes/budgets, and old controversies).
    3. Return EXACTLY {count_needed} news items in valid JSON array format.

    TITLE RULE:
    - Short, crisp newspaper headline in Gurmukhi (MAX 8-10 words, MAX 60 chars).

    POINTS STRUCTURE - 8 DEEP & CONNECTED POINTS (Write 3-4 detailed lines per point):
    Point 1 - ਅੱਜ ਦੀ ਤਾਜ਼ਾ ਸਥਿਤੀ (Current Update): ਖ਼ਬਰ ਦੀ ਸ਼ੁਰੂਆਤ ਕਹਾਣੀ ਵਾਂਗ ਕਰੋ। ਅੱਜ ਦੀ ਤਰੀਕ ਤੱਕ ਇਸ ਮਾਮਲੇ ਵਿੱਚ ਕੀ ਨਵਾਂ ਵਾਪਰਿਆ ਹੈ? ਕਿਸ ਨੇ ਕੀ ਬਿਆਨ ਦਿੱਤਾ?
    Point 2 - ਪੂਰਾ ਘਟਨਾਕ੍ਰਮ (What Happened): ਮਾਮਲਾ ਸ਼ੁਰੂ ਕਿਵੇਂ ਹੋਇਆ? ਕਦੋਂ ਅਤੇ ਕਿੱਥੇ ਵਾਪਰਿਆ? ਪੂਰਾ ਪਿਛੋਕੜ ਦੱਸੋ। ਜੇ ਕਿਸੇ ਵਿਅਕਤੀ ਬਾਰੇ ਹੈ ਤਾਂ ਉਸ ਦਾ ਸਿਆਸੀ/ਸਮਾਜਿਕ ਪਿਛੋਕੜ ਦੱਸੋ।
    Point 3 - ਪੰਜਾਬ, ਭਾਰਤ ਅਤੇ ਦੁਨੀਆਂ ਪੱਧਰ 'ਤੇ ਸਥਿਤੀ (Regional to Global Context): ਇਸ ਮੁੱਦੇ ਜਾਂ ਚੀਜ਼ ਦੀ ਪੰਜਾਬ ਵਿੱਚ ਕੀ ਸਥਿਤੀ ਹੈ, ਪੂਰੇ ਭਾਰਤ ਵਿੱਚ ਕੀ ਹਾਲ ਹੈ, ਅਤੇ ਦੁਨੀਆਂ ਜਾਂ ਪ੍ਰਵਾਸੀ ਪੰਜਾਬੀਆਂ ਵਿੱਚ ਇਸ ਦਾ ਕੀ ਅਸਰ ਹੈ?
    Point 4 - ਅੰਕੜੇ ਅਤੇ ਤੱਥ (Data & Statistics): ਅਸਲੀ ਅੰਕੜੇ ਦਿਓ—ਜਿਵੇਂ ਬਜਟ, ਵੋਟਾਂ ਦਾ ਫ਼ਰਕ, ਨੁਕਸਾਨ ਦੀ ਰਕਮ, ਤਰੀਕਾਂ, ਜਾਂ ਕਿੰਨੇ ਲੋਕ ਪ੍ਰਭਾਵਿਤ ਹੋਏ।
    Point 5 - ਫਾਇਦੇ / ਸਕਾਰਾਤਮਕ ਪੱਖ (Benefits): ਇਸ ਕਦਮ, ਨੀਤੀ ਜਾਂ ਵਿਅਕਤੀ ਦੇ ਕੰਮਾਂ ਨਾਲ ਆਮ ਲੋਕਾਂ, ਕਿਸਾਨਾਂ ਜਾਂ ਨੌਜਵਾਨਾਂ ਨੂੰ ਕੀ ਫਾਇਦਾ ਹੋਇਆ ਹੈ?
    Point 6 - ਨੁਕਸਾਨ / ਕਮੀਆਂ (Drawbacks & Impact): ਇਸ ਦਾ ਨਕਾਰਾਤਮਕ ਅਸਰ ਕੀ ਹੈ? ਆਮ ਆਦਮੀ ਦੀ ਜ਼ਿੰਦਗੀ 'ਤੇ ਕੀ ਬੋਝ ਪਿਆ ਹੈ?
    Point 7 - ਵਿਵਾਦ / ਕੰਟ੍ਰੋਵਰਸੀ (Controversies): ਇਸ ਵਿਸ਼ੇ ਨਾਲ ਜੁੜੇ ਛੋਟੇ ਪੱਧਰ ਤੋਂ ਲੈ ਕੇ ਵੱਡੇ ਪੱਧਰ ਤੱਕ ਦੇ ਸਾਰੇ ਵਿਵਾਦ ਦੱਸੋ। ਵਿਰੋਧੀ ਧਿਰ, ਅਦਾਲਤ ਜਾਂ ਲੋਕ ਕੀ ਇਲਜ਼ਾਮ ਲਾ ਰਹੇ ਹਨ ਅਤੇ ਦੂਜੀ ਧਿਰ ਦੀ ਕੀ ਸਫ਼ਾਈ ਹੈ?
    Point 8 - ਅੱਗੇ ਕੀ ਹੋਵੇਗਾ (What Next): ਭਵਿੱਖ ਵਿੱਚ ਇਸ ਦਾ ਕੀ ਨਤੀਜਾ ਨਿਕਲ ਸਕਦਾ ਹੈ? ਅਗਲੀ ਤਰੀਕ ਜਾਂ ਫ਼ੈਸਲਾ ਕੀ ਹੈ? ਅੰਤ ਵਿੱਚ ਪਾਠਕਾਂ ਲਈ ਇੱਕ ਸਵਾਲ ਛੱਡੋ।

    OUTPUT ONLY VALID JSON (No extra text before or after JSON):
    [
      {{
        "category": "{category}",
        "title": "ਛੋਟਾ ਸਿਰਲੇਖ ਗੁਰਮੁਖੀ ਵਿੱਚ",
        "points": [
          "Point 1 text...",
          "Point 2 text...",
          "Point 3 text...",
          "Point 4 text...",
          "Point 5 text...",
          "Point 6 text...",
          "Point 7 text...",
          "Point 8 text..."
        ],
        "source": "News Source Name",
        "trending_score": 5
      }}
    ]

    NEWS FEED DATA:
    {news_feed_text}
    """

    for i, model in enumerate(MODELS):
        try:
            print(f"Trying {model} for {category}... (Attempt {i+1}/{len(MODELS)})")
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.7,
                    max_output_tokens=32000,
                )
            )
            result = extract_json(resp.text)
            print(f"SUCCESS with {model} for {category} - Got {len(result)} news")
            return result
        except Exception as e:
            print(f"FAILED {model} for {category}: {e}")
            if i < len(MODELS) - 1:
                safe_wait(12)
            continue
    print(f"All models failed for {category}")
    return []

def build_section(category, rss_list, output_file):
    print(f"\n--- Building {category} -> {output_file} ---")
    topics = get_trending_topics(rss_list)
    
    news = call_ai(category, topics[:12], count_needed=5)
    
    if len(news) < 10:
        print(f"Fetching remaining news for {category}...")
        safe_wait(12)
        news2 = call_ai(category, topics[12:25], count_needed=5)
        seen_titles = set(n.get('title', '') for n in news)
        for n in news2:
            if n.get('title', '') not in seen_titles:
                news.append(n)
                seen_titles.add(n.get('title', ''))
                
    news = [n for n in news if n.get("category", "").lower() == category.lower()]
    news = news[:10]
    
    if news:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(news, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(news)} news to {output_file}")
    else:
        print(f"Failed {category}, old {output_file} will remain")
    return news

def main():
    build_section("punjab", RSS_PUNJAB, "today_punjab.json")
    safe_wait(12)
    build_section("india", RSS_INDIA, "today_india.json")
    safe_wait(12)
    build_section("world", RSS_WORLD, "today_world.json")
    print("\nSab ho gaya! 3 files updated:")
    print("- today_punjab.json (10 news)")
    print("- today_india.json (10 news)")
    print("- today_world.json (10 news)")

if __name__ == "__main__":
    main()
