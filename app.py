import os
from datetime import datetime

from flask import Flask, request, render_template_string, redirect
from flask_sqlalchemy import SQLAlchemy
from functools import wraps
from google.cloud import pubsub_v1
import json

import firebase_admin
from firebase_admin import auth, credentials

# ======================================================
# FIREBASE INIT
# ======================================================

cred = credentials.ApplicationDefault()
firebase_admin.initialize_app(cred)

# ======================================================
# AUTH
# ======================================================

def verify_token(request):
    token = request.cookies.get("token")

    if not token:
        return None

    try:
        return auth.verify_id_token(token)
    except Exception as e:
        print(e)
        return None


def require_auth(f):

    @wraps(f)
    def wrapper(*args, **kwargs):

        user = verify_token(request)

        if not user:
            return redirect("/login")

        request.user = user

        therapist = Therapist.query.filter_by(
            firebase_uid=user["uid"]
        ).first()

        if not therapist and request.path != "/setup":
            return redirect("/setup")

        request.therapist = therapist

        return f(*args, **kwargs)

    return wrapper




# ======================================================
# APP INIT
# ======================================================

app = Flask(__name__)

publisher = pubsub_v1.PublisherClient()

PROJECT_ID = "cloud-final-495319"

TOPIC_PATH = publisher.topic_path(
    PROJECT_ID,
    "visit-ticket-events"
)

# ======================================================
# DB CONFIG
# ======================================================

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")
INSTANCE_CONNECTION_NAME = os.getenv("INSTANCE_CONNECTION_NAME")

DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASS}"
    f"@/{DB_NAME}"
    f"?host=/cloudsql/{INSTANCE_CONNECTION_NAME}"
)

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ======================================================
# MODELS
# ======================================================

class Therapist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    firebase_uid = db.Column(db.String(128), unique=True)


