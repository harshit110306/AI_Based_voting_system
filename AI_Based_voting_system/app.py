from flask import Flask, render_template, request, redirect, url_for, flash, session,  jsonify,Response
import os
import mysql.connector
import re
from werkzeug.utils import secure_filename
import cv2
import face_recognition
import numpy as np
from PIL import Image
import io


app = Flask(__name__)

app.secret_key = 'a658914e47696c55b51090d5d0e395798559fa0d181fff9fe8be5281cb21718d'
UPLOAD_FOLDER = os.path.join('static', 'uploads', 'party_logos')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Define folder path
FACE_UPLOAD_FOLDER = os.path.join('static', 'uploads', 'face_data')

# Create the folder if it doesn't exist
if not os.path.exists(FACE_UPLOAD_FOLDER):
    os.makedirs(FACE_UPLOAD_FOLDER)

# Configure Flask
app.config['FACE_UPLOAD_FOLDER'] = FACE_UPLOAD_FOLDER

# Allowed file extensions for face images
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}


# MYSQL data base connection
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Aditya@2005",
        database="e_vote"
    )
#=====================================home page====================================
@app.route('/')
def home():
    return render_template('home.html')

#====================================User Authentication ===========================

#====================================User regstation ================================

@app.route('/regstation', methods=['GET', 'POST'])
def regstation():
    if request.method == 'POST':
        # Get form data
        username = request.form.get('username')
        mobile = request.form.get('mobile')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        branch = request.form.get('branch')
        gender = request.form.get('gender')

        # ✅ Validate all fields
        if not all([username, mobile, password, confirm_password, branch, gender]):
            flash("All fields are required!", "danger")
            return redirect(url_for('regstation'))

        # ✅ Validate mobile number (Indian format: starts 6–9, 10 digits)
        if not re.match(r'^[6-9]\d{9}$', mobile):
            flash("Enter a valid 10-digit Indian mobile number!", "danger")
            return redirect(url_for('regstation'))

        # ✅ Check password match
        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('regstation'))

        # ✅ Password strength check
        if len(password) < 8 or not re.search(r'[A-Z]', password) or not re.search(r'\d', password) or not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
            flash("Password must be 8+ chars, include uppercase, number & special char!", "warning")
            return redirect(url_for('regstation'))

        

        # ✅ Connect DB
        db = get_db_connection()
        cursor = db.cursor(dictionary=True)

        # ✅ Check if username already exists
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            flash("Username already exists!", "danger")
            cursor.close()
            db.close()
            return redirect(url_for('regstation'))

        # ✅ Insert into database
        cursor.execute("""
            INSERT INTO users (username, mobile_no, password, branch, gender)
            VALUES (%s, %s, %s, %s, %s)
        """, (username, mobile, password, branch, gender))
        db.commit()

        cursor.close()
        db.close()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for('login'))

    # GET request → show registration page
    return render_template('reg.html')


     

#=====================================User Login=======================================

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        captcha_input = request.form.get('captcha-input')
        captcha_value = request.form.get('captcha-value')

        # ✅ CAPTCHA validation
        if captcha_input != captcha_value:
            flash("CAPTCHA verification failed!", "danger")
            return redirect(url_for('login'))

        if not username or not password:
            flash("Please enter username and password!", "danger")
            return redirect(url_for('login'))

        # ✅ Detect user type based on username
        if re.fullmatch(r'\d+', username):  # Only digits
            user_type = "Admin"
        elif re.fullmatch(r'[A-Za-z]+', username):  # Only letters
            user_type = "Candidate"
        elif re.fullmatch(r'[A-Za-z0-9]+', username):  # Alphanumeric
            user_type = "User"
        else:
            flash("Invalid username format!", "danger")
            return redirect(url_for('login'))

        try:
            db = get_db_connection()
            cursor = db.cursor(dictionary=True)

            # ✅ Match username and password from DB
            cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
            user = cursor.fetchone()

            if user:
                session['username'] = username
                session['user_type'] = user_type

                flash(f"Welcome {username}! You are logged in as {user_type}.", "success")

                # ✅ Redirect based on type
                if user_type == 'Admin':
                    session['user_name'] = username
                    return redirect(url_for('admin'))
                
                elif user_type == 'Candidate':
                    session['user_name'] = username
                    return redirect(url_for('candi_home'))
                elif user_type == 'User':
                    session['user_name'] = username
                    return redirect(url_for('user_home'))
            else:
                flash("Invalid username or password!", "danger")
                return redirect(url_for('login'))

        except mysql.connector.Error as err:
            flash(f"Database error: {err}", "danger")

        finally:
            cursor.close()
            db.close()

    return render_template('login.html')

