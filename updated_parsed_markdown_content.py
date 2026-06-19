import json
import mysql.connector
import markdown

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
# Helper function
# --------------------------
def parse_markdown(content):
    """
    Converts ONLY markdown to HTML.
    Assumes input is raw markdown.
    """

    extensions=[
        "extra",       # adds tables, fenced code blocks, footnotes, definition lists, abbreviations
        "smarty",      # converts quotes, dashes, ellipses into typographically correct forms
        "sane_lists",  # better nested list handling
        "toc",         # table of contents support
        "nl2br",       # converts single line breaks to <br>
        "attr_list",   # enables setting HTML attributes on elements (like id/class)
        "md_in_html",  # allows Markdown inside HTML blocks (important for your <YoutubeEmbed /> etc.)
        "codehilite"   # adds syntax highlighting for code blocks
    ]

    return markdown.markdown(content, extensions=extensions)

# --------------------------
# SQL
# --------------------------
update_markdown_sql = """
UPDATE blogs
SET markdown_content = %s, updated_at = NOW() 
WHERE id = %s
"""

# --------------------------
# Process blogs.json
# --------------------------
file_path = "boldfact-blogs-Dec12-final-image-links.json"
batch_size = 50
count = 0
print(f"markdown contents script started...")

with open(file_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue

        try:
            blog = json.loads(line)
        except json.JSONDecodeError:
            continue

        blog_id = blog.get("id")
        markdown_content = blog.get("markdown_content")

        # Skip if no markdown content
        if not blog_id or not markdown_content:
            continue

        # Parse markdown → HTML
        parsed_html = parse_markdown(markdown_content)

        # Update ONLY markdown_content
        cursor.execute(update_markdown_sql, (parsed_html, blog_id))

        count += 1
        if count % batch_size == 0:
            conn.commit()
            print(f"{count} markdown contents updated...")

# Final commit
conn.commit()
cursor.close()
conn.close()

print("Markdown content updated successfully!")
