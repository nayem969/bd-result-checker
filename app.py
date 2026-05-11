from flask import Flask, request, jsonify
from flask_cors import CORS
import os
import requests as req

app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def supabase_query(params):
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }
    url = f"{SUPABASE_URL}/rest/v1/results"
    r = req.get(url, headers=headers, params=params, timeout=10)
    return r.json()

@app.route("/api/result", methods=["POST"])
def search_by_name():
    data = request.get_json()
    if not data:
        return jsonify({"error": "কোনো ডেটা পাঠানো হয়নি।"}), 400

    name        = data.get("name", "").strip()
    year        = data.get("year", "")
    exam        = data.get("exam", "JSC")
    father_name = data.get("father_name", "").strip()

    if not name:
        return jsonify({"error": "নাম দেওয়া আবশ্যিক।"}), 400

    try:
        params = {
            "select": "*",
            "name":   f"ilike.*{name}*",
            "limit":  "20",
        }
        if year:
            params["year"] = f"eq.{year}"
        if exam:
            params["exam"] = f"ilike.*{exam}*"
        if father_name:
            params["father_name"] = f"ilike.*{father_name}*"

        results = supabase_query(params)

        if not results or (isinstance(results, dict) and "error" in results):
            return jsonify({"error": f"'{name}' নামে কোনো রেজাল্ট পাওয়া যায়নি।"})

        if len(results) == 1:
            return jsonify(results[0])

        return jsonify({"multiple_results": results, "total": len(results)})

    except Exception as e:
        return jsonify({"error": f"সার্ভার ত্রুটি: {str(e)}"}), 500


@app.route("/api/result/roll", methods=["POST"])
def search_by_roll():
    data = request.get_json()
    roll = data.get("roll", "")
    year = data.get("year", "")

    try:
        params = {"select": "*", "roll": f"eq.{roll}", "limit": "1"}
        if year:
            params["year"] = f"eq.{year}"
        results = supabase_query(params)
        if not results:
            return jsonify({"error": "রোল নম্বরে কোনো রেজাল্ট পাওয়া যায়নি।"})
        return jsonify(results[0])
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "message": "সার্ভার চলছে ✅"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
