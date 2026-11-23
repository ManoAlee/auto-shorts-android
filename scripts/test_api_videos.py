import json
import urllib.request

try:
    resp = urllib.request.urlopen("http://127.0.0.1:8787/api/videos")
    data = json.loads(resp.read().decode("utf-8"))
    vids = data.get("videos", [])
    print(f"Total videos returned: {len(vids)}")
    for i, v in enumerate(vids, 1):
        print(f"{i:02d}. {v.get('title')}")
except Exception as e:
    print(f"Error checking API: {e}")
