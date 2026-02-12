import requests
from flask import Flask, render_template, url_for, flash, redirect, session
from forms import RectangleForm, SignupForm, LoginForm, UpgradeToAdminForm, WeatherReport
from models import db, User
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pizza'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()


# --- PUBLIC ROUTES ---

@app.route('/')
def home():
    return render_template('index.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/rectangle', methods=['GET', 'POST'])
def rectangle():
    form = RectangleForm()
    area = None
    perimeter = None
    if form.validate_on_submit():
        if form.area.data:
            area = form.length.data * form.width.data
        elif form.perimeter.data:
            perimeter = 2 * (form.length.data + form.width.data)
    return render_template("rectangle.html", form=form, area=area, perimeter=perimeter)


# --- AUTH ROUTES ---

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered.', 'danger')
            return render_template('signup.html', form=form)

        # Everyone starts as a USER
        new_user = User(username=form.username.data, email=form.email.data, role="user")
        new_user.set_password(form.password.data)

        db.session.add(new_user)
        db.session.commit()

        flash('Account created! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html', form=form)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()

        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account is deactivated.', 'danger')
                return redirect(url_for('login'))

            session['user_id'] = user.id
            session['role'] = user.role
            session['username'] = user.username

            flash('Logged in successfully!', 'success')
            return redirect(url_for('private'))
        else:
            flash('Invalid email or password.', 'danger')

    return render_template('login.html', form=form)


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out.', 'info')
    return redirect(url_for('home'))


# --- NEW: CONSOLE OTP LOGIC ---

@app.route('/request_code')
def request_code():
    # 1. Generate a random 6-digit number
    code = str(random.randint(100000, 999999))

    # 2. Save it to the session
    session['admin_otp'] = code

    # 3. PRINT TO TERMINAL (Instead of Email)
    print("\n" + "=" * 40)
    print(f" [SIMULATED EMAIL] To: {session['username']}")
    print(f" YOUR ADMIN CODE IS: {code}")
    print("=" * 40 + "\n")

    flash('Code "sent"! Check your server terminal/console.', 'info')

    return redirect(url_for('private'))


@app.route('/private', methods=['GET', 'POST'])
def private():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    upgrade_form = UpgradeToAdminForm()

    if upgrade_form.validate_on_submit():
        real_code = session.get('admin_otp')

        if real_code and upgrade_form.admin_code.data == real_code:
            user = User.query.get(session['user_id'])
            user.role = 'admin'
            db.session.commit()

            session['role'] = 'admin'
            session.pop('admin_otp', None)

            flash('Success! You are now an Admin.', 'success')
            return redirect(url_for('private'))
        else:
            flash('Invalid Code.', 'danger')

    return render_template('private.html', upgrade_form=upgrade_form)


# --- ADMIN DASHBOARD ---

@app.route('/admin')
def admin():
    if session.get('role') != 'admin':
        return redirect(url_for('home'))
    users = User.query.all()
    return render_template('admin.html', users=users)


@app.route('/admin/toggle/<int:user_id>', methods=['POST'])
def toggle_user(user_id):
    if session.get('role') != 'admin': return redirect(url_for('home'))
    user = User.query.get_or_404(user_id)
    if user.id != session['user_id']:
        user.is_active = not user.is_active
        db.session.commit()
    return redirect(url_for('admin'))


@app.route('/admin/delete/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    if session.get('role') != 'admin': return redirect(url_for('home'))
    user = User.query.get_or_404(user_id)
    if user.id != session['user_id']:
        db.session.delete(user)
        db.session.commit()
    return redirect(url_for('admin'))

@app.route('/weather', methods=['GET', 'POST'])
def weather():
    form = WeatherReport()

    weather_data = None
    error = None

    if form.validate_on_submit():
        city = form.city.data.strip()

        # 1) City -> (lat, lon) using Nominatim
        geo_url = "https://nominatim.openstreetmap.org/search"
        geo_params = {"q": city, "format": "json", "limit": 1}
        geo_headers = {"User-Agent": "ASE-Flask-Student-Project (school use)"}

        geo_resp = requests.get(geo_url, params=geo_params, headers=geo_headers, timeout=10)
        geo_results = geo_resp.json()

        if not geo_results:
            error = "City not found. Please try another spelling."
            return render_template("weather.html", form=form, weather_data=weather_data, error=error)

        lat = float(geo_results[0]["lat"])
        lon = float(geo_results[0]["lon"])

        # 2) (lat, lon) -> current weather using Open-Meteo
        weather_url = "https://api.open-meteo.com/v1/forecast"
        weather_params = {
            "latitude": lat,
            "longitude": lon,
            "current_weather": True
        }

        w_resp = requests.get(weather_url, params=weather_params, timeout=10)
        w_json = w_resp.json()

        if "current_weather" not in w_json:
            error = "Weather data is unavailable right now. Try again later."
        else:
            cw = w_json["current_weather"]
            weather_data = {
                "city": city,
                "temperature": cw.get("temperature"),
                "windspeed": cw.get("windspeed"),
                "winddirection": cw.get("winddirection"),
                "time": cw.get("time")
            }

    return render_template("weather.html", form=form, weather_data=weather_data, error=error)

if __name__ == '__main__':
    app.run(debug=True, port=5003)