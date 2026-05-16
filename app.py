from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector as connector
import config
from werkzeug.utils import secure_filename
from ultralytics import YOLO
from dotenv import load_dotenv
import bcrypt
import os
import cv2

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Load YOLO model
model = YOLO("models/best.pt")


# ================= DATABASE CONNECTION =================
def connect_to_db():
    try:
        return connector.connect(**config.mysql_credentials)
    except connector.Error as e:
        print("Database error:", e)
        return None


# ================= HOME =================
@app.route('/')
def home():
    return render_template('index.html')


# ================= SIGNUP =================
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':

        name = request.form.get('full_name')
        email = request.form.get('email')
        password = request.form.get('password')
        contact_number = request.form.get('phone')
        vehicle_number = request.form.get('vehicle_id')
        brand = request.form.get('car_brand')
        model_name = request.form.get('car_model')

        if not name or not email or not password:
            flash("All fields are required!", "error")
            return redirect(url_for('signup'))

        hashed_password = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

        connection = connect_to_db()
        if not connection:
            flash("Database connection failed!", "error")
            return redirect(url_for('signup'))

        cursor = connection.cursor()

        try:
            cursor.execute("""
                INSERT INTO users (name, email, password, contact_number)
                VALUES (%s, %s, %s, %s)
            """, (name, email, hashed_password, contact_number))

            user_id = cursor.lastrowid

            cursor.execute("""
                INSERT INTO vehicles (user_id, vehicle_number, brand, model)
                VALUES (%s, %s, %s, %s)
            """, (user_id, vehicle_number, brand, model_name))

            connection.commit()
            flash("Signup successful!", "success")
            return redirect(url_for('login'))

        except connector.Error as e:
            connection.rollback()
            print("Signup error:", e)
            # ✅ FIX: Properly differentiate duplicate entry errors
            if e.errno == 1062:
                if 'email' in str(e).lower():
                    flash("Email already exists! Please use a different email.", "error")
                elif 'vehicle_number' in str(e).lower():
                    flash("Vehicle number already registered! Please check your Vehicle ID.", "error")
                else:
                    flash("Duplicate entry! Please check your details.", "error")
            elif e.errno == 1406:
                flash("Phone number too long! Please enter max 10 digits.", "error")
            elif e.errno == 1048:
                flash("All fields are required! Please fill in everything.", "error")
            else:
                flash(f"Registration failed! Error code: {e.errno}", "error")

        finally:
            cursor.close()
            connection.close()

    return render_template('signup.html')


# ================= LOGIN =================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':

        email = request.form.get('email')
        password = request.form.get('password')

        connection = connect_to_db()
        if not connection:
            flash("Database connection failed!", "error")
            return redirect(url_for('login'))

        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE email = %s", (email,))
        user = cursor.fetchone()

        if user and bcrypt.checkpw(password.encode(), user['password'].encode()):
            session['user_id'] = user['user_id']
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid email or password", "error")

        cursor.close()
        connection.close()

    return render_template('login.html')


# ================= LOGOUT =================
@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))


