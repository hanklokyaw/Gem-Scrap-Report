from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from datetime import date, datetime
from models import db, Departments, Reporters, Items, Reports, ReportDetails
from werkzeug.security import check_password_hash, generate_password_hash
from config import Config
from decimal import Decimal
from sqlalchemy import func
import logging
import csv
import io
import sqlite3


app = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)
app.config.from_object(Config)
db.init_app(app)

# Dummy password hash for example purposes
PASSWORD_HASH = generate_password_hash('Hak@5624586822')  # Replace with your hashed password

# @app.before_first_request
# def create_tables():
#     db.create_all()

@app.route('/')
def index():
    reporters = Reporters.query.all()
    departments = Departments.query.all()
    items = Items.query.all()
    today_date = date.today().strftime('%Y-%m-%d')
    return render_template('index.html', reporters=reporters, departments=departments, items=items, today_date=today_date)

#
# @app.route('/items')
# def list_items():
#     items = Item.query.all()  # Assuming you're using SQLAlchemy
#     return render_template('items.html', items=items)
#
#
#
# @app.route('/add_vendor', methods=['GET', 'POST'])
# def add_vendor():
#     if request.method == 'POST':
#         vendor_name = request.form.get('vendor_name')
#         address = request.form.get('address')
#         phone = request.form.get('phone')
#         city = request.form.get('city')
#         contact_person = request.form.get('contact_person')
#         email = request.form.get('email')
#         web = request.form.get('web')
#         comments = request.form.get('comments')
#
#         # Validate and save the vendor (add to database)
#         vendor = Vendor(name=vendor_name, address=address, phone=phone, city=city, email=email, web=web, comments=comments)
#         db.session.add(vendor)
#         db.session.commit()
#         flash('Vendor added successfully', 'success')
#         return redirect(url_for('index'))  # Redirect to main page or wherever appropriate
#
#     return render_template('add_vendor.html')
#
#
@app.route('/add_reporter', methods=['GET', 'POST'])
def add_reporter():
    if request.method == 'POST':
        reporter_name = request.form.get('reporter_name')
        requester = Reporters(reporter_name=reporter_name)
        db.session.add(requester)
        db.session.commit()
        flash('Reporter added successfully', 'success')
        return redirect(url_for('index'))  # Redirect to main page or wherever appropriate

    return render_template('add_reporter.html')
#
# @app.route('/add_item', methods=['GET', 'POST'])
# def add_item():
#     if request.method == 'POST':
#         item_name = request.form.get('item_name')
#         alt_sku = request.form.get('alt_sku')
#         description = request.form.get('description')
#         purchase_price = request.form.get('purchase_price')
#         unit = request.form.get('unit')
#         on_hand = request.form.get('on_hand')
#         inventory_date = request.form.get('inventory_date')
#         url = request.form.get('url')
#         # Validate and save the item (add to database)
#         item = Item(item_name=item_name, alt_sku = alt_sku, description=description, purchase_price=purchase_price, unit=unit, on_hand=on_hand, inventory_date=inventory_date, url=url)
#         db.session.add(item)
#         db.session.commit()
#         flash('Item added successfully', 'success')
#         return redirect(url_for('index'))  # Redirect to main page or wherever appropriate
#
#     return render_template('add_item.html')
#
@app.route('/list_reports', methods=['GET'])
def list_reports():
    # Get sorting parameters from the request
    sort_by = request.args.get('sort_by', 'date')  # Default to 'date'
    order = request.args.get('order', 'desc')  # Default to 'desc'

    # Define mapping for sorting columns
    sort_columns = {
        'report_number': Reports.id,
        'date': Reports.date,
        'reporter': Reporters.reporter_name,  # Adjust if needed
        'department': Departments.dept_name,  # Adjust if needed
        'total_quantity': db.func.sum(ReportDetails.quantity)
    }

    sort_column = sort_columns.get(sort_by, Reports.date)  # Default to 'date'

    # Query to fetch report details and aggregate information with sorting
    query = db.session.query(
        Reports,
        db.func.count(ReportDetails.id).label('num_items'),
        db.func.sum(ReportDetails.quantity).label('total_quantity')
    ).outerjoin(ReportDetails, Reports.id == ReportDetails.report_id
    ).outerjoin(Reporters, Reports.reporter_id == Reporters.id
    ).outerjoin(Departments, Reports.dept_id == Departments.id
    ).group_by(Reports.id
    )

    # Apply sorting
    query = query.order_by(sort_column.asc() if order == 'asc' else sort_column.desc())

    reports = query.all()

    # Ensure total_quantity is not None
    reports_aggregated = [
        (report, num_items, round(float(total_quantity or 0), 2))
        for report, num_items, total_quantity in reports
    ]

    return render_template('list_reports.html', reports=reports_aggregated, sort_by=sort_by, order=order)



@app.route('/get_items')
def get_items():
    items = Items.query.all()
    items_data = [{
        'id': item.id,
        'item_name': item.item_name,
        'alt_sku': item.alt_sku,
        'description': item.description
    } for item in items]
    return jsonify({'items': items_data})


from sqlalchemy.sql import text


