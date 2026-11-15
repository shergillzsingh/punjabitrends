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

# --- 3. TRENDING & NEWS RSS LINKS ---
RSS_PUNJAB = [
    "https://punjab.news18.com/commonfeeds/v1/pan/rss/punjab.xml",
    "https://feeds.bbci.co.uk/punjabi/rss.xml",
    "https://publish.tribuneindia.com/state/punjab/feed/",
    "https://trends.google.com/trending/rss?geo=CA",  # ਕੈਨੇਡਾ ਟਰੈਂਡਜ਼ (ਪੰਜਾਬੀ ਭਾਈਚਾਰੇ ਦੇ ਮੁੱਦੇ)
    "https://www.ptcnews.tv/rssfeed/punjab",
]

RSS_INDIA = [
    "https://trends.google.com/trending/rss?geo=IN",  # ਭਾਰਤ ਦੇ ਲਾਈਵ Google Search ਟਰੈਂਡਜ਼
    "https://www.thehindu.com/news/national/feeder/default.rss",
    "https://www.bhaskar.com/rss-v1--category-1061.xml",
    "https://indianexpress.com/section/india/feed/",
]

RSS_WORLD = [
    "https://trends.google.com/trending/rss?geo=US",  # ਦੁਨੀਆਂ ਦੇ ਲਾਈਵ Google Search ਟਰੈਂਡਜ਼
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.thehindu.com/news/international/feeder/default.rss",
    "https://www.reddit.com/r/worldnews/hot/.rss",
]

# --- 4. CATEGORY RULES ---
CATEGORY_RULES = {
    "punjab": {
        "allowed": "ONLY trending topics and news directly related to Punjab, Punjabi people, Punjab politics, Punjabi music/cinema, or NRI Punjabis.",
        "blocked": "DO NOT include pure Bollywood, South India, or unrelated foreign news.",
    },
    "india": {
        "allowed": "ONLY trending topics and news in India (national politics, economy, cricket, tech, viral Indian issues).",
        "blocked": "DO NOT include Punjab-only local news and DO NOT include pure foreign news.",
    },
    "world": {
        "allowed": "ONLY global trending topics outside India (USA, UK, Canada, China, Russia, Middle East, global tech/events).",
        "blocked": "DO NOT include Punjab news. DO NOT include India-only news.",
    }
}

