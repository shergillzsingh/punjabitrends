import os
import feedparser
import json
import time
import random
import re
from google import genai

# --- 1. API KEY FROM GITHUB SECRETS ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY not found!")
    exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)

# --- 2. MODELS - LITE PEHLA, 3.8 AKHAR TE ---
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

# --- 4. CATEGORY RULES ---
CATEGORY_RULES = {
    "punjab": {
        "allowed": "ONLY news that happened IN Punjab, or is directly about Punjab people, Punjab government, Punjab cities (Amritsar, Ludhiana, Jalandhar, Patiala, Bathinda, etc). If news mentions Punjab even a little, INCLUDE it.",
        "blocked": "DO NOT include pure Delhi / Mumbai / World news where Punjab is not mentioned at all. But DO NOT reject Punjab news just because it also mentions India.",
    },
    "india": {
        "allowed": "ONLY news that happened IN India (outside Punjab), or is about India national government. Delhi, Mumbai, UP, Bihar etc are allowed. If news mentions India, INCLUDE it.",
        "blocked": "DO NOT include Punjab-only local news (Punjab village, Punjab local crime) and DO NOT include pure World news.",
    },
    "world": {
        "allowed": "ONLY news that happened OUTSIDE India. USA, UK, China, Pakistan, Russia, Ukraine, etc.",
        "blocked": "DO NOT include Punjab news. DO NOT include India news. Even if India news mentions USA, if main event is in India, REJECT it.",
    }
}

# --- 5. TRENDING TOPICS - FIXED GROUPING ---
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

    print(f"Total headlines collected: {len(all_titles)}")

    # Grouping FIX: Pehle wali galti - 4 shabda naal group karna band
    # Hun har title nu alag rakho, duplicate hi hatao
    topics = []
    seen = set()
    for title in all_titles:
        low = title.lower().strip()
        if low in seen:
            continue
        seen.add(low)
        # Count karo - eh topic kinniya feeds vich aaya?
        count = 0
        for t2 in all_titles:
            # Je 60% shabad milde ne ta same topic
            w1 = set(re.findall(r'\w+', title.lower()))
            w2 = set(re.findall(r'\w+', t2.lower()))
            if w1 and w2 and len(w1 & w2) / max(len(w1), 1) > 0.5:
                count += 1
        topics.append({"count": count, "titles": [title]})
    
    # Trending wale pehla
    topics = sorted(topics, key=lambda x: x["count"], reverse=True)
    return topics[:25]

# --- 6. SAFE WAIT ---
def safe_wait(seconds=30):
    print(f"Waiting {seconds} sec to avoid RPM limit...")
    time.sleep(seconds)

