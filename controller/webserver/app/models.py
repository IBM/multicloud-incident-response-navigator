from app import db
import datetime

class Edge(db.Model):
	id = db.Column(db.Integer, primary_key=True)
	start_uid = db.Column(db.String(128), nullable=False) # format: <cluster_name>,uid (because uids unique to cluster)
	end_uid = db.Column(db.String(128), nullable = False)
	relation = db.Column(db.String(128), nullable = False)
	last_updated = db.Column(db.DateTime(timezone=True), default = datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

class Resource(db.Model):
	uid = db.Column(db.String(512), unique=True, nullable = False, primary_key=True)
	created_at = db.Column(db.DateTime(timezone=True))	# when k8s created the resource
	last_updated = db.Column(db.DateTime(timezone=True), default = datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)	# when the row was last updated
	rtype = db.Column(db.String(128), nullable = False)
	name = db.Column(db.String(256), nullable = False)
	cluster = db.Column(db.String(128), nullable = False)
	namespace = db.Column(db.String(128))
	application = db.Column(db.String(128))
	app_path = db.Column(db.String(512))
	cluster_path = db.Column(db.String(512))
	sev_measure = db.Column(db.Integer)		# for anomaly mode
	sev_reason = db.Column(db.String(128))	# for anomaly mode
	info = db.Column(db.String(100000))	# the remaning json info about the resource goes here