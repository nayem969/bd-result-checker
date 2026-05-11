"""
দিনাজপুর JSC রেজাল্ট সংগ্রহকারী — Resume সিস্টেমসহ
======================================================
- কারেন্ট গেলে বা বন্ধ হলে ঠিক যেখানে ছিল সেখান থেকে শুরু হবে
- progress.json ফাইলে অগ্রগতি সেভ থাকে
- Supabase এ ডেটা জমা হয়

চালানোর নির্দেশ:
  pip install requests beautifulsoup4 supabase python-dotenv
  python collector.py
"""

import requests
from bs4 import BeautifulSoup
import time
import os
import json
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

BOARD         = "dinajpur"
EXAM          = "jsc"
DELAY         = 1.5
BATCH_SIZE    = 50
PROGRESS_FILE = "progress.json"
BASE_URL      = "https://www.educationboardresults.gov.bd"

YEAR_RANGES = {
    2010: (101001, 180000),
    2011: (101001, 182000),
    2012: (101001, 185000),
    2013: (101001, 188000),
    2014: (101001, 190000),
    2015: (101001, 192000),
    2016: (101001, 195000),
    2017: (101001, 197000),
    2018: (101001, 200000),
    2019: (101001, 202000),
    2020: (101001, 200000),
    2021: (101001, 198000),
    2022: (101001, 196000),
}


def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_progress(progress):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def mark_year_done(progress, year):
    progress[str(year)] = {"status": "done"}
    save_progress(progress)


def save_last_roll(progress, year, roll, found):
    progress[str(year)] = {
        "status": "in_progress",
        "last_roll": roll,
        "found_so_far": found,
    }
    save_progress(progress)


def get_start_roll(progress, year):
    key = str(year)
    if key in progress:
        if progress[key]["status"] == "done":
            return None
        last = progress[key].get("last_roll")
        if last:
            print(f"  ⏩ আগের অগ্রগতি পাওয়া গেছে — রোল {last} থেকে শুরু")
            return last + 1
    return YEAR_RANGES[year][0]


def fetch_result(roll, year):
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Referer": BASE_URL,
        })
        home = session.get(BASE_URL + "/", timeout=10)
        soup = BeautifulSoup(home.text, "html.parser")

        payload = {
            "exam": EXAM, "year": str(year),
            "board": BOARD, "roll": str(roll),
            "reg": "", "button2": "Submit",
        }
        for h in soup.find_all("input", {"type": "hidden"}):
            payload[h.get("name", "")] = h.get("value", "")

        resp = session.post(BASE_URL + "/", data=payload, timeout=15)
        return parse_result(resp.text, roll, year)
    except Exception:
        return None


def parse_result(html, roll, year):
    if "No result" in html or "Invalid" in html or "not found" in html.lower():
        return None

    soup = BeautifulSoup(html, "html.parser")
    data = {
        "roll": str(roll), "year": year, "board": "dinajpur", "exam": "JSC",
        "name": None, "father_name": None, "mother_name": None,
        "institution": None, "gpa": None, "grade": None, "pass_status": None,
    }

    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if len(cells) < 2:
                continue
            key = cells[0].lower()
            val = cells[1]
            if "student name" in key or "name" in key:
                data["name"] = val
            elif "father" in key:
                data["father_name"] = val
            elif "mother" in key:
                data["mother_name"] = val
            elif "institution" in key or "school" in key:
                data["institution"] = val
            elif "gpa" in key:
                try: data["gpa"] = float(val)
                except: pass
            elif "grade" in key:
                data["grade"] = val
            elif "result" in key:
                data["pass_status"] = val

    return data if data["name"] else None


def save_batch(batch):
    try:
        supabase.table("results").insert(batch).execute()
        return True
    except Exception as e:
        print(f"  ⚠️ সেভ ত্রুটি: {e}")
        return False


def collect_year(year, progress):
    start_roll = get_start_roll(progress, year)
    if start_roll is None:
        print(f"⏭️  {year} সাল আগেই সম্পন্ন")
        return

    end_roll = YEAR_RANGES[year][1]
    found_before = progress.get(str(year), {}).get("found_so_far", 0)
    print(f"\n📥 {year} সাল — রোল {start_roll} → {end_roll}")

    batch = []
    found = 0

    for roll in range(start_roll, end_roll + 1):
        result = fetch_result(roll, year)
        if result:
            batch.append(result)
            found += 1

        if len(batch) >= BATCH_SIZE:
            save_batch(batch)
            batch = []
            print(f"  💾 সেভ | রোল: {roll} | মোট: {found_before + found}")

        # প্রতি ১০০ রোলে progress সেভ — কারেন্ট গেলেও নিরাপদ ✅
        if (roll - start_roll + 1) % 100 == 0:
            save_last_roll(progress, year, roll, found_before + found)

        if (roll - start_roll + 1) % 500 == 0:
            total = end_roll - YEAR_RANGES[year][0]
            done = roll - YEAR_RANGES[year][0] + 1
            pct = (done / total) * 100
            print(f"  📊 {pct:.1f}% | পাওয়া: {found_before + found}")

        time.sleep(DELAY)

    if batch:
        save_batch(batch)

    mark_year_done(progress, year)
    print(f"✅ {year} সাল শেষ — মোট {found_before + found} রেজাল্ট")


def main():
    print("=" * 50)
    print("দিনাজপুর JSC রেজাল্ট সংগ্রহকারী")
    print("কারেন্ট গেলেও Resume হবে ✅")
    print("=" * 50)

    progress = load_progress()
    years = sorted(YEAR_RANGES.keys())

    done = [y for y in years if progress.get(str(y), {}).get("status") == "done"]
    remaining = [y for y in years if y not in done]

    print(f"\n✅ সম্পন্ন বছর : {done if done else 'কোনোটি না'}")
    print(f"⏳ বাকি বছর   : {remaining}")

    if not remaining:
        print("\n🎉 সব ডেটা সংগ্রহ সম্পন্ন!")
        return

    print("\nশুরু করতে Enter চাপুন, বাদ দিতে Ctrl+C...")
    input()

    for year in remaining:
        try:
            collect_year(year, progress)
        except KeyboardInterrupt:
            print("\n⏸️  বন্ধ। পরে চালু করলে এখান থেকেই শুরু হবে।")
            break
        except Exception as e:
            print(f"❌ {year} সালে ত্রুটি: {e} — পরের বছরে যাচ্ছি...")
            continue

    print("\n✅ সেশন শেষ। পরে চালু করলে বাকিটা শুরু হবে।")


if __name__ == "__main__":
    main()
