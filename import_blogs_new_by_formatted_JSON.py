import json
import mysql.connector
import markdown
import os
import time
import base64

# --------------------------
# CONFIG
# --------------------------
BATCH_SIZE = 50
HEADLINE_BATCH = 500

MD_EXTENSIONS = [
    "extra",       # adds tables, fenced code blocks, footnotes, definition lists, abbreviations
    "smarty",      # converts quotes, dashes, ellipses into typographically correct forms
    "sane_lists",  # better nested list handling
    "toc",         # table of contents support
    "nl2br",       # converts single line breaks to <br>
    "attr_list",   # enables setting HTML attributes on elements (like id/class)
    "md_in_html",  # allows Markdown inside HTML blocks (important for your <YoutubeEmbed /> etc.)
    "codehilite"   # adds syntax highlighting for code blocks
]

# --------------------------
# DB connection
# --------------------------
conn = mysql.connector.connect(
    host="sd-rds-01.c8lpklkvlcek.us-west-2.rds.amazonaws.com",
    user="kirandeep.kaur",
    password="FTfdD!21313Ad",
    database="NewsEngine"
)
cursor = conn.cursor()

# --------------------------
# Markdown Parser
# --------------------------
def parse_markdown(content):
    """
    Converts ONLY markdown to HTML.
    Assumes input is raw markdown.
    """
    if not content:
        return ""

    return markdown.markdown(content, extensions=MD_EXTENSIONS)

# --------------------------
# Category handler (cached)
# --------------------------
CATEGORY_CACHE = {}

def get_or_create_category(name):
    if name in CATEGORY_CACHE:
        return CATEGORY_CACHE[name]

    cursor.execute("SELECT id FROM categories WHERE name=%s", (name,))
    row = cursor.fetchone()
    if row:
        CATEGORY_CACHE[name] = row[0]
        return row[0]

    cursor.execute("INSERT INTO categories (name) VALUES (%s)", (name,))
    conn.commit()
    CATEGORY_CACHE[name] = cursor.lastrowid
    return cursor.lastrowid

# --------------------------
# SQL
# --------------------------
BLOG_SQL = """
INSERT INTO blogs (
    id, slug, title, short_headlines,
    author_name, publish_date,
    markdown_content, category_id
)
VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
ON DUPLICATE KEY UPDATE
title=VALUES(title),
short_headlines=VALUES(short_headlines),
author_name=VALUES(author_name),
publish_date=VALUES(publish_date),
markdown_content=VALUES(markdown_content),
category_id=VALUES(category_id)
"""

HEADLINE_SQL = """
INSERT IGNORE INTO blog_headlines (blog_id, headline, headline_index)
VALUES (%s,%s,%s)
"""

def generate_blog_id():
    """
    Generates a sortable, URL-safe alphanumeric ID
    similar to: 015QUPQTvl5p2bdBREosMs
    """
    timestamp_ms = int(time.time() * 1000).to_bytes(6, "big")
    random_bytes = os.urandom(10)
    raw = timestamp_ms + random_bytes

    # Base32 encode, lowercase, strip padding
    return base64.b32encode(raw).decode("utf-8").rstrip("=").lower()

# --------------------------
# Process JSON (JSON Lines)
# --------------------------
blog_count = 0
headline_buffer = []

with open("boldfacts_articles_2026-01-13_v9_key_order_fixed.json", "r", encoding="utf-8") as f:
    blogs = json.load(f)

for blog in blogs:
    # ✅ Generate ID if missing
    blog_id = blog.get("id") or generate_blog_id()

    markdown_content = blog.get("markdown_content", "")
    html_content = parse_markdown(markdown_content)

    category = blog.get("categories", ["Uncategorized"])[0]
    cat_id = get_or_create_category(category)

    cursor.execute(
        BLOG_SQL,
        (
            blog_id,
            blog["slug"],
            blog["title"],
            blog.get("short_headlines"),
            blog.get("author_name"),
            blog.get("publish_date"),
            html_content,
            cat_id
        )
    )

    # ✅ Deduplicate headlines (preserve order)
    headlines = list(dict.fromkeys(blog.get("headlines", [])))
    for pos, h in enumerate(headlines):
        headline_buffer.append((blog_id, h, pos))

    if len(headline_buffer) >= HEADLINE_BATCH:
        cursor.executemany(HEADLINE_SQL, headline_buffer)
        headline_buffer.clear()

    blog_count += 1

    if blog_count % BATCH_SIZE == 0:
        conn.commit()
        print(f"Processed {blog_count} blogs...")

# Final flush
if headline_buffer:
    cursor.executemany(HEADLINE_SQL, headline_buffer)

conn.commit()
cursor.close()
conn.close()

print("\n✅ Import completed successfully")
print(f"Total blogs processed: {blog_count}")