# --- 7. AI CALL WITH FALLBACK + GAP ---
def call_ai(category, topics):
    titles_text = ""
    for t in topics:
        titles_text += f"\n- Topic (Appeared in {t['count']} feeds): " + " | ".join(t['titles'][:2])

    rules = CATEGORY_RULES[category]

    prompt = f"""
    You are a professional Punjabi news editor and analyst.

    INPUT:
    Below are news headlines from Hindi and English RSS feeds for category: {category}.

    STRICT CATEGORY FILTER:
    ALLOWED: {rules['allowed']}
    BLOCKED: {rules['blocked']}

    TASK - READ CAREFULLY:
    1. You MUST return EXACTLY 10 news items. Not 1, Not 2, Not 5. EXACTLY 10.
    2. If after filtering you have only 2-3 news, then take remaining from headlines list even if less trending.
    3. DO NOT reject a news just because it is slightly related to another category. If it mentions {category} even a little, INCLUDE it.
    4. If still less than 10, split one big topic into 2-3 separate news. Example: Punjab Government news -> 1. Government announcement, 2. Opposition reaction, 3. Public reaction.
    5. NEVER return less than 10. Empty list is NOT allowed.
    6. Rank by RSS count. Higher count = Higher trending = Top rank.

    TITLE RULE - VERY IMPORTANT:
    - Title must be SHORT, CRISP, like a newspaper headline.
    - MAX 8-10 words only. MAX 60 characters.
    - NEVER write a long sentence as title.
    - WRONG: "2027 diyan chona to pehla Punjab sarkar da vadda daa: naujawan layi quiz mukable te tubewell load regularization vich rahat" (Too long)
    - CORRECT: "ਪੰਜਾਬ ਸਰਕਾਰ ਦਾ ਵੱਡਾ ਦਾਅ" (Short)
    - CORRECT: "ਟਿਊਬਵੈੱਲ ਲੋਡ ਵਿੱਚ ਰਾਹਤ" (Short)
    - If topic has 2 parts, pick ONLY main one for title. Details will go in points.

    OUTPUT STYLE - POINTS, NOT ESSAY:
    - Do NOT write a long paragraph essay.
    - Write each news as 5-6 SHORT BULLET POINTS.
    - Each point max 1-2 lines.
    - Total for one news = around 300-400 words, but divided into points.
    - Points must cover:
      Point 1: Main News - Ki hoya?
      Point 2: CURRENT STATUS TODAY - Ajj ki chal reha hai? Latest update?
      Point 3: RELATED DEVELOPMENTS - Same topic te hor thawan te ki chal reha hai? Example: If Modi inaugurated Metro, tell Metro status in other cities. Successful or not? NOTE: Related must stay inside SAME category only.
      Point 4: IMPACT - BENEFIT - Fayda ki hai? Kaun nu fayda?
      Point 5: IMPACT - HARM / LOSS - Nuksan ki hai? Kaun nu nuksan?
      Point 6: DATA & STATISTICS - If you know real numbers, include them. If you do not know, do NOT invent fake numbers. Write "official figures not yet available".

    LANGUAGE RULES:
    - Use ONLY Gurmukhi script. NEVER use Roman Punjabi.
    - Translate names: Narendra Modi -> ਨਰਿੰਦਰ ਮੋਦੀ, Donald Trump -> ਡੋਨਲਡ ਟਰੰਪ
    - Use Punjabi words, not Hindi words.
    - Return ONLY valid JSON. No markdown, no explanation.

    OUTPUT JSON FORMAT:
    [
      {{
        "category": "{category}",
        "title": "MAX 8-10 words, MAX 60 chars, short headline in Gurmukhi",
        "points": [
          "Point 1 - Main News in Gurmukhi",
          "Point 2 - Current Status Today in Gurmukhi",
          "Point 3 - Related Developments in Gurmukhi",
          "Point 4 - Benefit in Gurmukhi",
          "Point 5 - Harm / Loss in Gurmukhi",
          "Point 6 - Statistics in Gurmukhi"
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
            resp = client.models.generate_content(model=model, contents=prompt)
            text = resp.text.strip().replace("```json", "").replace("```", "").strip()
            result = json.loads(text)
            print(f"SUCCESS with {model} for {category} - Got {len(result)} news")
            return result
        except Exception as e:
            print(f"FAILED {model} for {category}: {e}")
            if i < len(MODELS) - 1:
                wait_time = 30 + random.randint(0, 10)
                safe_wait(wait_time)
            continue

    print(f"All models failed for {category}")
    return []

# --- 8. BUILD ONE SECTION -> ONE FILE - 10 PAKKI ---
def build_section(category, rss_list, output_file):
    print(f"\n--- Building {category} -> {output_file} ---")
    topics = get_trending_topics(rss_list)
    print(f"Found {len(topics)} topics for {category}")

    news = call_ai(category, topics)

    # FIX: Je 10 to ghat aaiya, ta fer try karo bharne lai
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

    # Category filter + Sirf 10
    news = [n for n in news if n.get("category", "").lower() == category.lower()]
    news = news[:10]

    if news:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(news, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(news)} news to {output_file}")
    else:
        print(f"Failed {category}, old {output_file} will remain")
    return news

# --- 9. MAIN ---
def main():
    build_section("punjab", RSS_PUNJAB, "today_punjab.json")
    safe_wait(30)

    build_section("india", RSS_INDIA, "today_india.json")
    safe_wait(30)

    build_section("world", RSS_WORLD, "today_world.json")

    print("\nSab ho gaya! 3 files ban gayian:")
    print("- today_punjab.json (10 news)")
    print("- today_india.json (10 news)")
    print("- today_world.json (10 news)")

if __name__ == "__main__":
    main()
