from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import os



app = Flask(__name__)
app.secret_key = "lifelink_secret_key"

EMAIL_ADDRESS = "lifelinkresq@gmail.com"
EMAIL_PASSWORD = "narl@2026"
# ---------------- DATABASE ----------------
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="tiger",   # change if needed
    database="lifelink"
)
cursor = db.cursor(dictionary=True)

# ---------------- EMAIL CONFIG ----------------

EMAIL_ADDRESS = "lifelinkresq@gmail.com"
EMAIL_PASSWORD = "narl@2005"

def send_payment_email_receipt_email(to_email, user_name, amount, receipt_path):
    msg = MIMEMultipart()
    msg["From"] = EMAIL_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = "LifeLink Payment Receipt"

    body = f"""
Hello {user_name},

Your payment of Rs. {amount} was successful.

Please find the receipt attached.

Thank you for choosing LifeLink 🚑
"""
    msg.attach(MIMEText(body, "plain"))

    # Attach receipt file (TXT)
    with open(receipt_path, "rb") as f:
        attachment = MIMEApplication(f.read(), _subtype="txt")
        attachment.add_header(
            "Content-Disposition",
            "attachment",
            filename=os.path.basename(receipt_path)
        )
        msg.attach(attachment)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        print("Email error:", e)

#----------------- PDF RECEIPT GENERATION ----------------
def generate_payment_receipt(payment_id, user_name, amount):
    file_path = f"receipts/receipt_{payment_id}.pdf"
    os.makedirs("receipts", exist_ok=True)

    c = canvas.Canvas(file_path, pagesize=A4)
    c.setFont("Helvetica", 14)

    c.drawString(200, 800, "LifeLink Payment Receipt")
    c.drawString(50, 750, f"Receipt ID: {payment_id}")
    c.drawString(50, 720, f"User: {user_name}")
    c.drawString(50, 690, f"Amount Paid: ₹{amount}")
    c.drawString(50, 660, "Status: SUCCESS")
    c.drawString(50, 630, "Thank you for using LifeLink")

    c.save()
    return file_path
# ---------------- AUTH ----------------
@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        cursor.execute(
            "SELECT * FROM users WHERE email=%s AND password=%s",
            (email, password)
        )
        user = cursor.fetchone()

        if user:
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session["name"] = user["name"]

            if user["role"] == "admin":
                return redirect(url_for("admin_dashboard"))
            else:
                return redirect(url_for("symptoms"))

        return render_template("shared/message.html", message="Invalid login")

    return render_template("auth/login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------- USER SYMPTOMS ----------------
@app.route("/symptoms")
def symptoms():
    if "user_id" not in session:
        return redirect(url_for("login"))

    return render_template("user/symptoms.html")

# ---------------- USER BOOKING ----------------
@app.route("/booking", methods=["GET", "POST"])
def booking():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        user_id = session["user_id"]

        # Create booking with initial status
        cursor.execute("""
            INSERT INTO bookings (user_id, status, created_at)
            VALUES (%s, %s, %s)
        """, (user_id, "requested", datetime.now()))

        db.commit()
        booking_id = cursor.lastrowid

        # Redirect to payment with booking id
        return redirect("/my-booking")


    return render_template("booking/booking.html")

# ---------------- USER BOOKING TRACKING ----------------
@app.route("/my-booking")
def my_booking():
    if "user_id" not in session:
        return redirect(url_for("login"))

    cursor.execute("""
        SELECT 
            b.id,
            b.status,
            b.created_at,
            a.vehicle_number,
            d.name AS driver_name,
            d.phone AS driver_phone
        FROM bookings b
        LEFT JOIN ambulances a ON b.ambulance_id = a.id
        LEFT JOIN drivers d ON b.driver_id = d.id
        WHERE b.user_id = %s
        ORDER BY b.id DESC
        LIMIT 1
    """, (session["user_id"],))

    booking = cursor.fetchone()

    return render_template(
        "booking/my_booking.html",
        booking=booking
    )


# ---------------- ADMIN GUARD ----------------
def admin_required():
    return "user_id" in session and session.get("role") == "admin"


# ---------------- ADMIN DASHBOARD ----------------
@app.route("/admin/dashboard")
def admin_dashboard():
    if not admin_required():
        return redirect(url_for("login"))

    cursor.execute("SELECT COUNT(*) c FROM users")
    users = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) c FROM drivers")
    drivers = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) c FROM ambulances")
    ambulances = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) c FROM bookings")
    bookings = cursor.fetchone()["c"]

    cursor.execute("SELECT COUNT(*) c FROM payments")
    payments = cursor.fetchone()["c"]

    cursor.execute("SELECT AVG(rating) avg FROM feedback")
    avg_rating = cursor.fetchone()["avg"] or 0

    return render_template(
        "admin/dashboard.html",
        users=users,
        drivers=drivers,
        ambulances=ambulances,
        bookings=bookings,
        payments=payments,
        avg_rating=round(avg_rating, 1)
    )


