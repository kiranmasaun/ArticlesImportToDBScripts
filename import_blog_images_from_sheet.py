import pandas as pd
import mysql.connector

# --------------------------
# LOAD EXCEL
# --------------------------
file_path = "Master News articles.xlsx"
sheet_name = "Articles from VP"

df = pd.read_excel(file_path, sheet_name=sheet_name)

# Keep only required columns
df = df[['id', 's3_image_name']].dropna()

# Rename columns
df.columns = ['blog_id', 'file_name']

# Remove duplicates within Excel
df = df.drop_duplicates(subset=['blog_id', 'file_name'])

# --------------------------
# MYSQL CONNECTION
# --------------------------
conn = mysql.connector.connect(
    host="sd-rds-01.c8lpklkvlcek.us-west-2.rds.amazonaws.com",
    user="kirandeep.kaur",
    password="FTfdD!21313Ad",
    database="NewsEngine"
)

cursor = conn.cursor()

# --------------------------
# INSERT QUERY
# --------------------------
sql = """
INSERT INTO NewsEngine.blog_images (blog_id, file_name)
VALUES (%s, %s)
ON DUPLICATE KEY UPDATE file_name = file_name;
"""

data = list(df.itertuples(index=False, name=None))

cursor.executemany(sql, data)
conn.commit()

print(f"Processed {len(data)} records safely.")

cursor.close()
conn.close()
