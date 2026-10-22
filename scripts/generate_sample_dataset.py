"""
Generates the synthetic demo dataset used throughout this project.

IMPORTANT: This produces 100% SYNTHETIC DATA. No real user posts, messages,
or accounts are scraped, exported, or represented. The "WhatsApp Export"
platform value simulates the *shape* of an authorized chat export; it does
not contain, imply, or come from any real WhatsApp conversation.

Output: data/sample/social_media_sample.csv

Run:
    python scripts/generate_sample_dataset.py
"""

import csv
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42
NUM_ROWS = 5000
DUPLICATE_RATE = 0.03       # fraction of rows that are near-duplicates of an earlier row
MISSING_TEXT_RATE = 0.01    # rows with missing text (to test validation/dropping)
MISSING_TOPIC_RATE = 0.03   # rows with missing topic
MISSING_HASHTAG_RATE = 0.55 # most posts don't have hashtags, which is realistic
LABEL_NOISE_RATE = 0.08     # fraction of rows where the text's tone doesn't match its assigned
                             # label (simulates sarcasm/ambiguity/annotation error in real data)

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "sample" / "social_media_sample.csv"
LABELED_OUTPUT_PATH = Path(__file__).resolve().parent.parent / "data" / "sample" / "social_media_sample_labeled.csv"

random.seed(SEED)

PLATFORMS = {
    "Instagram": 0.22,
    "X/Twitter": 0.22,
    "Facebook": 0.18,
    "YouTube": 0.16,
    "Reddit": 0.14,
    "WhatsApp Export": 0.08,
}

TOPICS = [
    "Battery", "Camera", "Customer Service", "Pricing", "Delivery",
    "App Update", "User Interface", "Software Bug", "Product Quality",
    "Return Policy", "Streaming Quality", "Gaming Performance",
    "Food Quality", "Travel Experience", "Fashion Trends",
    "Sports Highlights", "Movie Review", "Music Release",
    "Politics", "Weather", "Health Tips", "Education", "Environment",
]

HASHTAG_MAP = {
    "Battery": ["battery", "batterylife", "chargefail"],
    "Camera": ["camera", "photography", "cameraquality"],
    "Customer Service": ["customerservice", "support", "cx"],
    "Pricing": ["pricing", "toexpensive", "valueformoney"],
    "Delivery": ["delivery", "shipping", "logistics"],
    "App Update": ["appupdate", "software", "newversion"],
    "User Interface": ["ui", "ux", "design"],
    "Software Bug": ["bug", "crash", "glitch"],
    "Product Quality": ["quality", "productreview", "buildquality"],
    "Return Policy": ["returns", "refund", "policy"],
    "Streaming Quality": ["streaming", "buffering", "videoquality"],
    "Gaming Performance": ["gaming", "fps", "lag"],
    "Food Quality": ["foodie", "foodreview", "yum"],
    "Travel Experience": ["travel", "vacation", "wanderlust"],
    "Fashion Trends": ["fashion", "style", "ootd"],
    "Sports Highlights": ["sports", "gameday", "highlights"],
    "Movie Review": ["movienight", "cinema", "review"],
    "Music Release": ["newmusic", "album", "nowplaying"],
    "Politics": ["politics", "election", "policy"],
    "Weather": ["weather", "storm", "forecast"],
    "Health Tips": ["health", "wellness", "fitness"],
    "Education": ["education", "learning", "students"],
    "Environment": ["climate", "sustainability", "green"],
}

EMOJIS_POS = ["😍", "🔥", "👏", "💯", "🎉", "😊", "❤️", "✨", "👍", "🙌"]
EMOJIS_NEG = ["😡", "😤", "👎", "💔", "😞", "🤬", "😑", "😢", "⚠️", "🙄"]
EMOJIS_NEU = ["🤔", "📌", "👀", "📝", "🔄", "📅"]

FIRST_NAMES = ["alex", "priya", "sam", "jordan", "ravi", "mia", "leo", "kavya",
               "noah", "sara", "omar", "tara", "ken", "zoe", "arjun", "lily",
               "diego", "maya", "chris", "nina"]

MENTIONS = ["@techdaily", "@supportteam", "@globalnews", "@reviewhub",
            "@storeofficial", "@friend22", "@teamupdates", "@localguide"]

URLS = ["https://example.com/post", "http://bit.ly/3xample", "https://news.example.org/story",
        "https://example.net/article"]

