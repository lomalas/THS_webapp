import base64
import json
import os
import sqlalchemy

def process_visit_ticket(event, context):
    message = base64.b64decode(event['data']).decode('utf-8')
    data = json.loads(message)

    # Connect to Cloud SQL from the function
    db_user = os.environ["DB_USER"]
    db_pass = os.environ["DB_PASS"]
    db_name = os.environ["DB_NAME"]
    instance = os.environ["INSTANCE_CONNECTION_NAME"]

    engine = sqlalchemy.create_engine(
        f"postgresql+pg8000://{db_user}:{db_pass}@/{db_name}",
        creator=lambda: pg8000.connect(
            user=db_user, password=db_pass,
            database=db_name,
            unix_sock=f"/cloudsql/{instance}/.s.PGSQL.5432"
        )
    )

    with engine.connect() as conn:
        conn.execute(sqlalchemy.text("""
            INSERT INTO visit_ticket
              (patient_id, reason_for_visit, pain_level, symptom_duration,
               condition_category, body_location, condition_type,
               allergies, medications, chronic_conditions,
               emergency_contact, therapist_notes, consent_signed)
            VALUES
              (:patient_id, :reason_for_visit, :pain_level, :symptom_duration,
               :condition_category, :body_location, :condition_type,
               :allergies, :medications, :chronic_conditions,
               :emergency_contact, :therapist_notes, :consent_signed)
        """), data)
        conn.commit()

    if data["pain_level"] >= 8:
        print(f"HIGH PAIN ALERT — patient {data['patient_id']}")