import feedparser
from google import genai
import json
import time
import os
from datetime import date

# --- GitHub ਲਈ Key - Secret ਤੋਂ ਆਵੇਗੀ, File ਵਿੱਚ ਨਹੀਂ ਲਿਖੀ ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    print("ERROR: GEMINI_API_KEY nahi mili. 【entity-GitHub Secrets¦canonical_name=GitHub】 vich pao.")
    raise SystemExit(1)

client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-3.5-flash-lite"

RSS_FEEDS = [
    "https://www.ptcnews.tv/rssfeed/trending-in-punjabi",
    "https://punjab.news18.com/commonfeeds/v1/pan/rss/punjab.xml",
    "https://punjabilinkmediagroup.com/rss/latest-posts",
]

print("Step 1: 【entity-RSS¦canonical_name=RSS】 padh reha haan...")
all_headlines = []
for feed_url in RSS_FEEDS:
    try:
        feed = feedparser.parse(feed_url)
        print(f"【entity-RSS¦canonical_name=RSS】 toh {len(feed.entries)} mileya - {feed_url}")
        for entry in feed.entries[:10]:
            my_date = entry.get("published", "aaj")
            my_desc = entry.get("summary", "")[:200]
            my_line = f"{entry.title} | Date: {my_date} | Detail: {my_desc}"
            all_headlines.append(my_line)
    except Exception as e:
        print(f"Error 【entity-RSS¦canonical_name=RSS】: {feed_url} - {e}")

print(f"Kul Headlines: {len(all_headlines)}")

if len(all_headlines) == 0:
    print("【entity-RSS¦canonical_name=RSS】 khali hai, backup vishe vart rahe haan...")
    all_headlines = [
        "Bathinda pradhushan AQI 816",
        "LPU vivad High Court faisla",
        "Punjab vich meenh di sambhavna"
    ]

headlines_text = "\n".join(all_headlines)
today_str = date.today().strftime("%d %B %Y")

print("Step 2: AI vishe bana reha hai...")
prompt_topics = f"""
Aaj di tareekh hai: {today_str}
Headlines:
{headlines_text}
Kaam:
1. Ikko jihiya khabran nu ik Group vich pa de
2. Sirf Punjab naal sambandh wale Top 10 vishe de
3. Jawab SIRF JSON vich de - jive ["Bathinda Pradhushan", "LPU Vivad"]
"""
response = client.models.generate_content(model=MODEL_NAME, contents=prompt_topics)
topics_text = response.text.replace("```json", "").replace("```", "").strip()
topics = json.loads(topics_text)
print(f"Top Vishe: {topics}")

print("Step 3: AI lekh likh reha hai...")
final_articles = []
for topic in topics:
    prompt_article = f"""
Aaj di tareekh hai: {today_str}
Visha: {topic}

Tussi ek Punjabi samajhdaar dost ho, jive Meta AI chat vich samjhaunda hai. Khabar nahi, samjhauna hai.

ZARURI NIYAM:
1. Sirf GURMUKHI PUNJABI vich likh - jive "ਪੰਜਾਬ, ਚੰਡੀਗੜ੍ਹ, ਖ਼ਬਰ"
2. English akharan vich Punjabi BILKUL na likh - jive "Punjab, Chandigarh" NA likh
3. Sokhi, saaf Punjabi vich likh, jive pind vich kise nu samjha rahe ho
4. Kise da lekh Copy na kari, apne shabdan vich likh

LEKH DA STYLE - Bilkul is tarah likh:

**ਕੀ ਹੋਇਆ?**
2-3 line vich sidha dasso - aaj ki hoya hai.

**ਕਿਉਂ Trend ਕਰ ਰਿਹਾ ਹੈ?**
Lokan ne is nu kyon chukkeya? Social media te kyon gall ho rahi hai?

**ਪਹਿਲਾਂ ਕੀ ਹੋਇਆ ਸੀ?**
Eh mudda aaj da nahi hai. Is da pichokad dasso. Pehlan kadon, kithon shuru hoya si? Pehlan ki faisla hoya si, ki gall hoyi si? Pura background dasso taan ki padhan wale nu samajh aave ki eh gall ithe tak kiven pahunchi.

**ਹੁਣ ਕੀ ਹੋਇਆ ਹੈ?**
Hun taaza ki hoya hai? Aaj ki nava hoya hai jo pehlan nahi si hoya? Pehlan wali gall te hun wali gall vich ki fark hai?

**ਹੋਰ ਪਾਸੇ ਕੀ ਕਹਿ ਰਹੇ ਨੇ?**
Ikko gall te sab ikko jeha nahi sochde.
- Ek passe wale ki keh rahe ne?
- Duje passe wale ki keh rahe ne?
- Sarkar / Court / Police ki keh rahi hai?
- Aam lok / Virodhi / Samarthak ki keh rahe ne?
Dovan paksan di gall dasso, sirf ik passe di gall na dasso.

**ਹੋਰ ਰਾਜਾਂ / ਹੋਰ ਥਾਵਾਂ ਤੇ ਕੀ ਹੋਇਆ? - EH SAB TOH ZARURI HAI**
Is vishay da sirf Punjab naal sambandh nahi hai. Hor thawan te is da ki haal hai, oh vi dasso.

Jive:
- Je visha Metro Train hai, taan dasso - Delhi vich Metro kinni kamyab rahi? Mumbai, Kolkata, Chennai vich ki hoya? Kithe kamyab rahi, kithe fail hoyi, te kyon?
- Je visha Pradhushan hai, taan dasso - Delhi da AQI ki hai? Haryana, UP vich ki haal hai?
- Je visha Chunaav hai, taan dasso - Hor rajan vich chunaav vich ki hoya si?
- Je visha Kisan hai, taan dasso - Hor rajan de kisan ki kar rahe ne?

Har vishay nu duje rajan / duje deshan naal TULNA karke dasso - kithe kamyab hoya, kithe nahi hoya, te kyon nahi hoya. Punjab layi us toh ki sikhna chahida hai?

**ਪੰਜਾਬ ਤੇ ਕੀ ਅਸਰ ਪਵੇਗਾ?**
Aam Punjabi nu is nal ki fark pavenga? Kisan, student, ya shehar de lokan te ki asar hovega?

**ਅੱਗੇ ਕੀ ਹੋਵੇਗਾ?**
Hun agge ki hon di umeed hai? Agli tareekh, agli meeting, ya agla faisla ki ho sakda hai?

Lekh 600-700 shabdan da hove. Vadda-vadda paragraph na likh, chhote-chhote paragraph vich likh.
"""
    art = client.models.generate_content(model=MODEL_NAME, contents=prompt_article)
    final_articles.append({"topic": topic, "article": art.text})
    print(f"Lekh ban gaya: {topic}")
    time.sleep(5)

with open("today_trends.json", "w", encoding="utf-8") as f:
    json.dump(final_articles, f, ensure_ascii=False, indent=2)

print("Ho gaya! today_trends.json vich Save ho gaya.")