POSITIVE_TEMPLATES = [
    "Absolutely loving the {topic} lately, {emoji} best decision ever!",
    "Just have to say the {topic} experience today was amazing {emoji}",
    "Huge shoutout to everyone talking about {topic}, so impressed {emoji}",
    "Can't stop smiling about {topic}, totally worth it {emoji}",
    "The {topic} update fixed everything, great job team {emoji}",
    "Best {topic} I've seen in a long time, highly recommend {hashtag}",
    "Wow, {topic} really outdid themselves this time {emoji}",
    "Super happy with how {topic} turned out, 10/10 {emoji}",
    "{topic} just made my day, thank you so much {emoji}",
    "Finally some good news about {topic}, feeling great {emoji}",
    "This {topic} review is going to be all praise, honestly {emoji}",
    "Been using it for a week and the {topic} is fantastic {hashtag}",
    "Kudos to the {topic} team, exceeded my expectations {emoji}",
    "Nothing but love for {topic} right now {emoji} {hashtag}",
    "Genuinely impressed by the {topic}, five stars {emoji}",
    "Honestly {topic} isn't bad at all, pleasantly surprised {emoji}",
    "Not gonna lie, {topic} turned out pretty good {emoji}",
    "{topic} has been decent lately, can't complain {emoji}",
    "Things are looking up with {topic}, glad I stuck with it {emoji}",
    "I'd say {topic} is solid overall, no real complaints {emoji}",
    "{topic} today was actually pretty good, would try again",
    "Turns out {topic} was worth it after all {emoji}",
]

NEGATIVE_TEMPLATES = [
    "Really disappointed with {topic}, this needs to be fixed asap {emoji}",
    "Worst {topic} experience I've had in years, avoid at all costs {emoji}",
    "Cannot believe how bad the {topic} situation has gotten {emoji}",
    "So frustrated with {topic} right now, nothing works {emoji}",
    "This is the third time {topic} has let me down {emoji} {hashtag}",
    "Terrible {topic}, wasted my time and money {emoji}",
    "Why is {topic} still broken after all these complaints? {emoji}",
    "Extremely unhappy with {topic}, do better {emoji}",
    "The {topic} quality has dropped so much, unacceptable {hashtag}",
    "I regret ever trying {topic}, complete disaster {emoji}",
    "Customer service ignored my {topic} complaint for days {emoji}",
    "Not going to recommend {topic} to anyone after this {emoji}",
    "{topic} keeps crashing and support is useless {emoji} {hashtag}",
    "Feeling scammed by {topic} honestly {emoji}",
    "This {topic} update made everything worse, roll it back {emoji}",
    "Honestly {topic} just isn't cutting it anymore {emoji}",
    "Not gonna lie, {topic} has been kind of a letdown {emoji}",
    "{topic} has been rough lately, hard to stay positive {emoji}",
    "Things aren't looking good with {topic}, getting concerned {emoji}",
    "I'd say {topic} needs serious work, lots of complaints {emoji}",
    "{topic} today was actually pretty disappointing, wouldn't try again",
    "Turns out {topic} wasn't worth it after all {emoji}",
]

NEUTRAL_TEMPLATES = [
    "Just posted a new update about {topic}, check it out {url}",
    "Anyone else following the {topic} news today?",
    "Here's a quick summary of {topic} for anyone interested {url}",
    "Curious what people think about {topic}, drop your thoughts below",
    "Saw an article on {topic} earlier, sharing the link {url}",
    "Still deciding what I think about {topic}, need more info",
    "{topic} was trending today, here's what happened {hashtag}",
    "Question: does anyone have tips regarding {topic}?",
    "Watching a documentary about {topic} right now",
    "Scheduled a meeting to discuss {topic} next week",
    "Reading up on {topic} before making any decisions",
    "Neutral take: {topic} has both pros and cons worth noting",
    "Posting my notes on {topic} for reference {url}",
    "Just an update, {topic} is still ongoing, will report back",
    "Comparing a few options related to {topic} this weekend",
    "{topic} was okay today, nothing special either way",
    "Mixed feelings about {topic} honestly, some good some bad",
    "{topic} is fine I guess, still forming an opinion",
    "Not sure how I feel about {topic} yet, will update later",
    "{topic} today was about what I expected, nothing more nothing less",
]

SENTIMENT_TEMPLATES = {
    "Positive": (POSITIVE_TEMPLATES, EMOJIS_POS),
    "Negative": (NEGATIVE_TEMPLATES, EMOJIS_NEG),
    "Neutral": (NEUTRAL_TEMPLATES, EMOJIS_NEU),
}

# Slightly skew overall sentiment mix so the demo has realistic variety
# (not perfectly balanced, so analytics/alerts have something to show).
SENTIMENT_WEIGHTS = {"Positive": 0.40, "Neutral": 0.32, "Negative": 0.28}


def weighted_choice(weight_map):
    items, weights = zip(*weight_map.items())
    return random.choices(items, weights=weights, k=1)[0]


def random_username():
    return f"{random.choice(FIRST_NAMES)}{random.randint(10, 9999)}"