# ================= DASHBOARD =================
@app.route('/dashboard', methods=['GET', 'POST'])
def dashboard():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':

        file = request.files.get('image')
        if not file:
            flash("No file selected!", "error")
            return redirect(url_for('dashboard'))

        filename = secure_filename(file.filename)
        image_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(image_path)

        # ✅ FIX: Check DB connection before using it
        connection = connect_to_db()
        if not connection:
            flash("Database connection failed!", "error")
            return redirect(url_for('dashboard'))

        cursor = connection.cursor(dictionary=True)

        cursor.execute("""
            SELECT vehicle_id, brand, model
            FROM vehicles
            WHERE user_id = %s
        """, (session['user_id'],))

        vehicle = cursor.fetchone()

        if not vehicle:
            flash("Vehicle not found!", "error")
            return redirect(url_for('profile'))

        cursor.execute("""
            INSERT INTO damage_images (vehicle_id, image_path)
            VALUES (%s, %s)
        """, (vehicle['vehicle_id'], filename))

        image_id = cursor.lastrowid

        results = model(image_path)

        detected_filename = "detected_" + filename
        detected_path = os.path.join(UPLOAD_FOLDER, detected_filename)
        results[0].save(detected_path, conf=False)

        detected_objects = results[0].boxes
        class_names = ['Bonnet', 'Bumper', 'Dickey', 'Door', 'Fender', 'Light', 'Windshield']

        img = cv2.imread(image_path)
        image_area = img.shape[0] * img.shape[1]

        estimates = {}
        total_estimate = 0

        for box in detected_objects:

            class_id = int(box.cls.item())
            part_name = class_names[class_id]

            x1, y1, x2, y2 = box.xyxy[0].tolist()
            box_area = (x2 - x1) * (y2 - y1)
            damage_percentage = round((box_area / image_area) * 100, 2)

            cursor.execute("""
                SELECT part_id, price
                FROM car_parts
                WHERE brand = %s AND model = %s AND part_name = %s
            """, (vehicle['brand'], vehicle['model'], part_name))

            part_data = cursor.fetchone()

            if part_data:
                total_cost = part_data['price']
                total_estimate += total_cost

                cursor.execute("""
                    INSERT INTO damage_reports (image_id, part_id, damage_count, total_cost)
                    VALUES (%s, %s, %s, %s)
                """, (image_id, part_data['part_id'], 1, total_cost))

                # Accumulate if same part detected multiple times
                if part_name in estimates:
                    estimates[part_name]["count"] += 1
                    estimates[part_name]["total"] += total_cost
                    estimates[part_name]["damage_percent"] = round(
                        estimates[part_name]["damage_percent"] + damage_percentage, 2
                    )
                else:
                    estimates[part_name] = {
                        "count": 1,
                        "price_per_part": part_data['price'],
                        "total": total_cost,
                        "damage_percent": damage_percentage
                    }

        connection.commit()
        cursor.close()
        connection.close()

        return render_template(
            'estimate.html',
            original_image=filename,
            detected_image="uploads/" + detected_filename,
            estimates=estimates,
            total_estimate=total_estimate
        )

    return render_template('dashboard.html')


# ================= PROFILE =================
@app.route('/profile', methods=['GET', 'POST'])
def profile():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    connection = connect_to_db()
    if not connection:
        flash("Database connection failed!", "error")
        return redirect(url_for('login'))

    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT * FROM users WHERE user_id=%s", (session['user_id'],))
    user = cursor.fetchone()

    cursor.execute("SELECT * FROM vehicles WHERE user_id=%s", (session['user_id'],))
    vehicle = cursor.fetchone()

    if request.method == 'POST':

        name = request.form.get('name')
        contact = request.form.get('contact')
        vehicle_number = request.form.get('vehicle_number')
        brand = request.form.get('brand')
        model_name = request.form.get('model')

        cursor.execute("""
            UPDATE users
            SET name=%s, contact_number=%s
            WHERE user_id=%s
        """, (name, contact, session['user_id']))

        cursor.execute("""
            UPDATE vehicles
            SET vehicle_number=%s, brand=%s, model=%s
            WHERE user_id=%s
        """, (vehicle_number, brand, model_name, session['user_id']))

        connection.commit()
        # ✅ FIX: Close connection before redirecting (was leaking before)
        cursor.close()
        connection.close()
        flash("Profile Updated Successfully!", "success")
        return redirect(url_for('profile'))

    cursor.close()
    connection.close()

    return render_template('profile.html', user=user, vehicle=vehicle)


# ================= CHANGE PASSWORD =================
@app.route('/change_password', methods=['POST'])
def change_password():

    if 'user_id' not in session:
        return redirect(url_for('login'))

    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')

    connection = connect_to_db()
    if not connection:
        flash("Database connection failed!", "error")
        return redirect(url_for('profile'))

    cursor = connection.cursor(dictionary=True)

    cursor.execute("SELECT password FROM users WHERE user_id=%s", (session['user_id'],))
    user = cursor.fetchone()

    if user and bcrypt.checkpw(current_password.encode(), user['password'].encode()):
        hashed_password = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()

        cursor.execute("""
            UPDATE users
            SET password=%s
            WHERE user_id=%s
        """, (hashed_password, session['user_id']))

        connection.commit()
        flash("Password Changed Successfully!", "success")
    else:
        flash("Current password is incorrect!", "error")

    cursor.close()
    connection.close()

    return redirect(url_for('profile'))


if __name__ == '__main__':
    app.run(debug=True)