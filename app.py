from flask import Flask, render_template, url_for, flash, redirect, session
from flask_mail import Mail, Message
from forms import RectangleForm, SignupForm, LoginForm, UpgradeToAdminForm
from models import db, User
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'pizza'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# --- EMAIL CONFIGURATION ---
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = '35055@acs.sch.ae'  # <--- REPLACE THIS
app.config['MAIL_PASSWORD'] = '12345678'  # <--- REPLACE THIS

mail = Mail(app)
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
        # Check if email exists
        if User.query.filter_by(email=form.email.data).first():
            flash('Email already registered.', 'danger')
            return render_template('signup.html', form=form)

        # EVERYONE starts as a 'user'. No admin code here anymore.
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


# --- NEW: ADMIN UPGRADE LOGIC ---

@app.route('/request_code')
def request_code():
    # 1. Generate a random 6-digit number
    code = str(random.randint(100000, 999999))

    # 2. Save it to the session (temporary memory)
    session['admin_otp'] = code

    # 3. Send email to the current user
    user = User.query.get(session['user_id'])

    try:
        msg = Message('Admin Access Code',
                      sender='noreply@ase-portfolio.com',
                      recipients=[user.email])
        msg.body = f"Your Admin Upgrade Code is: {code}"
        mail.send(msg)
        flash('Code sent! Check your email.', 'info')
    except Exception as e:
        print(e)
        flash('Error sending email. Check server logs.', 'danger')

    return redirect(url_for('private'))


@app.route('/private', methods=['GET', 'POST'])
def private():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    upgrade_form = UpgradeToAdminForm()

    # If they submit the code form
    if upgrade_form.validate_on_submit():
        real_code = session.get('admin_otp')  # Get the code we generated earlier

        if real_code and upgrade_form.admin_code.data == real_code:
            # Code matches! Upgrade the user.
            user = User.query.get(session['user_id'])
            user.role = 'admin'
            db.session.commit()

            # Update session so the page updates immediately
            session['role'] = 'admin'
            session.pop('admin_otp', None)  # Delete used code

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


if __name__ == '__main__':
    app.run(debug=True, port=5003)