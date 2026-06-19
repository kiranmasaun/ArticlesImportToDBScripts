import json
import re
import mysql.connector

JSON_FILE = "TopLineNews JSON_Crime_06.10-11Jun.json"

# ----------------------------------------------------------------------
# DB CONFIG
# ----------------------------------------------------------------------
DB_HOST     = "sd-rds-01.c8lpklkvlcek.us-west-2.rds.amazonaws.com"
DB_PORT     = 3306
DB_USER     = "kirandeep.kaur"
DB_PASSWORD = "FTfdD!21313Ad"
DB_NAME     = "NewsEngine"

COLUMNS_TO_CHECK = ["slug", "title", "headlines", "short_headlines", "author_name", "markdown_content", "categories"]


def find_non_ascii(text):
    """Return list of (char, position) tuples for non-ASCII characters in a string."""
    return [(ch, idx) for idx, ch in enumerate(text) if ord(ch) > 127]


def check_value(value):
    """Recursively check a value (str or list of str) for non-ASCII characters."""
    issues = []
    if isinstance(value, str):
        hits = find_non_ascii(value)
        if hits:
            issues.append({
                "snippet": value[:120],
                "non_ascii_chars": [{"char": ch, "unicode": f"U+{ord(ch):04X}", "position": pos} for ch, pos in hits]
            })
    elif isinstance(value, list):
        for i, item in enumerate(value):
            if isinstance(item, str):
                hits = find_non_ascii(item)
                if hits:
                    issues.append({
                        "index": i,
                        "snippet": item[:120],
                        "non_ascii_chars": [{"char": ch, "unicode": f"U+{ord(ch):04X}", "position": pos} for ch, pos in hits]
                    })
    return issues


def main():
    with open(JSON_FILE, "r", encoding="utf-8") as f:
        articles = json.load(f)

    flagged_articles = []

    for article_idx, article in enumerate(articles):
        article_issues = {}

        for col in COLUMNS_TO_CHECK:
            value = article.get(col)

            # Skip short_headlines if empty/null
            if col == "short_headlines" and not value:
                continue

            if value is None:
                continue

            issues = check_value(value)
            if issues:
                article_issues[col] = issues

        if article_issues:
            flagged_articles.append({
                "article_index": article_idx + 1,
                "slug": article.get("slug", "N/A"),
                "title": article.get("title", "N/A"),
                "issues": article_issues
            })

    # ---------- Report ----------
    print("=" * 70)
    print(f"Non-ASCII Check Report: {JSON_FILE}")
    print("=" * 70)
    print(f"Total articles checked : {len(articles)}")
    print(f"Articles with issues   : {len(flagged_articles)}")
    print()

    if not flagged_articles:
        print("All articles passed. No non-ASCII characters found.")
    else:
        for entry in flagged_articles:
            print(f"Article #{entry['article_index']}: {entry['title']}")
            print(f"  Slug : {entry['slug']}")
            for col, issues in entry["issues"].items():
                print(f"  Column: [{col}]")
                for issue in issues:
                    if "index" in issue:
                        print(f"    - Item index {issue['index']}: \"{issue['snippet']}\"")
                    else:
                        print(f"    - \"{issue['snippet']}\"")
                    for ch_info in issue["non_ascii_chars"]:
                        print(f"      Non-ASCII char: '{ch_info['char']}' ({ch_info['unicode']}) at position {ch_info['position']}")
            print()

        print("=" * 70)
        print("Summary of flagged articles:")
        for entry in flagged_articles:
            cols = ", ".join(entry["issues"].keys())
            print(f"  #{entry['article_index']} | {entry['slug']} | Columns: {cols}")
        print("=" * 70)

    # ------------------------------------------------------------------
    # 2. DUPLICATE SLUG CHECK — within the JSON file
    # ------------------------------------------------------------------
    print()
    print("=" * 70)
    print("Duplicate Slug Check (within file)")
    print("=" * 70)

    file_duplicates = check_duplicate_slugs_in_file(articles)

    if not file_duplicates:
        print("  No duplicate slugs found within the file.")
    else:
        print(f"  {len(file_duplicates)} duplicate slug(s) found:\n")
        for slug, indexes in file_duplicates.items():
            idx_str = ", ".join(f"#{i}" for i in indexes)
            print(f"  Slug      : {slug}")
            print(f"  Articles  : {idx_str}")
            print()

    # ------------------------------------------------------------------
    # 3. DB SLUG CHECK — against NewsEngine.blogs
    # ------------------------------------------------------------------
    print()
    print("=" * 70)
    print("DB Duplicate Slug Check (against NewsEngine.blogs)")
    print("=" * 70)

    all_slugs = [
        a.get("slug", "").strip() for a in articles if a.get("slug", "").strip()
    ]

    db_matches = check_duplicate_slugs_in_db(all_slugs)

    if db_matches is None:
        print("  Skipped — could not connect to database.")
    elif not db_matches:
        print("  No slugs from this file already exist in the database.")
    else:
        print(f"  {len(db_matches)} slug(s) already exist in DB:\n")
        for row in db_matches:
            print(f"  DB id    : {row['id']}")
            print(f"  Slug     : {row['slug']}")
            print(f"  DB Title : {row['title'][:100]}")
            print()

    # ------------------------------------------------------------------
    # FINAL SUMMARY
    # ------------------------------------------------------------------
    print("=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    print(f"  Total articles checked        : {len(articles)}")
    print(f"  Articles with non-ASCII       : {len(flagged_articles)}")
    print(f"  Duplicate slugs (in file)     : {len(file_duplicates)}")
    db_count = len(db_matches) if db_matches is not None else "N/A (DB error)"
    print(f"  Slugs already in DB           : {db_count}")
    print("=" * 70)


def check_duplicate_slugs_in_file(articles):
    """Return list of slug values that appear more than once in the JSON file."""
    seen = {}
    for idx, article in enumerate(articles):
        slug = article.get("slug", "").strip()
        if not slug:
            continue
        if slug not in seen:
            seen[slug] = []
        seen[slug].append(idx + 1)   # 1-based article index

    return {slug: indexes for slug, indexes in seen.items() if len(indexes) > 1}


def check_duplicate_slugs_in_db(slugs):
    """Query NewsEngine.blogs and return DB rows whose slug matches any in the list."""
    if not slugs:
        return []
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
        )
        cursor = conn.cursor(dictionary=True)
        placeholders = ", ".join(["%s"] * len(slugs))
        cursor.execute(
            f"SELECT id, slug, title FROM blogs WHERE slug IN ({placeholders})",
            slugs,
        )
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        return rows
    except mysql.connector.Error as e:
        print(f"  DB ERROR: {e}")
        return None


if __name__ == "__main__":
    main()
