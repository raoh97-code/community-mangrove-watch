from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
import uuid

app = Flask(__name__)
CORS(app, supports_credentials=True)   # allow cookies for login
app.secret_key = "supersecretkey"      # needed for sessions

# ---------------- DB Setup ----------------
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///site.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

# ---------------- Models ----------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # "NGO" or "Volunteer"

class Complaint(db.Model):
    id = db.Column(db.String(20), primary_key=True, default=lambda: "CM-" + uuid.uuid4().hex[:8].upper())
    type = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(200), nullable=False)
    status = db.Column(db.String(20), default="Pending")
    assigned_to = db.Column(db.String(120), nullable=True)

class Donation(db.Model):
    id = db.Column(db.String(20), primary_key=True, default=lambda: "DN-" + uuid.uuid4().hex[:8].upper())
    amount = db.Column(db.Float, nullable=False)
    method = db.Column(db.String(50), nullable=False)


# ---------------- Registration ----------------
@app.route("/register", methods=["POST"])
def register():
    data = request.json
    if User.query.filter_by(email=data["email"]).first():
        return jsonify({"error": "Email already registered"}), 400

    user = User(
        name=data["name"],
        email=data["email"],
        password=data["password"],  # ⚠️ plain text for now, can hash later
        role=data["role"]
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "Registered successfully!"})


# ---------------- Login ----------------
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    user = User.query.filter_by(email=data["email"], password=data["password"]).first()
    if not user:
        return jsonify({"error": "Invalid email or password"}), 401

    # Save user session
    session["user_id"] = user.id
    session["role"] = user.role
    session["email"] = user.email

    return jsonify({
        "message": "Login successful",
        "user": {"name": user.name, "email": user.email, "role": user.role}
    })


# ---------------- Check Session ----------------
@app.route("/me", methods=["GET"])
def me():
    if "user_id" not in session:
        return jsonify({"logged_in": False}), 401
    
    return jsonify({
        "logged_in": True,
        "user": {
            "id": session["user_id"],
            "email": session["email"],
            "role": session["role"]
        }
    })


# ---------------- Logout ----------------
@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"})


# ---------------- Complaints ----------------
@app.route("/complaints", methods=["POST"])
def add_complaint():
    data = request.json
    complaint = Complaint(
        type=data['type'],
        description=data['description'],
        location=data['location']
    )
    db.session.add(complaint)
    db.session.commit()
    return jsonify({
        "message": "Complaint submitted!",
        "complaint_id": complaint.id,
        "status": complaint.status
    })


@app.route("/complaints/<cid>", methods=["GET"])
def get_complaint(cid):
    complaint = Complaint.query.get(cid)
    if not complaint:
        return jsonify({"error": "Not found"}), 404
    return jsonify({
        "id": complaint.id,
        "type": complaint.type,
        "description": complaint.description,
        "location": complaint.location,
        "status": complaint.status,
        "assigned_to": complaint.assigned_to
    })


@app.route("/complaints/<cid>/accept", methods=["POST"])
def accept_complaint(cid):
    if "role" not in session or session["role"] != "NGO":
        return jsonify({"error": "Only NGOs can accept complaints"}), 403

    complaint = Complaint.query.get(cid)
    if not complaint:
        return jsonify({"error": "Complaint not found"}), 404
    if complaint.status != "Pending":
        return jsonify({"error": "Already taken"}), 400

    complaint.status = "In Action"
    complaint.assigned_to = session["email"]
    db.session.commit()
    return jsonify({"message": "Complaint accepted", "complaint_id": complaint.id})


@app.route("/complaints/<cid>/complete", methods=["POST"])
def complete_complaint(cid):
    if "role" not in session or session["role"] != "NGO":
        return jsonify({"error": "Only NGOs can complete complaints"}), 403

    complaint = Complaint.query.get(cid)
    if not complaint:
        return jsonify({"error": "Complaint not found"}), 404

    complaint.status = "Completed"
    db.session.commit()
    return jsonify({"message": "Complaint marked completed", "complaint_id": complaint.id})


# ---------------- Donations ----------------
@app.route("/donate", methods=["POST"])
def donate():
    data = request.get_json()
    amount = data.get("amount")
    method = data.get("method")

    if not amount or not method:
        return jsonify({"error": "Missing donation data"}), 400

    donation = Donation(amount=amount, method=method)
    db.session.add(donation)
    db.session.commit()

    return jsonify({"message": "Donation successful", "donation_id": donation.id})


# ---------------- Run ----------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
