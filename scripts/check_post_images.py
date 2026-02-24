import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / 'db.sqlite3'
if not DB.exists():
    print('db.sqlite3 not found at', DB)
    raise SystemExit(1)

conn = sqlite3.connect(str(DB))
cur = conn.cursor()

cur.execute('SELECT post_id, COUNT(*) FROM core_postimage GROUP BY post_id ORDER BY COUNT(*) DESC')
rows = cur.fetchall()
print('post_id,count')
for r in rows:
    print(f'{r[0]},{r[1]}')

# show files for posts with count > 3
cur.execute('SELECT post_id, image FROM core_postimage ORDER BY post_id, id')
all_imgs = cur.fetchall()
from collections import defaultdict
m = defaultdict(list)
for post_id, image in all_imgs:
    m[post_id].append(image)

for post_id, imgs in m.items():
    if len(imgs) > 3:
        print('\nPost', post_id, 'images:', len(imgs))
        for im in imgs:
            print(' -', im)

conn.close()
