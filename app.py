import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
import time
from datetime import datetime, timedelta
from flask import Flask, render_template, url_for, flash, redirect, session, jsonify, request
from forms import RectangleForm, SignupForm, LoginForm, UpgradeToAdminForm, WeatherReport, MarketForm
from models import db, User
import random
import yfinance as yf

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


# --- CONSOLE OTP LOGIC ---

@app.route('/request_code')
def request_code():
    code = str(random.randint(100000, 999999))
    session['admin_otp'] = code

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


# --- WEATHER ROUTE ---

@app.route('/weather', methods=['GET', 'POST'])
def weather():
    form = WeatherReport()
    weather_data = None
    error = None

    if form.validate_on_submit():
        city = form.city.data.strip()

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


# --- MARKET DASHBOARD ---

@app.route('/market', methods=['GET', 'POST'])
def market():
    form = MarketForm()

    target_currency = 'AED'
    if form.validate_on_submit():
        target_currency = form.currency.data.upper()

    market_data = None
    error = None

    gold_api_key = 'goldapi-7v3osmlrppe1p-io'
    gold_url = "https://www.goldapi.io/api/XAU/USD"
    gold_headers = {"x-access-token": gold_api_key}

    forex_url = "https://open.er-api.com/v6/latest/USD"

    try:
        gold_resp = requests.get(gold_url, headers=gold_headers, timeout=10)
        gold_json = gold_resp.json()

        forex_resp = requests.get(forex_url, timeout=10)
        forex_json = forex_resp.json()

        if "error" in gold_json or "price" not in gold_json:
            error = "Error fetching Gold data. Check API Key."
        elif target_currency not in forex_json.get('rates', {}):
            error = f"Currency {target_currency} not supported. Try EUR, GBP, JPY, etc."
        else:
            gold_price_usd_oz = gold_json['price']
            exchange_rate = forex_json['rates'][target_currency]

            gold_price_target_oz = gold_price_usd_oz * exchange_rate
            gold_price_usd_g = gold_price_usd_oz / 31.1035
            gold_price_target_g = gold_price_target_oz / 31.1035

            market_data = {
                "currency": target_currency,
                "gold_usd_oz": round(gold_price_usd_oz, 2),
                "gold_target_oz": round(gold_price_target_oz, 2),
                "gold_usd_g": round(gold_price_usd_g, 2),
                "gold_target_g": round(gold_price_target_g, 2),
                "rate": exchange_rate,
                "updated": time.strftime("%H:%M UTC")
            }

    except requests.exceptions.RequestException:
        error = "Connection error. Please check your internet."

    return render_template('market.html', form=form, market_data=market_data, error=error)

# --- GOLD HISTORY API ROUTE ---
# Uses yfinance to pull real gold futures data (GC=F) from Yahoo Finance.
# Completely free, no API key required.
# Install with: pip install yfinance


@app.route('/api/gold-history')
def gold_history():
    days = request.args.get('days', 30, type=int)
    days = min(max(days, 7), 30)   # clamp between 7 and 30

    try:
        end_date   = datetime.utcnow()
        start_date = end_date - timedelta(days=days + 5)  # fetch a few extra to account for weekends

        ticker = yf.Ticker("GC=F")
        hist   = ticker.history(start=start_date.strftime('%Y-%m-%d'),
                                end=end_date.strftime('%Y-%m-%d'))

        if hist.empty:
            return jsonify({"error": "No data returned from Yahoo Finance."}), 502

        # hist.index is a DatetimeIndex — format as YYYY-MM-DD strings
        labels = [d.strftime('%Y-%m-%d') for d in hist.index]
        prices = [round(float(p), 2) for p in hist['Close']]

        # Slice to exactly the requested number of days (markets are closed weekends)
        labels = labels[-days:]
        prices = prices[-days:]

        return jsonify({"labels": labels, "prices": prices})

    except Exception as e:
        return jsonify({"error": str(e)}), 502


if __name__ == '__main__':
    app.run(debug=True, port=5003)