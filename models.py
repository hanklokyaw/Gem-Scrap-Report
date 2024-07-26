from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Departments(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    dept_name = db.Column(db.String(20), nullable=False)


class Reporters(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reporter_name = db.Column(db.String(30), nullable=False)


class Items(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(30), nullable=False)
    alt_sku = db.Column(db.String(30), nullable=True)
    description = db.Column(db.String(50), nullable=True)


class Reports(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    reporter_id = db.Column(db.Integer, db.ForeignKey('reporters.id'))
    dept_id = db.Column(db.Integer, db.ForeignKey('departments.id'))
    # Define relationship to Reporters model
    reporter = db.relationship('Reporters', backref='reports', lazy=True)
    department = db.relationship('Departments', backref='reports', lazy=True)
    report_details = db.relationship('ReportDetails', backref='report', lazy=True)

class ReportDetails(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    report_id = db.Column(db.Integer, db.ForeignKey('reports.id'))
    item_id = db.Column(db.Integer, db.ForeignKey('items.id'))
    quantity = db.Column(db.Integer, nullable=False)
    note = db.Column(db.String(10), nullable=False)
    # Define relationship to Items model
    item = db.relationship('Items', backref='report_details', lazy=True)