@app.route('/submit', methods=['POST'])
def submit():
    report_date_str = request.form.get('report_date')
    try:
        report_date = datetime.strptime(report_date_str, '%Y-%m-%d').date()
    except ValueError:
        report_date = datetime.strptime(report_date_str, '%m/%d/%Y').date()
    reporter_id = request.form.get('reporter')
    department_id = request.form.get('department')

    # Create the report
    report = Reports(date=report_date, reporter_id=reporter_id, dept_id=department_id)
    db.session.add(report)
    db.session.commit()

    items = request.form.getlist('item_ids')
    quantities = request.form.getlist('quantity')
    notes = request.form.getlist('note')

    # Initialize the list to store IDs of the newly created report_details
    report_details_ids = []

    # Add ReportDetails entries and collect their IDs
    for i in range(len(items)):
        item_id = items[i]
        quantity = int(quantities[i])
        note = notes[i]

        # Fetch item details from the database
        item = Items.query.get(item_id)
        if not item:
            continue  # Handle case where item is not found

        # Create and add ReportDetails
        report_detail = ReportDetails(report_id=report.id, item_id=item_id, quantity=quantity, note=note)
        db.session.add(report_detail)
        db.session.commit()  # Commit to generate ID for each report_detail

        # Collect the newly created report_detail IDs
        report_details_ids.append(report_detail.id)

    # Execute a raw SQL query to insert data into netsuite_upload
    for report_detail_id in report_details_ids:
        sql = text('INSERT INTO netsuite_upload (report_details_id, netsuite_update) VALUES (:report_details_id, :netsuite_update)')
        db.session.execute(
            sql,
            {'report_details_id': report_detail_id, 'netsuite_update': 0}
        )

    db.session.commit()
    return redirect(url_for('review', report_id=report.id))


@app.route('/view_report_details/<int:report_id>', methods=['GET'])
def view_report_details(report_id):
    # Fetch Report and its details
    report = Reports.query.get_or_404(report_id)
    details = ReportDetails.query.filter_by(report_id=report_id).all()

    # Calculate total_amount if needed
    total_quantity = sum(detail.quantity for detail in details)  # Example calculation, adjust as necessary

    return render_template('report_details.html', report=report, details=details, total_quantity=total_quantity)


@app.route('/review/<int:report_id>')
def review(report_id):
    # Fetch PO and its details
    report = Reports.query.get(report_id)
    details = ReportDetails.query.filter_by(report_id=report_id).all()

    return render_template('review.html', report=report, details=details)


@app.route('/edit/<int:report_id>', methods=['GET', 'POST'])
def edit(report_id):
    report = Reports.query.get(report_id)
    if not report:
        flash('Report not found')
        return redirect(url_for('index'))  # or redirect to a valid page

    if request.method == 'POST':
        # Parse the date with the custom format
        try:
            report.date = datetime.strptime(request.form.get('report_date'), '%Y-%m-%d').date()
        except ValueError:
            flash("Invalid date format. Please use MM/DD/YYYY.")
            return redirect(request.url)

        # Ensure these IDs are correctly handled and valid
        report.reporter_id = request.form.get('reporter')
        report.dept_id = request.form.get('department')

        # Delete existing ReportDetails
        db.session.query(ReportDetails).filter(ReportDetails.report_id == report.id).delete()

        # Add updated ReportDetails
        items = request.form.getlist('item[]')
        quantities = request.form.getlist('quantity[]')
        notes = request.form.getlist('note[]')
        for item_id, quantity_str, note in zip(items, quantities, notes):
            try:
                quantity = int(quantity_str)
            except ValueError:
                continue  # Skip invalid quantity values

            item = Items.query.get(item_id)
            if not item:
                continue

            report_detail = ReportDetails(report_id=report.id, item_id=item_id, quantity=quantity, note=note)
            db.session.add(report_detail)

        db.session.commit()
        return redirect(url_for('review', report_id=report.id))

    # Handle GET request to render the edit page
    reporters = Reporters.query.all()
    departments = Departments.query.all()
    items = Items.query.all()
    return render_template('edit.html',
                           report=report,
                           reporters=reporters,
                           departments=departments,
                           items=items)




@app.route('/download', methods=['GET', 'POST'])
def download():
    if request.method == 'POST':
        password = request.form.get('password')

        # Check password hash
        if not check_password_hash(PASSWORD_HASH, password):
            return "Invalid password", 403

        # SQL query to fetch data
        query = text("""
        SELECT details."report_id" AS "Report ID",
               reports."date" AS "Date",
               items."item_name" AS "Item",
               items."alt_sku" AS "Old SKU",
               items."description" AS "Description",
               departments."dept_name" AS "Department",
               details."quantity" AS "Quantity",
               details."note" AS "Note",
               netsuite_upload."netsuite_update" AS "Netsuite Adj. File Downloaded"
        FROM report_details AS details
        LEFT JOIN reports
        ON reports."id" = details."report_id"
        LEFT JOIN items
        ON details."item_id" = items."id"
        LEFT JOIN departments
        ON reports."dept_id" = departments."id"
        LEFT JOIN netsuite_upload
        ON details."id" = netsuite_upload."report_details_id"
        WHERE netsuite_upload."netsuite_update" = 0;
        """)

        # Execute query and fetch results
        with db.session.connection() as conn:
            result = conn.execute(query)
            columns = result.keys()
            rows = result.fetchall()

            # Create CSV in-memory
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(columns)  # Write header
            writer.writerows(rows)    # Write data
            output.seek(0)

            # Update netsuite_upload table
            update_query = text("""
            UPDATE netsuite_upload
            SET netsuite_update = 1
            WHERE netsuite_update = 0
            """)
            conn.execute(update_query)
            db.session.commit()

        # Send CSV file as download
        return send_file(io.BytesIO(output.getvalue().encode()), download_name='report_details.csv', as_attachment=True)

    return render_template('download.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5010, debug=True)
