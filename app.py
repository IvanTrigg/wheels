from flask import Flask, render_template, redirect, url_for, request, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user,logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from flask import abort

app = Flask(__name__)

app.config['SECRET_KEY'] = 'supersecret'
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///database.db"
app.config["PROPAGATE_EXCEPTIONS"] = True

# --- DB Setup --- 

db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# --- Datebase Models ---

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='member')
    approved = db.Column(db.Boolean, default=False)
    is_senior = db.Column(db.Boolean, default=False)
    chapter = db.Column(db.String(50))

class Ride(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200))
    location = db.Column(db.String(200))
    ride_date = db.Column(db.String(100))
    description = db.Column(db.Text)
    created_by = db.Column(db.Integer)
    meeting_points = db.relationship(
        'MeetingPoint',
        backref='ride',
        cascade="all, delete-orphan"
    )
    participants = db.relationship(
        'RideParticipant',
        backref='ride',
        cascade='all, delete-orphan'
    )

class RideParticipant(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey('ride.id'), nullable=False)
    user_id = db.Column(db.Integer)
    meeting_point = db.Column(db.String(200))

class MeetingPoint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    ride_id = db.Column(db.Integer, db.ForeignKey('ride.id'), nullable=False)
    location_name = db.Column(db.String(200))

# ---Login Loader---

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

def senior_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "senior":
            abort(403)
        return f(*args, **kwargs)
    return decorated_function


# --- Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contacts')
def contacts():
    return render_template('contacts.html')

@app.route('/rides')
def rides():
    
    rides = Ride.query.order_by(Ride.id.desc()).all()
    return render_template('rides.html', rides=rides)

# --- Register ---

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        chapter  = request.form.get("chapter")

        if not username or not password:
            flash("Please fill in all fields.")
            return redirect(url_for("register"))

        hashed_password = generate_password_hash(password)

        new_user = User(
            username=username,
            password=hashed_password,
            role="member",
            approved=False,
            chapter=chapter
        )

        db.session.add(new_user)
        db.session.commit()

        flash("Account created. Waiting for senior approval.")
        return redirect(url_for("login"))

    return render_template("register.html")

# --- Login ---

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            if not user.approved:
                flash('Account pending approval')
                return redirect(url_for('login'))
            
            login_user(user)
            return redirect(url_for('index'))
        
        flash('Login, Failed')

    return render_template('login.html')

# --- Logout ---

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- Create First Admin ---

@app.route('/create-first-admin')
def create_first_admin():
    senior_exists = User.query.filter_by(role='senior').first()

    if senior_exists:
        return 'Admin already exists!'
    
    username = 'admin'
    password = generate_password_hash('admin')

    admin = User(
        username=username,
        password=password,
        role='senior',
        approved=True
    )

    db.session.add(admin)
    db.session.commit()

    return 'Frist admin created. Username: admin | Password: wheels2026'

# --- Members Approval ---

@app.route('/approve-members')
@login_required
@senior_required
def approve_members():
    pending_users = User.query.filter_by(approved=False).all()
    return render_template("approve_members.html", users=pending_users) 

@app.route("/approve/<int:user_id>")
@login_required
@senior_required
def approve_user(user_id):
    user = User.query.get_or_404(user_id)
    user.approved = True
    db.session.commit()
    return redirect(url_for("approve_members"))

# --- Create Rides Routes

@app.route('/create-ride', methods=['GET', 'POST'])
@login_required
@senior_required
def create_ride():
    if request.method == 'POST':
        title = request.form.get('title')
        location = request.form.get('location')
        ride_date = request.form.get('ride_date')
        description = request.form.get('description')

        new_ride = Ride(
            title=title,
            location=location,
            ride_date=ride_date,
            description=description,
            created_by=current_user.id
        )

        db.session.add(new_ride)
        db.session.commit()

        return redirect(url_for("manage_meeting_points", ride_id=new_ride.id))
    
    return render_template('create_ride.html')

# Meeting ponts

@app.route("/ride/<int:ride_id>/meeting-points", methods=["GET", "POST"])
@login_required
@senior_required
def manage_meeting_points(ride_id):
    ride = Ride.query.get_or_404(ride_id)

    if request.method == 'POST':
        location_name = request.form.get('location_name')

        if location_name:
            new_point = MeetingPoint(
                ride_id=ride.id,
                location_name=location_name
            )

            db.session.add(new_point)
            db.session.commit()

    meeting_points = MeetingPoint.query.filter_by(ride_id=ride.id).all()

    return render_template(
        "manage_meeting_points.html",
        ride=ride,
        meeting_points=meeting_points
    )

@app.route('/ride/<int:ride_id>', methods=['GET', 'POST'])
def ride_detail(ride_id):
    ride = Ride.query.get_or_404(ride_id)
    meeting_points = MeetingPoint.query.filter_by(ride_id=ride.id).all()

    # Check current user already joined?
    participant = None
    if current_user.is_authenticated:
        participant = RideParticipant.query.filter_by(
            ride_id=ride.id,
            user_id=current_user.id
        ).first()

    # handle join/update

    if request.method == 'POST':
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        
        selected_point = request.form.get('meeting_point')

        if participant:
            #Update meeting point
            participant.meeting_point = selected_point
            
        else:
            #Join Ride
            new_participant = RideParticipant(
                ride_id=ride.id,
                user_id=current_user.id,
                meeting_point=selected_point
            )

            db.session.add(new_participant)

        db.session.commit()
        
        return redirect(url_for('ride_detail', ride_id=ride.id))
    
    
    participants = RideParticipant.query.filter_by(ride_id=ride.id).all()
    
    ride_participants = []
    for p in participants:
        user = User.query.get(p.user_id)
        ride_participants.append({
            'username': user.username,
            'meeting_point': p.meeting_point
        })
    
    return render_template(
        'ride_detail.html',
        ride=ride,
        meeting_points=meeting_points,
        participant=participant,
        ride_participants=ride_participants
    )

# Delete Route

@app.route("/ride/<int:ride_id>/delete", methods=["POST"])
@login_required
def delete_ride(ride_id):
    ride = Ride.query.get_or_404(ride_id)

    if not current_user.is_senior:
        abort(403)

    db.session.delete(ride)
    db.session.commit()

    return redirect(url_for('rides'))

@app.route("/db-test")
def db_test():
    try:
        rides = Ride.query.all()
        return f"Database working. {len(rides)} rides found."
    except Exception as e:
        return str(e)

# --- Run App ---   

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
