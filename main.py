import os
import feedparser
import json
import time
import random
from google import genai

# --- 1. API KEY FROM GITHUB SECRETS ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY not found in environment!")
    exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)

# --- 2. MODELS - SCREENSHOT DE HISAB NAAL SET KITE ---
# Pehla Lite wale, kyunki ohna di RPM zyada hai (15)
# 3.8 Flash akhar te, kyunki ohdi RPM sirf 5 hai te oh ajj full ho gaya si
MODELS = [
    "gemini-3.5-flash-lite",  # RPM 15 - Pehla try
    "gemini-3.1-flash-lite",  # RPM 15 - Dusra
    "gemini-2.5-flash-lite",  # RPM 10
    "gemini-3-flash",         # RPM 5
    "gemini-2.5-flash",       # RPM 5
    "gemini-3.8-flash",       # RPM 5 - Akhar te
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

# --- 4. STRICT CATEGORY RULES ---
CATEGORY_RULES = {
    "punjab": {
        "allowed": "ONLY news that happened IN Punjab, or is directly about Punjab people, Punjab government, Punjab cities (Amritsar, Ludhiana, Jalandhar, Patiala, Bathinda, etc).",
        "blocked": "DO NOT include India national news, Delhi news, or World news. Even if Modi / India news appears in Punjab RSS, REJECT it unless the event happened IN Punjab.",
    },
    "india": {
        "allowed": "ONLY news that happened IN India (outside Punjab), or is about India national government, India national issues. Delhi, Mumbai, UP, Bihar etc are allowed.",
        "blocked": "DO NOT include Punjab-only news (Punjab local crime, Punjab local politics, Punjab village news). DO NOT include World news. If a news is only about Punjab, REJECT it.",
    },
    "world": {
        "allowed": "ONLY news that happened OUTSIDE India. USA, UK, China, Pakistan, Russia, Ukraine, etc.",
        "blocked": "DO NOT include Punjab news. DO NOT include India news. Even if an India news mentions USA, if the main event is in India, REJECT it.",
    }
}

# --- 5. TRENDING LOGIC ---
def get_trending_topics(rss_list):
    all_titles = []
    for url in rss_list:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:15]:
                all_titles.append(entry.title.strip())
        except Exception as e:
            print(f"RSS Failed: {url} - {e}")
            continue

    topics = {}
    for title in all_titles:
        words = __import__("re").findall(r'\w+', title.lower())
        if len(words) < 3:
            continue
        key = " ".join(words[:4])
        if key not in topics:
            topics[key] = {"count": 0, "titles": []}
        topics[key]["count"] += 1
        if title not in topics[key]["titles"]:
            topics[key]["titles"].append(title)

    sorted_topics = sorted(topics.values(), key=lambda x: x["count"], reverse=True)
    return sorted_topics[:12]

# --- 6. SAFE WAIT FUNCTION ---
# Har request to baad 30 sec rukega, taan jo RPM limit na tutte
def safe_wait(seconds=30):
    print(f"Waiting {seconds} sec to avoid RPM limit...")
    time.sleep(seconds)