class Patient(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    therapist_id = db.Column(db.Integer, db.ForeignKey("therapist.id"))
    name = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ======================================================
# CLEAN VISIT TICKET (FIXED)
# ======================================================

class VisitTicket(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    # ownership
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"))

    # visit info
    reason_for_visit = db.Column(db.String(300))
    pain_level = db.Column(db.Integer)
    symptom_duration = db.Column(db.String(100))

    # condition classification
    condition_category = db.Column(db.String(100))  # muscular/skeletal/etc
    body_location = db.Column(db.String(100))       # arm/leg/neck
    condition_type = db.Column(db.String(100))      # pain/swelling/etc

    # medical snapshot
    allergies = db.Column(db.String(300))
    medications = db.Column(db.String(300))
    chronic_conditions = db.Column(db.String(300))
    emergency_contact = db.Column(db.String(200))

    # therapist notes
    therapist_notes = db.Column(db.Text)

    # consent
    consent_signed = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ======================================================
# CREATE TABLES
# ======================================================

with app.app_context():
    db.create_all()


# ======================================================
# HELPERS
# ======================================================

def get_therapist(uid):
    return Therapist.query.filter_by(firebase_uid=uid).first()


# ======================================================
# HOME
# ======================================================

@app.route("/")
@require_auth
def home():

    therapist = get_therapist(request.user["uid"])

    patients = Patient.query.filter_by(
        therapist_id=therapist.id
    ).all() if therapist else []

    return render_template_string("""
    <h1>Therapist Dashboard</h1>

    <form method="POST" action="/create_patient">
        <input name="name" placeholder="Patient Name">
        <button>Create</button>
    </form>

    <h2>Your Patients</h2>

    <ul>
    {% for p in patients %}
        <li><a href="/patient/{{p.id}}">{{p.name}}</a></li>
    {% endfor %}
    </ul>

    <a href="/logout">Logout</a>
    """, patients=patients)

# ======================================================
# SIGN IN
# ======================================================

@app.route("/setup", methods=["GET", "POST"])
@require_auth
def setup():

    user = request.user

    therapist = Therapist.query.filter_by(
        firebase_uid=user["uid"]
    ).first()

    # already exists → go home
    if therapist:
        return redirect("/")

    if request.method == "POST":

        therapist = Therapist(
            firebase_uid=user["uid"],
            name=request.form["name"]
        )

        db.session.add(therapist)
        db.session.commit()

        return redirect("/")

    return """
    <h1>Therapist Setup</h1>
    <form method="POST">
        <input name="name" placeholder="Your Name" required>
        <button>Create Account</button>
    </form>
    """ 

# ======================================================
# LOGIN / LOGOUT
# ======================================================

@app.route("/login")
def login_page():
    return render_template_string(open("login.html").read())


@app.route("/logout")
def logout():
    res = redirect("/login")
    res.set_cookie("token", "", expires=0)
    return res


# ======================================================
# CREATE PATIENT
# ======================================================

@app.route("/create_patient", methods=["POST"])
@require_auth
def create_patient():

    therapist = get_therapist(request.user["uid"])

    if not therapist:
        therapist = Therapist(
            name="Therapist",
            firebase_uid=request.user["uid"]
        )
        db.session.add(therapist)
        db.session.commit()

    patient = Patient(
        therapist_id=therapist.id,
        name=request.form["name"]
    )

    db.session.add(patient)
    db.session.commit()

    return redirect("/")


# ======================================================
# PATIENT PAGE
# ======================================================

@app.route("/patient/<int:patient_id>")
@require_auth
def patient_page(patient_id):

    therapist = get_therapist(request.user["uid"])

    patient = Patient.query.get(patient_id)

    if not patient or patient.therapist_id != therapist.id:
        return "Forbidden", 403

    tickets = VisitTicket.query.filter_by(
        patient_id=patient_id
    ).order_by(VisitTicket.created_at.desc()).all()

    return render_template_string("""
    <h1>{{ patient.name }}</h1>

    <h2>Create Visit Ticket</h2>

    <form method="POST" action="/create_ticket/{{ patient.id }}">

        <input name="reason_for_visit" placeholder="Reason" required><br><br>

        <input type="number" name="pain_level" min="0" max="10" placeholder="Pain Level"><br><br>

        <input name="symptom_duration" placeholder="Duration"><br><br>

        <select name="condition_category">
            <option>Muscular</option>
            <option>Skeletal</option>
            <option>Cartilage</option>
            <option>Neurological</option>
        </select><br><br>

        <select name="body_location">
            <option>Neck</option>
            <option>Shoulder</option>
            <option>Arm</option>
            <option>Back</option>
            <option>Hip</option>
            <option>Knee</option>
            <option>Leg</option>
        </select><br><br>

        <select name="condition_type">
            <option>Pain</option>
            <option>Swelling</option>
            <option>Fracture</option>
            <option>Tear</option>
        </select><br><br>

        <input name="allergies" placeholder="Allergies"><br><br>
        <input name="medications" placeholder="Medications"><br><br>
        <input name="chronic_conditions" placeholder="Chronic Conditions"><br><br>
        <input name="emergency_contact" placeholder="Emergency Contact"><br><br>

        <textarea name="therapist_notes" placeholder="Notes"></textarea><br><br>

        <label>
            Consent
            <input type="checkbox" name="consent_signed">
        </label><br><br>

        <button>Create Ticket</button>
    </form>

    <hr>

    <h2>History</h2>

    <h2>Visit History</h2>

    {% for ticket in tickets %}

        <div style="
            border:1px solid gray;
            padding:15px;
            margin-bottom:20px;
        ">

            <h3>
                {{ ticket.created_at }}
            </h3>

            <p>
                <b>Reason:</b>
                {{ ticket.reason_for_visit }}
            </p>

            <p>
                <b>Pain Level:</b>
                {{ ticket.pain_level }}
            </p>

            <p>
                <b>Duration:</b>
                {{ ticket.symptom_duration }}
            </p>

            <p>
                <b>Category:</b>
                {{ ticket.condition_category }}
            </p>

            <p>
                <b>Location:</b>
                {{ ticket.body_location }}
            </p>

            <p>
                <b>Condition:</b>
                {{ ticket.condition_type }}
            </p>

            <p>
                <b>Allergies:</b>
                {{ ticket.allergies }}
            </p>

            <p>
                <b>Medications:</b>
                {{ ticket.medications }}
            </p>

            <p>
                <b>Conditions:</b>
                {{ ticket.chronic_conditions }}
            </p>

            <p>
                <b>Emergency Contact:</b>
                {{ ticket.emergency_contact }}
            </p>

            <p>
                <b>Notes:</b>
                {{ ticket.therapist_notes }}
            </p>

        </div>

    {% endfor %}

    <a href="/">Back</a>
    """, patient=patient, tickets=tickets)


# ======================================================
# CREATE TICKET
# ======================================================

@app.route("/create_ticket/<int:patient_id>", methods=["POST"])
@require_auth
def create_ticket(patient_id):

    therapist = get_therapist(request.user["uid"])
    patient = Patient.query.get(patient_id)

    if not patient or patient.therapist_id != therapist.id:
        return "Forbidden", 403

    ticket = VisitTicket(
        patient_id=patient_id,
        reason_for_visit=request.form.get("reason_for_visit"),
        pain_level=int(request.form.get("pain_level") or 0),
        symptom_duration=request.form.get("symptom_duration"),
        condition_category=request.form.get("condition_category"),
        body_location=request.form.get("body_location"),
        condition_type=request.form.get("condition_type"),
        allergies=request.form.get("allergies"),
        medications=request.form.get("medications"),
        chronic_conditions=request.form.get("chronic_conditions"),
        emergency_contact=request.form.get("emergency_contact"),
        therapist_notes=request.form.get("therapist_notes"),
        consent_signed=("consent_signed" in request.form)
    )

    db.session.add(ticket)
    db.session.commit()

    event_data = {
        "patient_id": patient_id,
        "reason_for_visit": request.form.get("reason_for_visit"),
        "pain_level": int(request.form.get("pain_level") or 0),
        "symptom_duration": request.form.get("symptom_duration"),
        "condition_category": request.form.get("condition_category"),
        "body_location": request.form.get("body_location"),
        "condition_type": request.form.get("condition_type"),
        "allergies": request.form.get("allergies"),
        "medications": request.form.get("medications"),
        "chronic_conditions": request.form.get("chronic_conditions"),
        "emergency_contact": request.form.get("emergency_contact"),
        "therapist_notes": request.form.get("therapist_notes"),
        "consent_signed": ("consent_signed" in request.form),
    }

    publisher.publish(TOPIC_PATH, json.dumps(event_data).encode("utf-8"))

    # Redirect immediately — don't wait for DB write
    return redirect(f"/patient/{patient_id}")


# ======================================================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)