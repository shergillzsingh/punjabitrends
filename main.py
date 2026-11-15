import os
import feedparser
import json
import time
import random
import re
from google import genai

# --- 1. API KEY FROM 【entity-GITHUB¦canonical_name=GitHub】 SECRETS ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY not found!")
    exit(1)

client = genai.Client(api_key=GEMINI_API_KEY)

# --- 2. MODELS - LITE FIRST, 3.8 LAST ---
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
        "allowed": "ONLY news that happened IN Punjab, or is directly about Punjab people, Punjab government, Punjab cities. If news mentions Punjab even a little, INCLUDE it.",
        "blocked": "DO NOT include pure Delhi / Mumbai / World news where Punjab is not mentioned at all.",
    },
    "india": {
        "allowed": "ONLY news that happened IN India (outside Punjab), or is about India national government. Delhi, Mumbai, UP, Bihar etc are allowed.",
        "blocked": "DO NOT include Punjab-only local news and DO NOT include pure World news.",
    },
    "world": {
        "allowed": "ONLY news that happened OUTSIDE India. USA, UK, China, Pakistan, Russia, Ukraine, etc.",
        "blocked": "DO NOT include Punjab news. DO NOT include India news.",
    }
}

# --- 5. TRENDING TOPICS ---
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

# --- 6. AI CALL - PROMPT FULL ENGLISH ---
def call_ai(category, topics):
    titles_text = ""
    for t in topics:
        titles_text += f"\n- Topic (Appeared in {t['count']} feeds): " + " | ".join(t['titles'][:2])

    rules = CATEGORY_RULES[category]

    prompt = f"""
    You are a senior Punjabi journalist, not a robot. You tell news like a story.

    INPUT:
    Headlines from Hindi and English RSS feeds for category: {category}.

    CATEGORY FILTER:
    ALLOWED: {rules['allowed']}
    BLOCKED: {rules['blocked']}

    TASK:
    1. You MUST return EXACTLY 10 news items. Not 1, Not 2. EXACTLY 10.
    2. If after filtering you have less, take remaining from headlines even if less trending.
    3. DO NOT reject news just because it is slightly related to another category.
    4. If still less than 10, split one big topic into 2-3 separate news.
    5. Rank by RSS count. Higher count = Higher trending.

    TITLE RULE:
    - Title must be SHORT, CRISP, newspaper headline.
    - MAX 8-10 words, MAX 60 characters.
    - WRONG: "2027 elections Punjab government big claim for youth quiz competition and tubewell load regularization relief"
    - CORRECT: Short headline like "Big Claim of Punjab Government"
    - Pick ONLY main part for title. Details go in points.

    WRITING STYLE - VERY IMPORTANT, THIS IS THE MAIN RULE:
    - Do NOT write like a robot, exam notes, government report, or dry list.
    - Write like a Punjabi journalist telling a story to a friend in a village chaupal.
    - Each point must be 2-3 lines, connected, with feeling, NOT 1 dry line.
    - Use simple, spoken Punjabi words that people use in daily life.
    - Add human touch: What did people say? What did family say? What did police / government say? Use quotes like "People are saying...", "Family says..."
    - Start with a story hook, like a film start. Reader should want to read next point.
    - Points should flow like a story, not like separate disconnected bullets.
    - First point = Story start. Last point = What will happen next? Leave reader thinking.
    - Do NOT repeat dry labels like "Main News:", "Current Status:" again and again.
    - Use natural headings: "What happened?", "What are people saying?", "Where did this issue start?"

    EXAMPLE - WRONG (Dry, No Taste):
    "Point 1: A youth died in Punjab."

    EXAMPLE - CORRECT (Story Style, Tasty to Read):
    "A heart-shaking incident has come to light in Punjab. A smiling youth suddenly... The whole village is in shock, family is crying badly, and people are asking - are food items not safe anymore?"

    POINTS STRUCTURE - 8 POINTS, STORY STYLE:
    Point 1 - Story Opening: Start with a story hook, 2-3 lines, emotionally engaging. What happened? Set the scene like a film opening.
    Point 2 - What Happened? How Did It Happen?: Full story, step by step, with quotes from people. Who is involved? Who said what? Victim, accused, government, opposition.
    Point 3 - Origin: Where Did This Issue Start? When did it start for the first time? Who started it? Where was it first raised? What is the background history?
    Point 4 - Controversy: What is the controversy linked to this topic? What does one side say, what does the other side say? Who is supporting, who is opposing? What is the court / government / opposition saying? Where is the fight?
    Point 5 - Related Developments Elsewhere: What is happening on the same topic in other places? Example: If Modi inaugurated Metro, tell Metro status in other cities. Is it successful there or not? NOTE: Related must stay inside SAME category only.
    Point 6 - Impact On People: What will be the benefit? What will be the harm / loss? What impact on common people, farmers, youth, businessmen? Explain with story, not with dry list.
    Point 7 - Data And Statistics: Real numbers - how many people, how much money, how many percent? If you do not know exact data, do NOT invent fake numbers. Write "official figures not yet available".
    Point 8 - What Will Happen Next? Future: What can happen next? What will government do next? When is next hearing / decision? What should people do now?

    LANGUAGE RULES:
    - Output MUST be in ONLY Gurmukhi script. NEVER use Roman Punjabi.
    - Translate names: Narendra Modi -> Narendra Modi in Gurmukhi, Donald Trump -> Donald Trump in Gurmukhi.
    - Use Punjabi words, not Hindi words.
    - Return ONLY valid JSON. No markdown.

    OUTPUT JSON FORMAT:
    [
      {{
        "category": "{category}",
        "title": "MAX 8-10 words, MAX 60 chars, short headline in Gurmukhi",
        "points": [
          "Point 1 - Story Opening, 2-3 lines story in Gurmukhi",
          "Point 2 - What happened, full story with quotes in Gurmukhi",
          "Point 3 - Origin, where did issue start in Gurmukhi",
          "Point 4 - Controversy, who is saying what in Gurmukhi",
          "Point 5 - Related developments elsewhere in Gurmukhi",
          "Point 6 - Impact on people, benefit / harm in Gurmukhi",
          "Point 7 - Data and statistics in Gurmukhi",
          "Point 8 - What will happen next in Gurmukhi"
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
                safe_wait(30 + random.randint(0, 10))
            continue
    print(f"All models failed for {category}")
    return []

# --- 7. BUILD SECTION - 10 PAKKI ---
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