# --- 7. AI CALL WITH FALLBACK + GAP ---
def call_ai(category, topics):
    titles_text = ""
    for t in topics:
        titles_text += f"\n- Topic (Appeared in {t['count']} RSS Feeds): " + " | ".join(t['titles'][:3])

    rules = CATEGORY_RULES[category]

    prompt = f"""
    You are a professional Punjabi news editor and analyst.

    INPUT:
    Below are news headlines from Hindi and English RSS feeds for category: {category}.
    Each topic shows in how many RSS feeds it appeared. Higher count = More Trending.

    STRICT CATEGORY FILTER - VERY IMPORTANT, DO NOT BREAK THIS RULE:
    ALLOWED FOR THIS CATEGORY: {rules['allowed']}
    BLOCKED FOR THIS CATEGORY: {rules['blocked']}

    If a headline belongs to another category, you MUST REJECT it and DO NOT include it in output.
    Example: If category is "punjab", do NOT include Delhi / Mumbai / World news even if it is trending.
    Example: If category is "india", do NOT include Punjab-local news or World news.
    Example: If category is "world", do NOT include any India or Punjab news.
    Only return news that 100% belongs to "{category}".

    TASK:
    1. First FILTER headlines by above rule, then select Top 10 Trending from the remaining.
    2. Rank them by RSS count. Topics that appeared in more RSS feeds must rank higher.
    3. For each topic, merge all its headlines into ONE combined news story.
    4. Write each story in 300-400 words in clean, natural GURMUKHI PUNJABI.
    5. Do NOT do literal translation. Rewrite it like a Punjabi newspaper article.

    6. IMPORTANT - ADD FULL CONTEXT, NOT JUST HEADLINE:
       For each topic, you must also explain in the SAME summary:
       a) CURRENT STATUS TODAY: As of today, what is the latest update on this topic? What is happening right now?
       b) RELATED DEVELOPMENTS: What is happening on this same topic in other places?
          Example: If Modi inaugurated a Metro, then tell what is the status of Metro in other cities / states / countries. Is it successful there or not?
          NOTE: Related developments must still stay inside the SAME category. For Punjab news, give related Punjab examples only. Do NOT bring India/World news into Punjab file.
       c) IMPACT ANALYSIS: Is this topic beneficial or harmful for people / country / world? Who will benefit and who will face loss?
       d) DATA & STATISTICS: If you know any real numbers, include them. Example: cost, length in km, number of passengers, percentage growth, deaths, profit/loss. If you do not know exact data, do NOT invent fake numbers. Write "official figures not yet available".

    7. LANGUAGE RULES:
       - Use ONLY Gurmukhi script. NEVER use Roman Punjabi.
       - Translate English/Hindi names to Punjabi: Narendra Modi -> ਨਰਿੰਦਰ ਮੋਦੀ, Donald Trump -> ਡੋਨਲਡ ਟਰੰਪ
       - Use Punjabi words, not Hindi words.
    8. Return ONLY valid JSON. No markdown, no explanation, no extra text.

    OUTPUT JSON FORMAT:
    [
      {{
        "category": "{category}",
        "title": "News title in Gurmukhi Punjabi",
        "summary": "300-400 words news in Gurmukhi Punjabi. Must include: Main News + Current Status Today + Related Developments (same category only) + Impact (Benefit / Harm) + Statistics if available.",
        "source": "Source name",
        "trending_score": 5
      }}
    ]

    HEADLINES:
    {titles_text}
    """

    # FALLBACK LOGIC: Ek fail hove ta duje to kamm lao
    for i, model in enumerate(MODELS):
        try:
            print(f"Trying {model} for {category}... (Attempt {i+1}/{len(MODELS)})")
            resp = client.models.generate_content(model=model, contents=prompt)
            text = resp.text.strip().replace("```json", "").replace("```", "").strip()
            result = json.loads(text)
            print(f"SUCCESS with {model} for {category}")
            return result
        except Exception as e:
            print(f"FAILED {model} for {category}: {e}")
            # Agar akhari model nahi hai, ta 30 sec ruk ke agle model te jao
            if i < len(MODELS) - 1:
                # 30 sec + thoda random gap, taan jo saare request ikathe na hon
                wait_time = 30 + random.randint(0, 10)
                safe_wait(wait_time)
            continue

    print(f"All models failed for {category}")
    return []

# --- 8. BUILD ONE SECTION -> ONE FILE ---
def build_section(category, rss_list, output_file):
    print(f"\n--- Building {category} -> {output_file} ---")
    topics = get_trending_topics(rss_list)
    print(f"Found {len(topics)} trending topics for {category}")

    news = call_ai(category, topics)

    if news:
        news = [n for n in news if n.get("category", "").lower() == category.lower()]
        news = news[:10]
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(news, f, ensure_ascii=False, indent=2)
        print(f"Saved {len(news)} news to {output_file}")
    else:
        print(f"Failed {category}, old {output_file} will remain")
    return news

# --- 9. MAIN ---
def main():
    # Punjab
    build_section("punjab", RSS_PUNJAB, "today_punjab.json")
    safe_wait(30)  # Punjab to India vich 30 sec gap

    # India
    build_section("india", RSS_INDIA, "today_india.json")
    safe_wait(30)  # India to World vich 30 sec gap

    # World
    build_section("world", RSS_WORLD, "today_world.json")

    print("\nSab ho gaya! 3 files ban gayian:")
    print("- today_punjab.json")
    print("- today_india.json")
    print("- today_world.json")

if __name__ == "__main__":
    main()