#============================Forget password=======================================

@app.route('/forget_password')
def forget():
    return render_template('forget_pass.html')
#============================ADMIN DASHBORD========================================


#===========================Admin home =============================================
@app.route('/admin')
def admin():
    if 'user_name' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    user_name = session['user_name']

    # ✅ Initialize all variables
    total_users = total_candidates = total_mp_votes = total_mla_votes = total_mp_candidates = total_mla_candidates = 0

    try:
        # ✅ Total users with alphanumeric usernames
        cursor.execute("""
            SELECT COUNT(*) AS total_users 
            FROM users 
            WHERE username REGEXP '[a-zA-Z]' AND username REGEXP '[0-9]'
        """)
        total_users = cursor.fetchone()['total_users']

        # ✅ Total MP candidates
        cursor.execute("SELECT COUNT(*) AS total_mp_candidates FROM candidate_reg WHERE candidate_type = 'MP'")
        total_mp_candidates = cursor.fetchone()['total_mp_candidates']

        # ✅ Total MLA candidates
        cursor.execute("SELECT COUNT(*) AS total_mla_candidates FROM candidate_reg WHERE candidate_type = 'MLA'")
        total_mla_candidates = cursor.fetchone()['total_mla_candidates']

        # ✅ Total candidates (all)
        cursor.execute("SELECT COUNT(*) AS total_candidates FROM candidate_reg")
        total_candidates = cursor.fetchone()['total_candidates']

        # ✅ Total MP votes
        cursor.execute("SELECT COUNT(*) AS total_mp_votes FROM vote_cast WHERE candidate_type = 'MP'")
        total_mp_votes = cursor.fetchone()['total_mp_votes']

        # ✅ Total MLA votes
        cursor.execute("SELECT COUNT(*) AS total_mla_votes FROM vote_cast WHERE candidate_type = 'MLA'")
        total_mla_votes = cursor.fetchone()['total_mla_votes']

    except mysql.connector.Error as err:
        flash(f"Database error: {err}", "danger")

    finally:
        cursor.close()
        conn.close()

    # ✅ Pass all values to template
    return render_template(
        'adminhome.html',
        username=user_name,
        total_users=total_users,
        total_candidates=total_candidates,
        total_mp_votes=total_mp_votes,
        total_mla_votes=total_mla_votes,
        total_mp_candidates=total_mp_candidates,
        total_mla_candidates=total_mla_candidates
    )


#============= All candidate information for Admin ==================================

@app.route('/candidate_display')
def candi_display():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ✅ Delete logic
    delete_name = request.args.get('delete')
    if delete_name:
        try:
            cursor.execute("DELETE FROM candidate_reg WHERE name = %s", (delete_name,))
            conn.commit()
            flash('Candidate record deleted successfully.', 'success')
            return redirect(url_for('candi_display'))
        except mysql.connector.Error as e:
            flash(f'Error deleting candidate: {e}', 'danger')

    # ✅ Fetch all candidates
    cursor.execute("SELECT * FROM candidate_reg")
    candidates = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('candi_display.html', candidates=candidates)

#==================================== candidate information edit ========================================
@app.route('/update', methods=['GET', 'POST'])
def update():
    # Get candidate name and branch from query string (like ?update=John&branch=CSE)
    candidate_name = request.args.get('update')
    branch = request.args.get('branch')

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Fetch candidate by name and branch
    cursor.execute("SELECT * FROM candidate_reg WHERE name=%s AND branch=%s", (candidate_name, branch))
    candidate = cursor.fetchone()

    if not candidate:
        flash("Candidate not found for the selected branch.", "danger")
        return redirect(url_for('candi_display'))

    # Handle form submission
    if request.method == "POST":
        name = request.form['name']
        age = request.form['age']
        dob = request.form['dob']
        gender = request.form['gender']
        mobile = request.form['mobile']
        branch = request.form['branch']
        email = request.form['email']
        parti_name = request.form['parti_name']
        candidate_type = request.form['candidate_type']

        # Update query
        cursor.execute("""
            UPDATE candidate_reg
            SET name=%s, age=%s, dob=%s, gender=%s, mobile=%s,
                branch=%s, email=%s, parti_name=%s, candidate_type=%s
            WHERE name=%s AND branch=%s
        """, (name, age, dob, gender, mobile, branch, email, parti_name, candidate_type, candidate_name, candidate['branch']))

        conn.commit()
        cursor.close()
        conn.close()

        flash("Candidate details updated successfully!", "success")
        return redirect(url_for('candi_display'))

    cursor.close()
    conn.close()
    return render_template('update.html', candidate=candidate)