# ---------------- ADMIN USERS ----------------
@app.route("/admin/users")
def admin_users():
    if not admin_required():
        return redirect(url_for("login"))

    cursor.execute("SELECT id, name, email, role FROM users")
    users = cursor.fetchall()
    return render_template("admin/users.html", users=users)


@app.route("/admin/users/delete/<int:user_id>", methods=["POST"])
def delete_user(user_id):
    if not admin_required():
        return redirect(url_for("login"))

    cursor.execute("DELETE FROM users WHERE id=%s", (user_id,))
    db.commit()
    return redirect(url_for("admin_users"))


# ---------------- ADMIN DRIVERS ----------------
@app.route("/admin/drivers")
def admin_drivers():
    if not admin_required():
        return redirect(url_for("login"))

    cursor.execute("SELECT * FROM drivers")
    drivers = cursor.fetchall()
    return render_template("admin/drivers.html", drivers=drivers)


@app.route("/admin/drivers/add", methods=["POST"])
def add_driver():
    if not admin_required():
        return redirect(url_for("login"))

    name = request.form["name"]
    phone = request.form["phone"]
    license_no = request.form["license_no"]

    cursor.execute(
        "INSERT INTO drivers (name, phone, license_no, status) VALUES (%s,%s,%s,%s)",
        (name, phone, license_no, "available")
    )
    db.commit()
    return redirect(url_for("admin_drivers"))


@app.route("/admin/drivers/status/<int:driver_id>/<status>")
def change_driver_status(driver_id, status):
    if not admin_required():
        return redirect(url_for("login"))

    cursor.execute(
        "UPDATE drivers SET status=%s WHERE id=%s",
        (status, driver_id)
    )
    db.commit()
    return redirect(url_for("admin_drivers"))


@app.route("/admin/drivers/delete/<int:driver_id>", methods=["POST"])
def delete_driver(driver_id):
    if not admin_required():
        return redirect(url_for("login"))

    cursor.execute("DELETE FROM drivers WHERE id=%s", (driver_id,))
    db.commit()
    return redirect(url_for("admin_drivers"))


# ---------------- ADMIN AMBULANCES ----------------
@app.route("/admin/ambulances")
def admin_ambulances():
    if not admin_required():
        return redirect(url_for("login"))

    cursor.execute("SELECT * FROM ambulances")
    ambulances = cursor.fetchall()
    return render_template("admin/ambulances.html", ambulances=ambulances)


@app.route("/admin/ambulances/add", methods=["POST"])
def add_ambulance():
    if not admin_required():
        return redirect(url_for("login"))

    vehicle_number = request.form["vehicle_number"]
    amb_type = request.form["type"]

    cursor.execute(
        "INSERT INTO ambulances (vehicle_number, type, status) VALUES (%s,%s,'available')",
        (vehicle_number, amb_type)
    )
    db.commit()
    return redirect(url_for("admin_ambulances"))


@app.route("/admin/ambulances/status/<int:amb_id>")
def toggle_ambulance_status(amb_id):
    if not admin_required():
        return redirect(url_for("login"))

    cursor.execute(
        "UPDATE ambulances SET status = IF(status='available','on-duty','available') WHERE id=%s",
        (amb_id,)
    )
    db.commit()
    return redirect(url_for("admin_ambulances"))


@app.route("/admin/ambulances/delete/<int:amb_id>")
def delete_ambulance(amb_id):
    if not admin_required():
        return redirect(url_for("login"))

    cursor.execute("DELETE FROM ambulances WHERE id=%s", (amb_id,))
    db.commit()
    return redirect(url_for("admin_ambulances"))
# ---------------- NOTIFICATIONS HELPER ----------------
def create_notification(user_id, message):
    cursor.execute("""
        INSERT INTO notifications (user_id, message, created_at)
        VALUES (%s, %s, %s)
    """, (user_id, message, datetime.now()))
    db.commit()
def send_sms(phone, message):
    # Mock SMS (for project/demo)
    print(f"📱 SMS to {phone}: {message}")