# --- 5. SYSTEM PROMPT ---
SYSTEM_PROMPT = """
ਤੁਸੀਂ ਇੱਕ ਤਜਰਬੇਕਾਰ ਪੰਜਾਬੀ ਟਰੈਂਡ ਐਨਾਲਿਸਟ (Trend Analyst) ਅਤੇ ਖੋਜੀ ਪੱਤਰਕਾਰ ਹੋ।
ਭਾਸ਼ਾ: ਸਿਰਫ਼ ਸ਼ੁੱਧ, ਸਰਲ ਅਤੇ ਬੋਲਚਾਲ ਵਾਲੀ ਪੰਜਾਬੀ (ਗੁਰਮੁਖੀ ਲਿਪੀ)। ਕੋਈ ਅੰਗਰੇਜ਼ੀ ਜਾਂ ਹਿੰਦੀ ਸ਼ਬਦ ਨਾ ਵਰਤੋ (ਸਿਰਫ਼ ਲੋੜ ਪੈਣ 'ਤੇ ਖਾਸ ਨਾਮ ਜਿਵੇਂ NASA, AI, ED, NATO ਲਿਖ ਸਕਦੇ ਹੋ)।
ਅੰਦਾਜ਼: ਦਿਲਚਸਪ, ਤੱਥਾਂ 'ਤੇ ਆਧਾਰਿਤ ਅਤੇ ਆਮ ਲੋਕਾਂ ਨੂੰ ਪੂਰੀ ਕਹਾਣੀ ਸਮਝਾਉਣ ਵਾਲਾ। ਹਰ ਪੁਆਇੰਟ ਪਿਛਲੇ ਪੁਆਇੰਟ ਨਾਲ ਜੁੜਿਆ ਹੋਣਾ ਚਾਹੀਦਾ ਹੈ।
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
            is_google_trend = "trends.google.com" in url
            print(f"RSS OK: {url} - Found {len(feed.entries)} entries")
            
            for entry in feed.entries[:25]:
                title = entry.get('title', '').strip()
                summary = clean_html(entry.get('summary', '') or entry.get('description', ''))
                
                # Google Trends ਵਿੱਚ ਸਰਚ ਟ੍ਰੈਫਿਕ (ਜਿਵੇਂ 50K+) ਵੀ ਮਿਲਦਾ ਹੈ
                traffic = entry.get('ht_approx_traffic', '')
                if traffic:
                    summary = f"[Google Search Traffic: {traffic}] {summary}"
                
                if title:
                    all_entries.append({
                        "title": title,
                        "summary": summary[:450],
                        "is_trend": is_google_trend
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
        
        # Google Trends ਵਾਲੇ ਟੌਪਿਕਸ ਨੂੰ ਵੱਧ ਸਕੋਰ ਦਿਓ
        count = 3 if item["is_trend"] else 1
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
        news_feed_text += f"\n- TRENDING TOPIC (Trend Score {t['count']}): {t['title']}\n  CONTEXT/DETAILS: {t['details']}\n"

    rules = CATEGORY_RULES[category]

    prompt = f"""
    Today's Date: {today_date}
    INPUT Live Trending Data for category: {category}.
    
    CATEGORY FILTER:
    ALLOWED: {rules['allowed']}
    BLOCKED: {rules['blocked']}

    TASK:
    1. Pick the top {count_needed} MOST VIRAL & IMPORTANT trending topics from the list below.
    2. Use 'CONTEXT/DETAILS' (for today's latest trigger) + your deep knowledge (for history, exact numbers/votes/traffic, and controversies) to write a complete trending report.
    3. Return EXACTLY {count_needed} items in valid JSON array format.

    TITLE RULE:
    - Catchy, crisp Gurmukhi headline (MAX 8-10 words, MAX 60 chars).

    POINTS STRUCTURE - 8 DEEP & CONNECTED POINTS (Write 3-4 detailed lines per point):
    Point 1 - ਕਿਉਂ ਟਰੈਂਡ ਕਰ ਰਿਹਾ ਹੈ (Why It's Trending Now): ਕਹਾਣੀ ਵਾਂਗ ਸ਼ੁਰੂਆਤ ਕਰੋ। ਅੱਜ ਦੀ ਤਰੀਕ ਵਿੱਚ ਅਜਿਹਾ ਕੀ ਵਾਪਰਿਆ ਕਿ ਲੋਕ ਇੰਟਰਨੈੱਟ 'ਤੇ ਇਸ ਨੂੰ ਧੜਾਧੜ ਸਰਚ ਕਰ ਰਹੇ ਹਨ?
    Point 2 - ਅਸਲ ਕਹਾਣੀ ਤੇ ਪਿਛੋਕੜ (Full Story & Origin): ਇਸ ਮਾਮਲੇ, ਵਿਅਕਤੀ ਜਾਂ ਘਟਨਾ ਦੀ ਸ਼ੁਰੂਆਤ ਕਿੱਥੋਂ ਹੋਈ? ਪੂਰਾ ਪਿਛੋਕੜ ਸਮਝਾਓ।
    Point 3 - ਪੰਜਾਬ, ਭਾਰਤ ਅਤੇ ਦੁਨੀਆਂ ਪੱਧਰ 'ਤੇ ਅਸਰ (Punjab, India & World Impact): ਇਸ ਟਰੈਂਡ ਦਾ ਪੰਜਾਬ ਵਿੱਚ ਕੀ ਅਸਰ ਹੈ, ਪੂਰੇ ਭਾਰਤ ਵਿੱਚ ਕੀ ਸਥਿਤੀ ਹੈ, ਅਤੇ ਵਿਦੇਸ਼ਾਂ (ਕੈਨੇਡਾ/ਅਮਰੀਕਾ/ਯੂ.ਕੇ.) ਵਿੱਚ ਇਸ ਬਾਰੇ ਕੀ ਚਰਚਾ ਹੈ?
    Point 4 - ਅੰਕੜੇ ਅਤੇ ਤੱਥ (Data & Numbers): ਅਸਲੀ ਅੰਕੜੇ ਦਿਓ—ਜਿਵੇਂ Google ਸਰਚ ਦੀ ਗਿਣਤੀ, ਬਜਟ, ਵੋਟਾਂ, ਵਿਊਜ਼, ਜਾਂ ਨੁਕਸਾਨ/ਮੁਨਾਫ਼ੇ ਦੇ ਅੰਕੜੇ।
    Point 5 - ਫਾਇਦੇ / ਸਕਾਰਾਤਮਕ ਪੱਖ (Benefits): ਇਸ ਨਾਲ ਆਮ ਲੋਕਾਂ, ਨੌਜਵਾਨਾਂ ਜਾਂ ਸਮਾਜ ਨੂੰ ਕੀ ਫਾਇਦਾ ਹੋ ਰਿਹਾ ਹੈ?
    Point 6 - ਨੁਕਸਾਨ / ਖਤਰੇ (Drawbacks & Risks): ਇਸ ਦਾ ਨਕਾਰਾਤਮਕ ਪੱਖ ਜਾਂ ਆਮ ਲੋਕਾਂ ਲਈ ਕੀ ਨੁਕਸਾਨ ਹੈ?
    Point 7 - ਵਿਵਾਦ / ਕੰਟ੍ਰੋਵਰਸੀ (Controversies): ਇਸ ਵਿਸ਼ੇ ਨਾਲ ਜੁੜੇ ਛੋਟੇ ਪੱਧਰ ਤੋਂ ਲੈ ਕੇ ਵੱਡੇ ਪੱਧਰ ਤੱਕ ਦੇ ਵਿਵਾਦ ਦੱਸੋ। ਕੌਣ ਵਿਰੋਧ ਕਰ ਰਿਹਾ ਹੈ ਤੇ ਦੂਜੀ ਧਿਰ ਦਾ ਕੀ ਕਹਿਣਾ ਹੈ?
    Point 8 - ਅੱਗੇ ਕੀ ਹੋਵੇਗਾ (What Next): ਆਉਣ ਵਾਲੇ ਦਿਨਾਂ ਵਿੱਚ ਇਸ ਦਾ ਕੀ ਨਤੀਜਾ ਨਿਕਲ ਸਕਦਾ ਹੈ? ਅੰਤ ਵਿੱਚ ਪਾਠਕਾਂ ਦੀ ਰਾਏ ਲੈਣ ਲਈ ਇੱਕ ਸਵਾਲ ਪੁੱਛੋ।

    OUTPUT ONLY VALID JSON (No extra text before or after JSON):
    [
      {{
        "category": "{category}",
        "title": "ਛੋਟਾ ਤੇ ਦਿਲਚਸਪ ਸਿਰਲੇਖ ਗੁਰਮੁਖੀ ਵਿੱਚ",
        "trend_tag": "🔥 ਟੌਪ ਟਰੈਂਡਿੰਗ",
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
        "source": "Google Trends / News",
        "trending_score": 9
      }}
    ]

    LIVE TRENDING DATA:
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
            print(f"SUCCESS with {model} for {category} - Got {len(result)} trending items")
            return result
        except Exception as e:
            print(f"FAILED {model} for {category}: {e}")
            if i < len(MODELS) - 1:
                safe_wait(12)
            continue
    print(f"All models failed for {category}")
    return []

def build_section(category, rss_list, output_file):
    print(f"\n--- Building Trending {category} -> {output_file} ---")
    topics = get_trending_topics(rss_list)
    
    news = call_ai(category, topics[:12], count_needed=5)
    
    if len(news) < 10:
        print(f"Fetching remaining trending items for {category}...")
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
        print(f"Saved {len(news)} trending items to {output_file}")
    else:
        print(f"Failed {category}, old {output_file} will remain")
    return news

def main():
    build_section("punjab", RSS_PUNJAB, "today_punjab.json")
    safe_wait(12)
    build_section("india", RSS_INDIA, "today_india.json")
    safe_wait(12)
    build_section("world", RSS_WORLD, "today_world.json")
    print("\nSab ho gaya! Live Trending files updated:")
    print("- today_punjab.json")
    print("- today_india.json")
    print("- today_world.json")

if __name__ == "__main__":
    main()