def random_date():
    start = datetime(2025, 4, 1)
    days_span = 180
    offset = random.randint(0, days_span)
    dt = start + timedelta(days=offset, hours=random.randint(0, 23), minutes=random.randint(0, 59))
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def build_hashtags(topic):
    if random.random() < MISSING_HASHTAG_RATE:
        return ""
    pool = HASHTAG_MAP.get(topic, ["general"])
    n = random.randint(1, min(3, len(pool)))
    tags = random.sample(pool, n)
    return " ".join(f"#{t}" for t in tags)


def build_text(topic, sentiment, hashtags):
    templates, emojis = SENTIMENT_TEMPLATES[sentiment]
    template = random.choice(templates)
    text = template.format(
        topic=topic.lower(),
        emoji=random.choice(emojis),
        hashtag=(f"#{random.choice(HASHTAG_MAP.get(topic, ['general']))}"),
        url=random.choice(URLS),
    )

    # Sprinkle in extra realism: mentions, extra urls, messy punctuation/whitespace
    if random.random() < 0.25:
        text = f"{random.choice(MENTIONS)} {text}"
    if random.random() < 0.12 and "http" not in text:
        text = f"{text} {random.choice(URLS)}"
    if hashtags and random.random() < 0.7:
        text = f"{text} {hashtags}"
    if random.random() < 0.15:
        text = text + "!!!"
    if random.random() < 0.1:
        text = "   " + text + "   "
    if random.random() < 0.08:
        text = text.replace(" ", "  ", 1)  # double space glitch

    return text.strip() if random.random() > 0.1 else text  # keep some raw whitespace for cleaning demo


def generate_rows(n):
    rows = []
    for i in range(1, n + 1):
        platform = weighted_choice(PLATFORMS)
        topic = random.choice(TOPICS) if random.random() > MISSING_TOPIC_RATE else ""
        sentiment = weighted_choice(SENTIMENT_WEIGHTS)  # the recorded/ground-truth label

        # Simulate real-world label noise: for a small fraction of posts, the
        # text is written in a *different* tone than the label says (sarcasm,
        # ambiguous wording, annotator disagreement). The label stays as
        # `sentiment`; only the template used to build the text changes.
        text_sentiment = sentiment
        if random.random() < LABEL_NOISE_RATE:
            text_sentiment = random.choice([s for s in SENTIMENT_WEIGHTS if s != sentiment])

        hashtags = build_hashtags(topic) if topic else ""
        text = build_text(topic if topic else random.choice(TOPICS), text_sentiment, hashtags)

        text_for_labels = text  # always-present text, used for the labeled training file

        if random.random() < MISSING_TEXT_RATE:
            text = ""

        platform_prefix = {
            "Instagram": "IG", "X/Twitter": "TW", "Facebook": "FB",
            "YouTube": "YT", "Reddit": "RD", "WhatsApp Export": "WA",
        }[platform]

        row = {
            "id": i,
            "platform": platform,
            "post_id": f"{platform_prefix}-{100000 + i}",
            "author": random_username(),
            "text": text,
            "date": random_date(),
            "topic": topic,
            "hashtags": hashtags,
            "_sentiment_label": sentiment,  # ground truth, used only for ml/ training (see below)
            "_label_text": text_for_labels,
            "_is_duplicate": False,
        }
        rows.append(row)

    # Inject duplicate rows (simulating re-scraped/duplicate posts)
    num_duplicates = int(n * DUPLICATE_RATE)
    for _ in range(num_duplicates):
        src = random.choice(rows).copy()
        src["id"] = len(rows) + 1
        src["_is_duplicate"] = True
        rows.append(src)

    random.shuffle(rows)
    for idx, row in enumerate(rows, start=1):
        row["id"] = idx

    return rows


def main():
    rows = generate_rows(NUM_ROWS)
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["id", "platform", "post_id", "author", "text", "date", "topic", "hashtags"]
    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in fieldnames})

    print(f"Generated {len(rows)} rows -> {OUTPUT_PATH}")

    # Separate labeled training file: the ground-truth sentiment used to build
    # each post's text, exposed only here so ml/train.py has something to
    # train/evaluate against. Excludes injected duplicates (avoids train/test
    # leakage) since those are meant to test dedup logic, not train on.
    label_fieldnames = ["id", "platform", "text", "sentiment"]
    with open(LABELED_OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=label_fieldnames)
        writer.writeheader()
        for row in rows:
            if row["_is_duplicate"]:
                continue
            writer.writerow({
                "id": row["id"],
                "platform": row["platform"],
                "text": row["_label_text"],
                "sentiment": row["_sentiment_label"],
            })
    print(f"Generated labeled training file -> {LABELED_OUTPUT_PATH}")
    print("NOTE: This is 100% SYNTHETIC DEMO DATA. No real social media content is included.")


if __name__ == "__main__":
    main()
