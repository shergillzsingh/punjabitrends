import os
import feedparser
import json
import time
import random
import re
from google import genai
from google.genai import types

# --- 1. API KEY ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY not found!")
    exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)

# --- 2. MODELS ---
MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-2.5-flash-lite",
    "gemini-3-flash",
    "gemini-2.5-flash",
    "gemini-3.8-flash",
]

# --- 3. RSS LINKS (Same as yours) ---
RSS_PUNJAB = [
    "https://www.ptcnews.tv/rssfeed/trending-in-punjabi",
    "https://punjab.news18.com/commonfeeds/v1/pan/rss/punjab.xml",
    "https://www.ptcnews.tv/rssfeed/punjab",
    "https://www.bhaskar.com/rss-v1--category-1743.xml",
    "https://publish.tribuneindia.com/state/punjab/feed/",
    "https://feeds.bbci.co.uk/punjabi/rss.xml",
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

# --- 4. CATEGORY RULES (Same as yours) ---
CATEGORY_RULES = {
    "punjab": {
        "allowed": "ONLY news that happened IN Punjab, or is directly about Punjab people, Punjab government, Punjab cities.",
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

# --- 5. NEW: SYSTEM PROMPT - Yeh sabse bada fix hai ---
SYSTEM_PROMPT = """
You are a 35-year-old Punjabi journalist from Ludhiana. You are sitting in a village chaupal, telling news to your friend. You are NOT an anchor, NOT a government officer.

LANGUAGE: Only simple spoken Punjabi in Gurmukhi script. Words like people use in Muktsar / Ludhiana. No Roman Punjabi. No Hindi words.

TONE: 70% Story, 30% light roast. If news is sad like death / attack, then 100% serious, no roast.

STORY RULE - VERY IMPORTANT:
Write 8 points, but they must read like ONE continuous story, not 8 separate news. End of Point 1 must connect to start of Point 2. Use connecting words like "ਉਸ ਤੋਂ ਬਾਅਦ...", "ਇਹ ਸੁਣ ਕੇ...", "ਪਰ ਅਸਲ ਕਹਾਣੀ ਤਾਂ..."

Each point = 2-3 lines, with feeling. Add quotes in every point: "Family says...", "People are saying...", "Police says..."

WRONG - DO NOT WRITE LIKE THIS:
"Point 1: Punjab vich ik naujawan di maut ho gayi. Police jaanch kar rahi hai."

CORRECT - WRITE LIKE THIS IN GURMUKHI:
"ਸੋਮਵਾਰ ਸਵੇਰੇ ਪਿੰਡ ਵਿੱਚ ਅਜੇ ਲੋਕ ਚਾਹ ਪੀ ਹੀ ਰਹੇ ਸਨ ਕਿ ਇੱਕ ਫੋਨ ਆਇਆ। ਦੂਜੇ ਪਾਸੇ ਤੋਂ ਆਵਾਜ਼ ਆਈ - 'ਤੁਹਾਡਾ ਮੁੰਡਾ...' ਤੇ ਉਸ ਤੋਂ ਬਾਅਦ ਪੂਰੇ ਘਰ ਵਿੱਚ ਰੌਲਾ ਪੈ ਗਿਆ। ਮਾਂ ਕਹਿੰਦੀ ਹੈ - 'ਮੇਰਾ ਪੁੱਤ ਤਾਂ ਸਵੇਰੇ ਹੱਸਦਾ ਹੋਇਆ ਗਿਆ ਸੀ।'"
"""

def get_trending_topics(rss_list):
    all_titles = []
    for url in rss_list:
        try:
            feed = feedparser.parse(url)
            print(f"RSS OK: {url} - Found {len(feed.entries)} entries")
            for entry in feed.entries[:25]:
                if entry.title.strip():
                    all_titles.append(entry.title.strip())
        except Exception as e:
            print(f"RSS Failed: {url} - {e}")
            continue
    print(f"Total headlines: {len(all_titles)}")
    topics = []
    seen = set()
    for title in all_titles:
        low = title.lower().strip()
        if low in seen:
            continue
        seen.add(low)
        count = 0
        for t2 in all_titles:
            w1 = set(re.findall(r'\w+', title.lower()))
            w2 = set(re.findall(r'\w+', t2.lower()))
            if w1 and w2 and len(w1 & w2) / max(len(w1), 1) > 0.5:
                count += 1
        topics.append({"count": count, "titles": [title]})
    topics = sorted(topics, key=lambda x: x["count"], reverse=True)
    return topics[:25]

def safe_wait(seconds=30):
    print(f"Waiting {seconds} sec...")
    time.sleep(seconds)

# --- 6. AI CALL - FIXED ---
def call_ai(category, topics):
    titles_text = ""
    for t in topics:
        titles_text += f"\n- Topic (Appeared in {t['count']} feeds): " + " | ".join(t['titles'][:2])

    rules = CATEGORY_RULES[category]

    prompt = f"""
    INPUT Headlines for category: {category}.
    CATEGORY FILTER:
    ALLOWED: {rules['allowed']}
    BLOCKED: {rules['blocked']}

    TASK:
    1. Return EXACTLY 10 news items.
    2. Rank by RSS count. Higher count = Higher trending.
    3. If after filtering you have less, split one big topic into 2-3 separate news.

    TITLE RULE:
    - Title SHORT, CRISP, newspaper headline.
    - MAX 8-10 words, MAX 60 characters.
    - WRONG: "2027 elections Punjab government big claim for youth quiz competition and tubewell load regularization relief"
    - CORRECT: "ਪੰਜਾਬ ਸਰਕਾਰ ਦਾ ਵੱਡਾ ਦਾਅਵਾ"

    POINTS STRUCTURE - 8 POINTS, BUT ONE STORY:
    Point 1 - Story Opening: Start like a film. 2-3 lines scene. Do NOT start with date.
    Point 2 - What Happened? Full story step-by-step, with quotes. Who said what?
    Point 3 - Origin: Where did this issue start? First time when? Background in story style.
    Point 4 - Controversy: One side says what? Other side says what? Court / Govt / Opposition saying what?
    Point 5 - Related Developments: SAME category only. If topic is Punjab, tell only other Punjab places. If topic is Canada attack, tell only other attacks on Sikhs. Do NOT jump to America politics or Metro example.
    Point 6 - Impact On People: Benefit / Harm with one small story of a common person - farmer, youth, mother. Not dry list.
    Point 7 - Data: 2-3 real numbers only. If you do not know, write in Punjabi "ਹਾਲੇ ਸਰਕਾਰੀ ਅੰਕੜਾ ਨਹੀਂ ਆਇਆ" - do NOT invent.
    Point 8 - What Will Happen Next? Next hearing / decision / date? End with one question for reader.

    OUTPUT: ONLY valid JSON. No markdown. All text in Gurmukhi only.

    OUTPUT JSON FORMAT:
    [
      {{
        "category": "{category}",
        "title": "MAX 8-10 words, MAX 60 chars, short headline in Gurmukhi",
        "points": [
          "Point 1 story in Gurmukhi, 2-3 lines",
          "Point 2 story in Gurmukhi, 2-3 lines, with quotes",
          "Point 3 origin story in Gurmukhi",
          "Point 4 controversy in Gurmukhi",
          "Point 5 related in SAME category in Gurmukhi",
          "Point 6 impact with small story in Gurmukhi",
          "Point 7 data in Gurmukhi",
          "Point 8 what next + question in Gurmukhi"
        ],
        "source": "Source name",
        "trending_score": 5
      }}
    ]

    HEADLINES:
    {titles_text}
    """

    for i, model in enumerate(MODELS):
        try:
            print(f"Trying {model} for {category}... (Attempt {i+1}/{len(MODELS)})")
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=0.8,
                    top_p=0.95,
                    max_output_tokens=4000,
                )
            )
            text = resp.text.strip().replace("```json", "").replace("```", "").strip()
            result = json.loads(text)
            print(f"SUCCESS with {model} for {category} - Got {len(result)} news")
            return result
        except Exception as e:
            print(f"FAILED {model} for {category}: {e}")
            if i < len(MODELS) - 1:
                safe_wait(30 + random.randint(0, 10))
            continue
    print(f"All models failed for {category}")
    return []

def build_section(category, rss_list, output_file):
    print(f"\n--- Building {category} -> {output_file} ---")
    topics = get_trending_topics(rss_list)
    news = call_ai(category, topics)
    if len(news) < 10:
        print(f"Only {len(news)} news for {category}, trying again to fill to 10...")
        safe_wait(10)
        news2 = call_ai(category, topics)
        seen_titles = set(n.get('title', '') for n in news)
        for n in news2:
            if n.get('title', '') not in seen_titles:
                news.append(n)
                seen_titles.add(n.get('title', ''))
            if len(news) >= 10:
                break
        print(f"After 2nd try, total: {len(news)}")
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
    safe_wait(30)
    build_section("india", RSS_INDIA, "today_india.json")
    safe_wait(30)
    build_section("world", RSS_WORLD, "today_world.json")
    print("\nSab ho gaya! 3 files:")
    print("- today_punjab.json (10 news)")
    print("- today_india.json (10 news)")
    print("- today_world.json (10 news)")

if __name__ == "__main__":
    main()
