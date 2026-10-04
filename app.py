
import os
import uuid
from dotenv import load_dotenv
import boto3
from botocore.exceptions import ClientError
from werkzeug.utils import secure_filename
from flask import (
    Flask, flash, redirect, render_template,
    request, url_for
)
from flask_sqlalchemy import SQLAlchemy

load_dotenv()

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv(
    "SECRET_KEY", "local-development-only"
)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL", "sqlite:///app.db"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB

db = SQLAlchemy(app)

S3_BUCKET = os.getenv(
    "S3_BUCKET", "piyush-cloud-platform-105508555730"
)
AWS_REGION = os.getenv("AWS_REGION", "ap-south-1")

# On EC2, boto3 automatically uses the attached IAM role.
s3 = boto3.client("s3", region_name=AWS_REGION)

ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "txt", "csv"}

class Record(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(500), nullable=False, default="")
    created_at = db.Column(db.DateTime, server_default=db.func.now())

@app.route("/")
def index():
    records = Record.query.order_by(Record.created_at.desc()).all()
    return render_template("index.html", records=records)

@app.route("/add", methods=["POST"])
def add_record():
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()

    if not title:
        flash("Please enter a title.", "error")
        return redirect(url_for("index"))

    if len(title) > 120 or len(description) > 500:
        flash("Please keep the title under 120 and description under 500 characters.", "error")
        return redirect(url_for("index"))

    record = Record(title=title, description=description)
    db.session.add(record)
    db.session.commit()
    flash("Record added successfully.", "success")
    return redirect(url_for("index"))

@app.route("/delete/<int:record_id>", methods=["POST"])
def delete_record(record_id):
    record = db.get_or_404(Record, record_id)
    db.session.delete(record)
    db.session.commit()
    flash("Record deleted.", "success")
    return redirect(url_for("index"))

@app.route("/upload", methods=["POST"])
def upload_file():
    uploaded_file = request.files.get("file")

    if not uploaded_file or not uploaded_file.filename:
        flash("Please select a file.", "error")
        return redirect(url_for("index"))

    original_name = secure_filename(uploaded_file.filename)
    if not original_name or "." not in original_name:
        flash("Invalid filename.", "error")
        return redirect(url_for("index"))

    extension = original_name.rsplit(".", 1)[1].lower()
    if extension not in ALLOWED_EXTENSIONS:
        flash("File type not allowed.", "error")
        return redirect(url_for("index"))

    object_key = f"uploads/{uuid.uuid4().hex}_{original_name}"

    try:
        s3.upload_fileobj(
            uploaded_file,
            S3_BUCKET,
            object_key,
            ExtraArgs={
                "ContentType": uploaded_file.mimetype or "application/octet-stream"
            }
        )
        flash("File uploaded to S3 successfully.", "success")
    except ClientError:
        app.logger.exception("S3 upload failed")
        flash("S3 upload failed. Please check the server configuration.", "error")

    return redirect(url_for("index"))

@app.route("/health")
def health():
    return {"status": "healthy"}, 200

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
