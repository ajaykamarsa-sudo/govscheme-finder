
import os
from functools import wraps
from urllib.parse import urlparse

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, abort
)
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, Scheme
from eligibility import is_eligible

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "development-only-change-this-key"
)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///schemes.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to continue."


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@app.route("/")
def index():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    schemes_query = Scheme.query.filter_by(active=True)

    if query:
        schemes_query = schemes_query.filter(
            db.or_(
                Scheme.name.ilike(f"%{query}%"),
                Scheme.description.ilike(f"%{query}%")
            )
        )

    if category:
        schemes_query = schemes_query.filter_by(category=category)

    schemes = schemes_query.order_by(Scheme.name).all()
    categories = [
        row[0] for row in
        db.session.query(Scheme.category)
        .filter_by(active=True).distinct().all()
    ]

    return render_template(
        "index.html",
        schemes=schemes,
        categories=categories,
        query=query,
        selected_category=category
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        category = request.form.get("category", "General")
        income_text = request.form.get("income", "0").strip()

        if not name or not email or not password:
            flash("Please complete all required fields.", "error")
        elif len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
        elif User.query.filter_by(email=email).first():
            flash("An account with that email already exists.", "error")
        else:
            try:
                income = float(income_text or 0)
                if income < 0:
                    raise ValueError
            except ValueError:
                flash("Enter a valid non-negative annual income.", "error")
                return render_template("register.html")

            user = User(
                name=name,
                email=email,
                password_hash=generate_password_hash(password),
                category=category,
                income=income
            )
            db.session.add(user)
            db.session.commit()

            flash("Registration successful. Please log in.", "success")
            return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Welcome back!", "success")

            destination = request.args.get("next", "")
            if destination:
                parsed = urlparse(destination)
                if parsed.scheme or parsed.netloc or not destination.startswith("/"):
                    destination = ""

            if destination:
                return redirect(destination)

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


@app.route("/dashboard")
@login_required
def dashboard():
    schemes = Scheme.query.filter_by(active=True).order_by(Scheme.name).all()
    eligible_schemes = [
        scheme for scheme in schemes
        if is_eligible(current_user, scheme)
    ]

    return render_template(
        "dashboard.html",
        schemes=eligible_schemes,
        total_schemes=len(schemes),
        eligible_count=len(eligible_schemes)
    )


@app.route("/scheme/<int:scheme_id>")
def scheme_detail(scheme_id):
    scheme = db.get_or_404(Scheme, scheme_id)
    if not scheme.active:
        abort(404)

    eligible = (
        is_eligible(current_user, scheme)
        if current_user.is_authenticated else None
    )

    return render_template(
        "scheme.html", scheme=scheme, eligible=eligible
    )


@app.route("/admin")
@admin_required
def admin():
    return render_template(
        "admin.html",
        users_count=User.query.count(),
        schemes_count=Scheme.query.count(),
        schemes=Scheme.query.order_by(Scheme.name).all()
    )


@app.errorhandler(403)
def forbidden(error):
    return render_template(
        "base.html",
        error_message="You do not have permission to access this page."
    ), 403


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(debug=True)
