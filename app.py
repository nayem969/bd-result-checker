"""
বাংলাদেশ রেজাল্ট চেকার - ব্যাকএন্ড সার্ভার
=============================================
educationboardresults.gov.bd থেকে নাম দিয়ে রেজাল্ট খোঁজে।

চালানোর নির্দেশ:
  pip install flask flask-cors requests beautifulsoup4
  python app.py

API ব্যবহার:
  POST /api/result
  Body: { "name": "রাহেলা বেগম", "exam": "SSC", "year": "2024", "board": "Dhaka" }
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re

app = Flask(__name__)
CORS(app)  # ফ্রন্টএন্ড থেকে কল করতে দেবে

# ===== বোর্ড কোড ম্যাপিং =====
BOARD_CODES = {
    "ঢাকা":         "dhaka",
    "Dhaka":        "dhaka",
    "চট্টগ্রাম":   "chittagong",
    "Chittagong":   "chittagong",
    "রাজশাহী":     "rajshahi",
    "Rajshahi":     "rajshahi",
    "যশোর":         "jessore",
    "Jessore":      "jessore",
    "কুমিল্লা":    "comilla",
    "Comilla":      "comilla",
    "বরিশাল":       "barisal",
    "Barisal":      "barisal",
    "সিলেট":        "sylhet",
    "Sylhet":       "sylhet",
    "দিনাজপুর":    "dinajpur",
    "Dinajpur":     "dinajpur",
    "ময়মনসিংহ":   "mymensingh",
    "Mymensingh":   "mymensingh",
    "মাদরাসা বোর্ড": "madrasah",
    "Madrasah":     "madrasah",
    "কারিগরি বোর্ড": "tec",
    "Technical":    "tec",
}

# ===== পরীক্ষা কোড ম্যাপিং =====
EXAM_CODES = {
    "SSC":    "ssc",
    "HSC":    "hsc",
    "JSC":    "jsc",
    "JDC":    "jdc",
    "PSC":    "psc",
    "Degree": "degree",
}

BASE_URL = "https://www.educationboardresults.gov.bd"


def fetch_result_by_roll(exam, year, board, roll):
    """
    রোল নম্বর দিয়ে একটি রেজাল্ট আনে।
    educationboardresults.gov.bd এর ফর্ম সাবমিট করে স্ক্র্যাপ করে।
    """
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Referer": BASE_URL,
        })

        # প্রথমে হোমপেজ লোড করে ক্যাপচা/টোকেন নিই
        home = session.get(BASE_URL + "/", timeout=10)
        soup = BeautifulSoup(home.text, "html.parser")

        # ফর্ম ডেটা তৈরি
        payload = {
            "exam":         EXAM_CODES.get(exam, "ssc"),
            "year":         year,
            "board":        BOARD_CODES.get(board, "dhaka"),
            "roll":         str(roll),
            "reg":          "",  # রেজিস্ট্রেশন ঐচ্ছিক
            "button2":      "Submit",
        }

        # hidden input থাকলে যোগ করি
        for hidden in soup.find_all("input", {"type": "hidden"}):
            payload[hidden.get("name", "")] = hidden.get("value", "")

        resp = session.post(BASE_URL + "/", data=payload, timeout=15)
        return parse_result_page(resp.text)

    except requests.RequestException as e:
        return {"error": f"নেটওয়ার্ক সমস্যা: {str(e)}"}


def parse_result_page(html):
    """
    রেজাল্ট পেজ পার্স করে ডেটা বের করে।
    """
    soup = BeautifulSoup(html, "html.parser")

    # সাধারণ এরর চেক
    if "No result found" in html or "Invalid" in html:
        return {"error": "কোনো রেজাল্ট পাওয়া যায়নি।"}

    result = {}

    # ছাত্র/ছাত্রীর তথ্য টেবিল থেকে বের করা
    tables = soup.find_all("table")
    for table in tables:
        rows = table.find_all("tr")
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            if len(cells) >= 2:
                key = cells[0].lower()
                val = cells[1] if len(cells) > 1 else ""

                if "name" in key or "নাম" in key:
                    result["name"] = val
                elif "roll" in key or "রোল" in key:
                    result["roll"] = val
                elif "reg" in key or "রেজি" in key:
                    result["registration"] = val
                elif "father" in key or "পিতা" in key:
                    result["father_name"] = val
                elif "mother" in key or "মাতা" in key:
                    result["mother_name"] = val
                elif "school" in key or "institution" in key or "প্রতিষ্ঠান" in key:
                    result["institution"] = val
                elif "gpa" in key:
                    result["gpa"] = val
                elif "grade" in key or "গ্রেড" in key:
                    result["grade"] = val
                elif "result" in key or "ফলাফল" in key:
                    result["pass_status"] = val

    # বিষয়ভিত্তিক মার্ক
    subjects = []
    for table in tables:
        header_cells = [th.get_text(strip=True).lower() for th in table.find_all("th")]
        if any(x in " ".join(header_cells) for x in ["subject", "marks", "grade", "বিষয়"]):
            for row in table.find_all("tr")[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cells) >= 2:
                    subjects.append({
                        "subject": cells[0] if len(cells) > 0 else "",
                        "marks":   cells[1] if len(cells) > 1 else "",
                        "grade":   cells[2] if len(cells) > 2 else "",
                    })
            break

    if subjects:
        result["subjects"] = subjects

    if not result:
        return {"error": "রেজাল্ট পার্স করা সম্ভব হয়নি।"}

    return result


def search_by_name(name, exam, year, board, father_name=""):
    """
    নাম দিয়ে রেজাল্ট খোঁজার জন্য একটি রোল-রেঞ্জে সার্চ করে।
    
    বাস্তব পদ্ধতি:
    educationboardresults.gov.bd এ নাম-ভিত্তিক সরাসরি API নেই।
    তাই নামের সাথে মেলানো রেজাল্ট খুঁজতে দুটি পদ্ধতি ব্যবহার করা হয়:
    1. Board এর নিজস্ব name-search endpoint (যদি থাকে)
    2. বিকল্প সার্ভিস যেমন eboardresults.com
    """
    # পদ্ধতি ১: eboardresults.com (নাম সার্চ সাপোর্ট করে)
    try:
        result = search_eboardresults(name, exam, year, board, father_name)
        if result and "error" not in result:
            return result
    except Exception:
        pass

    # পদ্ধতি ২: সরাসরি educationboardresults.gov.bd
    try:
        result = search_official_by_name(name, exam, year, board)
        if result and "error" not in result:
            return result
    except Exception:
        pass

    return {"error": f"'{name}' নামে কোনো রেজাল্ট পাওয়া যায়নি। নামটি সঠিকভাবে লিখুন।"}


def search_eboardresults(name, exam, year, board, father_name=""):
    """
    eboardresults.com এ নাম দিয়ে সার্চ করে।
    """
    board_code = BOARD_CODES.get(board, "dhaka")
    exam_code = EXAM_CODES.get(exam, "ssc")

    url = f"https://eboardresults.com/v2/home"
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://eboardresults.com/",
    })

    # ফর্ম পেলোড
    payload = {
        "exam":   exam_code,
        "year":   year,
        "board":  board_code,
        "name":   name,
        "type":   "3",  # নাম দিয়ে সার্চ
    }
    if father_name:
        payload["fname"] = father_name

    resp = session.post(url, data=payload, timeout=15)
    return parse_eboardresults(resp.text, name)


def parse_eboardresults(html, search_name):
    """
    eboardresults.com এর রেজাল্ট পেজ পার্স করে।
    """
    soup = BeautifulSoup(html, "html.parser")

    if "not found" in html.lower() or "no result" in html.lower():
        return {"error": "কোনো রেজাল্ট পাওয়া যায়নি।"}

    results = []
    rows = soup.select("table tr")
    for row in rows[1:]:  # হেডার বাদ দিয়ে
        cells = [td.get_text(strip=True) for td in row.find_all("td")]
        if len(cells) >= 3:
            student_name = cells[1] if len(cells) > 1 else ""
            # নামের সাথে মিলিয়ে দেখা
            if search_name.lower() in student_name.lower():
                results.append({
                    "roll": cells[0],
                    "name": student_name,
                    "gpa":  cells[-1],
                    "pass_status": "Pass" if "F" not in cells[-1] else "Fail",
                })

    if results:
        return {"multiple_results": results, "total": len(results)}

    return {"error": "নাম মিলল না।"}


def search_official_by_name(name, exam, year, board):
    """
    educationboardresults.gov.bd এর অফিশিয়াল এন্ডপয়েন্ট ব্যবহার।
    """
    board_code = BOARD_CODES.get(board, "dhaka")
    exam_code = EXAM_CODES.get(exam, "ssc")

    url = f"{BASE_URL}/result.php"
    payload = {
        "exam":   exam_code,
        "year":   year,
        "board":  board_code,
        "sname":  name,  # নাম দিয়ে সার্চ প্যারামিটার
        "type":   "2",
    }

    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0", "Referer": BASE_URL})
    resp = session.post(url, data=payload, timeout=15)
    return parse_result_page(resp.text)


# ===== API রাউট =====

@app.route("/api/result", methods=["POST"])
def get_result():
    """
    মূল API এন্ডপয়েন্ট।
    
    Request Body (JSON):
    {
        "name":        "রাহেলা বেগম",      (আবশ্যিক)
        "exam":        "SSC",               (আবশ্যিক)
        "year":        "2024",              (আবশ্যিক)
        "board":       "ঢাকা",             (আবশ্যিক)
        "father_name": "করিম সাহেব"        (ঐচ্ছিক)
    }
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "কোনো ডেটা পাঠানো হয়নি।"}), 400

    name = data.get("name", "").strip()
    exam = data.get("exam", "SSC").strip()
    year = data.get("year", "2024").strip()
    board = data.get("board", "ঢাকা").strip()
    father_name = data.get("father_name", "").strip()

    if not name:
        return jsonify({"error": "নাম দেওয়া আবশ্যিক।"}), 400

    result = search_by_name(name, exam, year, board, father_name)
    return jsonify(result)


@app.route("/api/result/roll", methods=["POST"])
def get_result_by_roll():
    """
    রোল নম্বর দিয়ে রেজাল্ট।
    """
    data = request.get_json()
    roll = data.get("roll", "")
    exam = data.get("exam", "SSC")
    year = data.get("year", "2024")
    board = data.get("board", "ঢাকা")

    result = fetch_result_by_roll(exam, year, board, roll)
    return jsonify(result)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "সার্ভার চলছে ✅"})


if __name__ == "__main__":
    print("=" * 50)
    print("বাংলাদেশ রেজাল্ট চেকার সার্ভার")
    print("http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000)
