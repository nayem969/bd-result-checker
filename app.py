"""
বাংলাদেশ রেজাল্ট চেকার - আপডেটেড ব্যাকএন্ড
=============================================
Supabase ডেটাবেজ থেকে নাম দিয়ে রেজাল্ট খোঁজে।
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Supabase সংযোগ
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


@app.route("/api/result", methods=["POST"])
def search_by_name():
    data = request.get_json()
    if not data:
        return jsonify({"error": "কোনো ডেটা পাঠানো হয়নি।"}), 400

    name        = data.get("name", "").strip()
    year        = data.get("year", "")
    board       = data.get("board", "")
    exam        = data.get("exam", "JSC")
    father_name = data.get("father_name", "").strip()

    if not name:
        return jsonify({"error": "নাম দেওয়া আবশ্যিক।"}), 400

    try:
        query = supabase.table("results")\
            .select("*")\
            .ilike("name", f"%{name}%")

        if year:
            query = query.eq("year", int(year))
        if exam:
            query = query.ilike("exam", f"%{exam}%")
        if father_name:
            query = query.ilike("father_name", f"%{father_name}%")

        query = query.limit(20)
        res = query.execute()

        if not res.data:
            return jsonify({"error": f"'{name}' নামে কোনো রেজাল্ট পাওয়া যায়নি।"})

        if len(res.data) == 1:
            return jsonify(res.data[0])

        return jsonify({"multiple_results": res.data, "total": len(res.data)})

    except Exception as e:
        return jsonify({"error": f"ডেটাবেজ ত্রুটি: {str(e)}"}), 500


@app.route("/api/result/roll", methods=["POST"])
def search_by_roll():
    data = request.get_json()
    roll = data.get("roll", "")
    year = data.get("year", "")

    try:
        query = supabase.table("results").select("*").eq("roll", str(roll))
        if year:
            query = query.eq("year", int(year))
        res = query.limit(1).execute()

        if not res.data:
            return jsonify({"error": "রোল নম্বরে কোনো রেজাল্ট পাওয়া যায়নি।"})

        return jsonify(res.data[0])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stats", methods=["GET"])
def stats():
    """ডেটাবেজে কতটা রেজাল্ট আছে দেখায়"""
    try:
        res = supabase.table("results").select("year, exam", count="exact").execute()
        return jsonify({"total": res.count, "message": "সার্ভার চলছে ✅"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "সার্ভার চলছে ✅"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