#================e-Voting result who win ============================================
@app.route('/result')
def result():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    query = """
        WITH vote_counts AS (
            SELECT 
                candidate_id,
                COUNT(*) AS total_votes
            FROM vote_cast
            GROUP BY candidate_id
        ),
        candidate_with_votes AS (
            SELECT 
                cr.id,
                cr.name,
                cr.branch,
                cr.parti_name,
                cr.party_logo,
                cr.candidate_type,
                COALESCE(vc.total_votes, 0) AS total_votes
            FROM candidate_reg cr
            LEFT JOIN vote_counts vc ON cr.id = vc.candidate_id
        ),
        branch_leaders AS (
            SELECT 
                branch,
                candidate_type,
                MAX(total_votes) AS max_votes
            FROM candidate_with_votes
            GROUP BY branch, candidate_type
        ),
        equal_counts AS (
            SELECT 
                cw.branch,
                cw.candidate_type,
                cw.total_votes,
                COUNT(*) AS cnt
            FROM candidate_with_votes cw
            GROUP BY cw.branch, cw.candidate_type, cw.total_votes
        )
        SELECT 
            cw.id,
            cw.name,
            cw.branch,
            cw.parti_name,
            cw.party_logo,
            cw.candidate_type,
            cw.total_votes,
            CASE
                WHEN cw.total_votes = 0 THEN ''
                WHEN cw.total_votes = bl.max_votes AND ec.cnt > 1 THEN 'Equal Vote'
                WHEN cw.total_votes = bl.max_votes THEN 'Win'
                ELSE ''
            END AS status
        FROM candidate_with_votes cw
        JOIN branch_leaders bl 
            ON cw.branch = bl.branch AND cw.candidate_type = bl.candidate_type
        LEFT JOIN equal_counts ec 
            ON cw.branch = ec.branch AND cw.candidate_type = ec.candidate_type AND cw.total_votes = ec.total_votes
        ORDER BY cw.branch, cw.candidate_type, cw.total_votes DESC;
    """

    cursor.execute(query)
    results = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template('result.html', candidates=results)


#============================candidate dashbord =======================================

#============================candidate Home page=========================================
@app.route('/candihome')
def candi_home():
    # ✅ Check if user is logged in
    if 'user_name' not in session:
        return redirect(url_for('login'))

    user_name = session['user_name']

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # ✅ Check if candidate is registered in candidate_reg table
    cursor.execute("SELECT * FROM candidate_reg WHERE name = %s", (user_name,))
    user_details = cursor.fetchone()

    # ✅ If candidate exists
    if user_details:
        reg_status = "YES"

        # ✅ Fetch candidate's total vote count (if votes table exists)
        try:
            cursor.execute(
                "SELECT COUNT(*) AS total_votes FROM vote_cast WHERE candidate_id = %s",
                (user_details['id'],)
            )
            result = cursor.fetchone()
            vote_count = result['total_votes'] if result else 0
        except Exception as e:
            print("Vote count fetch error:", e)
            vote_count = 0

    # ❌ If candidate not found
    else:
        reg_status = "NO"
        vote_count = 0
        user_details = {
            'id': '----',
            'name': user_name,
            'dob': '----',
            'age': '----',
            'gender': '----',
            'emailid': '----',
            'mobileno': '----',
            'parti_name': '----',
            'candidate_type': '----'
        }

    cursor.close()
    conn.close()

    # ✅ Render candidate home page
    return render_template(
        'candihome.html',
        user=user_details,
        vote_count=vote_count,
        reg_status=reg_status
    )


#=============================Candidate nomination for vote==============================