def send_email(to_email, subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = to_email
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()

    except Exception as e:
        print("Email error:", e)
# ---------------- ADMIN BOOKINGS ----------------
@app.route("/admin/bookings")
def admin_bookings():
    if not admin_required():
        return redirect("/login")

    cursor.execute("""
        SELECT 
            b.id AS booking_id,
            u.name AS user_name,
            u.email,
            a.vehicle_number AS ambulance_number,
            b.status
        FROM bookings b
        JOIN users u ON b.user_id = u.id
        LEFT JOIN ambulances a ON b.ambulance_id = a.id
        ORDER BY b.id DESC
    """)
    bookings = cursor.fetchall()

    return render_template("admin/bookings.html", bookings=bookings)

#------------------ BOOKING STATUS UPDATE (WITH RESOURCE ASSIGNMENT) ----------------
@app.route("/admin/bookings/update/<int:booking_id>")
def update_booking_status(booking_id):
    if not admin_required():
        return redirect("/login")

    cursor.execute("""
        SELECT status FROM bookings WHERE id=%s
    """, (booking_id,))
    booking = cursor.fetchone()

    if not booking:
        return redirect("/admin/bookings")

    current_status = booking["status"]

    # STATUS FLOW
    flow = ["requested", "accepted", "on-the-way", "completed"]

    if current_status == "requested":
        # 🚑 Find available ambulance
        cursor.execute("SELECT id FROM ambulances WHERE status='available' LIMIT 1")
        ambulance = cursor.fetchone()

        # 👨‍✈️ Find available driver
        cursor.execute("SELECT id FROM drivers WHERE status='available' LIMIT 1")
        driver = cursor.fetchone()

        if not ambulance or not driver:
            return render_template(
                "shared/message.html",
                type="error",
                heading="No Resources",
                message="No available ambulance or driver at the moment.",
                redirect_url="/admin/bookings"
            )

        # Assign both
        cursor.execute("""
            UPDATE bookings
            SET status='accepted',
                ambulance_id=%s,
                driver_id=%s
            WHERE id=%s
        """, (ambulance["id"], driver["id"], booking_id))

        cursor.execute(
            "UPDATE ambulances SET status='on-duty' WHERE id=%s",
            (ambulance["id"],)
        )

        cursor.execute(
            "UPDATE drivers SET status='busy' WHERE id=%s",
            (driver["id"],)
        )

    elif current_status == "accepted":
        cursor.execute(
            "UPDATE bookings SET status='on-the-way' WHERE id=%s",
            (booking_id,)
        )

    elif current_status == "on-the-way":
        cursor.execute(
            "UPDATE bookings SET status='completed' WHERE id=%s",
            (booking_id,)
        )

        # FREE ambulance + driver
        cursor.execute("""
            SELECT ambulance_id, driver_id FROM bookings WHERE id=%s
        """, (booking_id,))
        ids = cursor.fetchone()

        if ids["ambulance_id"]:
            cursor.execute(
                "UPDATE ambulances SET status='available' WHERE id=%s",
                (ids["ambulance_id"],)
            )

        if ids["driver_id"]:
            cursor.execute(
                "UPDATE drivers SET status='available' WHERE id=%s",
                (ids["driver_id"],)
            )

    db.commit()
    return redirect("/admin/bookings")
@app.route("/admin/bookings/delete/<int:booking_id>")
def delete_booking(booking_id):
    if not admin_required():
        return redirect("/login")

    cursor.execute("DELETE FROM bookings WHERE id=%s", (booking_id,))
    db.commit()
    return redirect("/admin/bookings")

# ---------------- ADMIN NOTIFICATIONS ----------------
@app.route("/admin/notifications")
def admin_notifications():
    if not admin_required():
        return redirect(url_for("login"))

    cursor.execute("""
        SELECT 
            n.id,
            u.name AS user_name,
            n.message,
            n.created_at
        FROM notifications n
        JOIN users u ON n.user_id = u.id
        ORDER BY n.created_at DESC
    """)
    notifications = cursor.fetchall()

    return render_template(
        "admin/notifications.html",
        notifications=notifications
    )

# ---------------- USER NOTIFICATIONS ----------------
@app.route("/notifications")
def user_notifications():
    if "user_id" not in session:
        return redirect("/login")

    cursor.execute("""
        SELECT message, created_at
        FROM notifications
        WHERE user_id=%s
        ORDER BY created_at DESC
    """, (session["user_id"],))
    notifications = cursor.fetchall()

    cursor.execute("""
        UPDATE notifications SET is_read=TRUE WHERE user_id=%s
    """, (session["user_id"],))
    db.commit()

    return render_template(
        "shared/notifications.html",
        notifications=notifications
    )
# ---------------- PAYMENTS ----------------
@app.route("/payment", methods=["GET", "POST"])
def payment():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        amount = request.form["amount"]

        cursor.execute("""
            INSERT INTO payments (user_id, amount, status, created_at)
            VALUES (%s, %s, %s, %s)
        """, (session["user_id"], amount, "SUCCESS", datetime.now()))
        db.commit()

        payment_id = cursor.lastrowid
        session["last_payment_id"] = payment_id   # ⭐ IMPORTANT

        return redirect(url_for("payment_success"))

    return render_template("payment/payment.html")


@app.route("/payment/process", methods=["POST"])
def process_payment():
    if not admin_required():
        return redirect("/login")

    booking_id = request.form["booking_id"]
    amount = request.form["amount"]

    cursor.execute("""
        INSERT INTO payments (user_id, amount, status, created_at)
        SELECT user_id, %s, 'SUCCESS', NOW()
        FROM bookings WHERE id=%s
    """, (amount, booking_id))

    cursor.execute("""
        UPDATE bookings SET status='completed' WHERE id=%s
    """, (booking_id,))

    db.commit()
    return redirect("/payment/success")


@app.route("/payment/success")
def payment_success():
    if "user_id" not in session:
        return redirect(url_for("login"))

    # 1️⃣ Fetch latest payment
    cursor.execute("""
        SELECT p.id, p.amount, p.created_at, u.name, u.email
        FROM payments p
        JOIN users u ON p.user_id = u.id
        WHERE p.user_id=%s
        ORDER BY p.id DESC
        LIMIT 1
    """, (session["user_id"],))
    payment = cursor.fetchone()

    if not payment:
        return redirect("/")

    # 2️⃣ Generate receipt file (TEXT – FREE & SIMPLE)
    receipt_filename = f"receipt_{payment['id']}.txt"
    receipt_path = f"receipts/{receipt_filename}"

    with open(receipt_path, "w", encoding="utf-8") as f:
        f.write(f"""
LifeLink Payment Receipt
------------------------

Receipt ID : {payment['id']}
Name       : {payment['name']}
Email      : {payment['email']}
Amount     : Rs. {payment['amount']}
Date       : {payment['created_at']}

Thank you for choosing LifeLink.
We wish you good health.

– LifeLink Team
""")


    # 3️⃣ Send email with receipt
    send_payment_email_receipt_email(
        payment["email"],
        payment["name"],
        payment["amount"],
        receipt_path
    )


    # 4️⃣ In-app notification
    create_notification(
        session["user_id"],
        f"Payment of ₹{payment['amount']} successful. Receipt emailed."
    )

    return render_template("payment/payment_success.html")

@app.route("/payment/<int:booking_id>")
def booking_payment(booking_id):
    if not admin_required():
        return redirect("/login")

    amount = 750  # fixed demo amount

    return render_template(
        "payment/payment.html",
        booking_id=booking_id,
        amount=amount
    )

# ---------------- ADMIN PAYMENTS ----------------
@app.route("/admin/payments")
def admin_payments():
    if not admin_required():
        return redirect("/login")

    cursor.execute("""
        SELECT 
            p.id,
            u.name AS user_name,
            p.amount,
            p.status,
            p.created_at
        FROM payments p
        JOIN users u ON p.user_id = u.id
        ORDER BY p.created_at DESC
    """)
    payments = cursor.fetchall()

    return render_template("admin/payments.html", payments=payments)
@app.route("/admin/payments/delete/<int:payment_id>", methods=["POST"])
def delete_payment(payment_id):
    if not admin_required():
        return redirect("/login")

    cursor.execute("DELETE FROM payments WHERE id=%s", (payment_id,))
    db.commit()

    return redirect("/admin/payments")

@app.route("/admin/payments/clear", methods=["POST"])
def clear_payments():
    if not admin_required():
        return redirect("/login")

    cursor.execute("DELETE FROM payments")
    db.commit()
    return redirect("/admin/payments")
# ---------------- FEEDBACK ----------------
@app.route("/admin/feedback")
def admin_feedback():
    if not admin_required():
        return redirect(url_for("login"))

    cursor.execute("""
        SELECT 
            f.id,
            u.name AS user_name,
            f.rating,
            f.message,
            f.created_at
        FROM feedback f
        JOIN users u ON f.user_id = u.id
        ORDER BY f.created_at DESC
    """)
    feedbacks = cursor.fetchall()

    return render_template(
        "admin/feedback.html",
        feedbacks=feedbacks
    )

@app.route("/feedback/submit", methods=["GET", "POST"])
def submit_feedback():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        cursor.execute(
            "INSERT INTO feedback (user_id, rating, message, created_at) VALUES (%s,%s,%s,%s)",
            (session["user_id"], request.form["rating"], request.form["message"], datetime.now())
        )
        db.commit()
        return render_template("shared/message.html", message="Feedback submitted")

    return render_template("feedback/submit_feedback.html")


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
