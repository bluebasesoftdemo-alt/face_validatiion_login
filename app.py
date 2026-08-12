"""
app.py  (Project 1 -- Login / Verification)

This project now OWNS the login experience: the candidate opens THIS
project first, takes their photo, and submits it here. On success,
this project redirects the candidate's browser to Project 2 (the
monitoring/exam app), carrying their verified identity in the URL.

Routes:
  /            -- the login page (Take Photo -> Retake -> Submit)
  /register    -- registration page (testing convenience)
  /start       -- verifies the submitted photo; on success returns
                  a redirect_url pointing at Project 2's /exam page
"""

from flask import Flask, render_template, request, jsonify
from face_verification import FaceVerificationService

app = Flask(__name__)

# Where Project 2 (the monitoring/exam app) lives
EXAM_APP_URL = "http://127.0.0.1:5000"

print("Loading FaceVerificationService...")
face_service = FaceVerificationService()
print("Ready.")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/register")
def register_page():
    return render_template("register.html")


@app.route("/register", methods=["POST"])
def register_candidate_route():
    payload = request.get_json(silent=True) or {}
    name = payload.get("candidate_name", "")
    image_data = payload.get("image")

    if not image_data:
        return jsonify({"success": False, "reason": "No photo was captured."}), 400

    result = face_service.register(image_data, name)
    return jsonify(result)


@app.route("/start", methods=["POST"])
def start():
    payload = request.get_json(silent=True) or {}
    image_data = payload.get("image")

    if not image_data:
        return jsonify({"verified": False, "reason": "No photo was submitted."}), 400

    result = face_service.verify(image_data)

    if not result["verified"]:
        return jsonify(result)

    # Build the URL to send the candidate's browser to -- Project 2's
    # /exam page, carrying their verified identity as query parameters.
    redirect_url = (
        f"{EXAM_APP_URL}/exam"
        f"?candidate_id={result['candidate_id']}"
        f"&candidate_name={result['candidate_name']}"
    )

    return jsonify({
        "verified": True,
        "candidate_id": result["candidate_id"],
        "candidate_name": result["candidate_name"],
        "redirect_url": redirect_url,
    })


if __name__ == "__main__":
    app.run(debug=True, port=5001, use_reloader=False, threaded=True)