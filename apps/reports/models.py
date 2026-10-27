from apps import db
from icecream import ic



# Define ScanResults Model — Time-series metrics only.
# Display fields (bio_text, profile_picture, public_profile_name, external_url)
# live on SocialAccount and are accessed via the relationship to avoid storage bloat.
class ScanResults(db.Model):
    __tablename__ = "scanresults"
    id = db.Column(db.Integer, primary_key=True)
    socialaccount_id = db.Column(db.Integer, db.ForeignKey("socialaccounts.id"), nullable=False, index=True)
    socialaccount = db.relationship("SocialAccount", back_populates="scan_results")
    followers = db.Column(db.Integer)
    likes = db.Column(db.Integer)
    posts = db.Column(db.Integer)
    creation_date = db.Column(db.Date, nullable=True, default=db.func.current_date())
    creation_time = db.Column(db.Time, nullable=True, default=db.func.current_time())
    time_taken = db.Column(db.String(20))



class ScanLog(db.Model):
    __tablename__ = "scanlog"
    id = db.Column(db.Integer, primary_key=True)
    success_count = db.Column(db.JSON)
    failure_count = db.Column(db.JSON)
    failures = db.Column(db.JSON)
    creation_date = db.Column(db.Date, nullable=True, default=db.func.current_date())
    creation_time = db.Column(db.Time, nullable=True, default=db.func.current_time())
    time_taken = db.Column(db.String(20))