@app.route('/candreg', methods=['GET', 'POST'])
def candi_reg():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT username, gender, mobile_no as mobileno, branch as city FROM users WHERE username = %s", (session['user_name'],))
    user_data = cursor.fetchone()
    
    if request.method == 'POST':
        name = request.form['name']
        age = request.form['age']
        dob = request.form['dob']
        gender = request.form['gender']
        mobile = request.form['mobile']
        branch = request.form['branch']
        email = request.form['email']
        parti_name = request.form['parti_name']
        candidate_type = request.form['candidate_type']

        party_logo_file = request.files['party_logo']
        party_logo_filename = secure_filename(party_logo_file.filename)
        party_logo_path = os.path.join(app.config['UPLOAD_FOLDER'], party_logo_filename)

        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])

        party_logo_file.save(party_logo_path)
        candidate_id = f"{mobile}{age}{dob}"

        try:
            insert_query = """
                INSERT INTO candidate_reg 
                (id, name, dob, age, gender, mobile, email, branch, parti_name, candidate_type, party_logo)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_query, (
                candidate_id, name, dob, age, gender, mobile, email, branch, parti_name, candidate_type, party_logo_filename
            ))
            conn.commit()
            return render_template('cload.html')
        except mysql.connector.Error as err:
            return f"Database Error: {err}"
        finally:
            cursor.close()
            conn.close()

    return render_template('candi_reg.html', user=user_data)

@app.route('/candiloding')
def candiloding():
    return render_template('cload.html')




#==========================================Voter section ===========================================

#========================================== voter home =============================================
@app.route('/userhome')
def user_home():
    # ✅ Check login session
    if 'user_name' not in session:
        return redirect(url_for('login'))

    user_name = session['user_name']
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)

    # Default values
    city = gender = mobileno = "Unknown"
    mp_vote_status = mla_vote_status = "❌"

    # ✅ Fetch user details
    cursor.execute("""
        SELECT branch AS city, gender, mobile_no AS mobileno 
        FROM users 
        WHERE username = %s
    """, (user_name,))
    
    user_data = cursor.fetchone()
    if user_data:
        city = user_data.get('city', 'Unknown')
        gender = user_data.get('gender', 'Unknown')
        mobileno = user_data.get('mobileno', 'Unknown')

    # ✅ Check voting status
    cursor.execute("SELECT candidate_type FROM vote_cast WHERE user_name = %s", (user_name,))
    vote_data = cursor.fetchall()

    for row in vote_data:
        candidate_type = row['candidate_type'].upper()
        if candidate_type == 'MP':
            mp_vote_status = "✅"
        elif candidate_type == 'MLA':
            mla_vote_status = "✅"

    # ✅ ✅ Check if photo exists in face table (CASE-INSENSITIVE, CORRECT FIX)
    cursor.execute("""
        SELECT id 
        FROM face 
        WHERE LOWER(username) = LOWER(%s)
        ORDER BY uploaded_at DESC 
        LIMIT 1
    """, (user_name,))

    face_record = cursor.fetchone()

    has_photo = True if face_record else False

    # ✅ Debug (remove after testing)
    print("Logged User:", user_name)
    print("Has Photo:", has_photo)

    # ✅ Close DB
    cursor.close()
    conn.close()

    # ✅ Render template
    return render_template(
        'userhome.html',
        username=user_name,
        city=city,
        gender=gender,
        mobileno=mobileno,
        mp_vote_status=mp_vote_status,
        mla_vote_status=mla_vote_status,
        has_photo=has_photo
    )


#======================================== vote cast ============================================

@app.route('/vote_cast', methods=['GET', 'POST'])
def vote_cast():
    if 'user_name' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    user_name = session['user_name']

    # Get all candidate types (for dropdown)
    cursor.execute("SELECT DISTINCT candidate_type FROM candidate_reg")
    candidate_types = cursor.fetchall()

    # Get user's branch
    cursor.execute("SELECT branch FROM users WHERE username = %s", (user_name,))
    user_branch_row = cursor.fetchone()
    user_branch = user_branch_row['branch'] if user_branch_row else ''

    # ✅ Handle vote submission
    if request.method == 'POST' and 'vote' in request.form:
        print("---- Vote Cast Form Data ----")
        print(request.form)

        candidate_id = request.form.get('candidate_id')
        candidate_name = request.form.get('candidate_name')
        parti_name = request.form.get('parti_name')
        candidate_type = request.form.get('candidate_type')

        # Check if user already voted
        cursor.execute("""
            SELECT * FROM vote_cast 
            WHERE user_name = %s AND candidate_type = %s
        """, (user_name, candidate_type))
        already_voted = cursor.fetchone()

        if already_voted:
            flash("⚠️ You have already cast your vote for this type of candidate.", "warning")
        else:
            try:
                cursor.execute("""
                    INSERT INTO vote_cast (candidate_id, candidate_name, parti_name, candidate_type, user_name)
                    VALUES (%s, %s, %s, %s, %s)
                """, (candidate_id, candidate_name, parti_name, candidate_type, user_name))
                conn.commit()
                flash("Vote cast successfully!", "success")
                print("Vote inserted successfully!")
                return redirect(url_for('loading'))
            except mysql.connector.Error as err:
                conn.rollback()
                print("MYSQL ERROR:", err)
                flash(f"MySQL Error: {err}", "danger")

    # ✅ Display candidates (based on dropdown selection)
    selected_branch = request.args.get('branch')
    selected_type = request.args.get('candidate_type')
    candidates = []

    if selected_branch and selected_type:
        cursor.execute("""
            SELECT id, name, parti_name, candidate_type, party_logo 
            FROM candidate_reg 
            WHERE branch = %s AND candidate_type = %s
        """, (selected_branch, selected_type))
        candidates = cursor.fetchall()

    cursor.close()
    conn.close()

    return render_template(
        'vote_cast.html',
        candidate_types=candidate_types,
        user_branch=user_branch,
        candidates=candidates
    )

@app.route('/loading')
def loading():
    return render_template('v_loder.html')


#=========================face authentication ===================================================

# ===================== FACE UPLOAD BACKEND =====================
@app.route('/userimg', methods=['GET', 'POST'])
def userimg():
    if 'user_name' not in session:
        return redirect(url_for('login'))

    user_name = session['user_name']

    if request.method == 'POST':
        if 'photo' not in request.files:
            flash("No file selected!", "danger")
            return redirect(url_for('userimg'))

        photo = request.files['photo']
        if photo.filename == '':
            flash("Invalid file selected!", "danger")
            return redirect(url_for('userimg'))

        filename = secure_filename(photo.filename)
        if not os.path.exists(app.config['FACE_UPLOAD_FOLDER']):
            os.makedirs(app.config['FACE_UPLOAD_FOLDER'])

        photo_path = os.path.join(app.config['FACE_UPLOAD_FOLDER'], filename)

        # Save as grayscale
        img = cv2.imdecode(np.frombuffer(photo.read(), np.uint8), cv2.IMREAD_GRAYSCALE)
        cv2.imwrite(photo_path, img)

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO face (username, image_path, uploaded_at) VALUES (%s, %s, NOW())",
            (user_name, photo_path)
        )
        conn.commit()
        cursor.close()
        conn.close()

        flash("Photo uploaded successfully in grayscale!", "success")
        return redirect(url_for('userimg'))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT image_path FROM face WHERE username=%s ORDER BY uploaded_at DESC LIMIT 1",
        (user_name,)
    )
    row = cursor.fetchone()
    cursor.close()
    conn.close()
    uploaded_photo = row[0] if row else None

    return render_template('user_img.html', uploaded_photo=uploaded_photo, user_name=user_name)

# Allowed file check
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS
# =================== Face Scan Verification ====================

@app.route('/face_scan', methods=['GET', 'POST'])
def face_scan():
    if 'user_name' not in session:
        return redirect(url_for('login'))

    user_name = session['user_name']

    if request.method == 'GET':
        return render_template('face_scan.html', user_name=user_name)

    try:
        if 'frame' not in request.files:
            return jsonify({"message": "No image received"})

        frame_file = request.files['frame']
        file_bytes = np.frombuffer(frame_file.read(), dtype=np.uint8)
        frame_gray = cv2.imdecode(file_bytes, cv2.IMREAD_GRAYSCALE)

        if frame_gray is None:
            return jsonify({"message": "Could not decode webcam image"})

        # --- Fetch stored grayscale image ---
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT image_path FROM face
            WHERE LOWER(username) = LOWER(%s)
            ORDER BY uploaded_at DESC LIMIT 1
        """, (user_name,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            return jsonify({"message": "No stored face image found"})

        stored_path = row['image_path']
        if not os.path.exists(stored_path):
            return jsonify({"message": "Stored image file not found"})

        stored_gray = cv2.imread(stored_path, cv2.IMREAD_GRAYSCALE)
        if stored_gray is None:
            return jsonify({"message": "Could not read stored face image"})

        # Resize both
        target_size = (200, 200)
        frame_gray = cv2.resize(frame_gray, target_size)
        stored_gray = cv2.resize(stored_gray, target_size)

        # Train recognizer
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train([stored_gray], np.array([0]))

        label, confidence = recognizer.predict(frame_gray)
        similarity = max(0, min(100, 100 * (1 - confidence / 200)))

        # Determine match status and next step
        if similarity >= 80:
            msg = f"Face Verified "
            allow_vote = True  # Full match, allow voting
        elif similarity >= 40:
            msg = f"Face Verified "
            allow_vote = True  # Partial match, allow voting
        else:
            msg = f"Face Not Matched "
            allow_vote = False  # Not allowed

        # Return JSON including flag for frontend
        return jsonify({"message": msg, "similarity": similarity, "allow_vote": allow_vote})

    except Exception as e:
        return jsonify({"message": f"Server error: {str(e)}"})

if __name__ == '__main__':
    app.run(debug=True)