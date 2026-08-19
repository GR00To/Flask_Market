from market import app, db, mail, serializer
from flask import render_template, redirect, url_for, flash, request
from market.models import Item, User
from market.forms import RegisterForm, LoginForm, PurchaseItemForm, SellItemForm
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message


# ── helpers ───────────────────────────────────────────────────────────────────

def send_verification_email(user):
    """Generate a secure token and email the confirmation link via Mailtrap."""
    token = serializer.dumps(user.email_address, salt='email-confirm')
    confirm_url = url_for('confirm_email', token=token, _external=True)

    msg = Message(
        subject='Confirm Your Email – Flask Market',
        recipients=[user.email_address]
    )
    msg.body = (
        f"Hi {user.username},\n\n"
        f"Thanks for registering at Flask Market!\n\n"
        f"Please click the link below to verify your email address:\n\n"
        f"  {confirm_url}\n\n"
        f"This link expires in 1 hour.\n\n"
        f"If you did not create this account, you can safely ignore this email.\n\n"
        f"— Flask Market Team"
    )
    mail.send(msg)


# ── routes ────────────────────────────────────────────────────────────────────

@app.route('/')
@app.route('/home')
def home_page():
    return render_template('home.html')


@app.route('/market', methods=['GET', 'POST'])
@login_required
def market_page():
    purchase_form = PurchaseItemForm()
    selling_form  = SellItemForm()

    if request.method == 'POST':
        # Purchase Item Logic
        purchased_item = request.form.get('purchased_item')
        p_item_object  = Item.query.filter_by(name=purchased_item).first()
        if p_item_object:
            if current_user.can_purchase(p_item_object):
                p_item_object.buy(current_user)
                flash(f"Congratulations! You purchased {p_item_object.name} for {p_item_object.price}$", category='success')
            else:
                flash(f"Unfortunately, you don't have enough money to purchase {p_item_object.name}!", category='danger')

        # Sell Item Logic
        sold_item    = request.form.get('sold_item')
        s_item_object = Item.query.filter_by(name=sold_item).first()
        if s_item_object:
            if current_user.can_sell(s_item_object):
                s_item_object.sell(current_user)
                flash(f"Congratulations! You sold {s_item_object.name} back to market!", category='success')
            else:
                flash(f"Something went wrong with selling {s_item_object.name}", category='danger')

        return redirect(url_for('market_page'))

    if request.method == 'GET':
        items       = Item.query.filter_by(owner=None)
        owned_items = Item.query.filter_by(owner=current_user.id)
        return render_template('market.html', items=items, purchase_form=purchase_form,
                               owned_items=owned_items, selling_form=selling_form)


@app.route('/register', methods=['GET', 'POST'])
def register_page():
    form = RegisterForm()
    if form.validate_on_submit():
        user_to_create = User(
            username=form.username.data,
            email_address=form.email_address.data,
            password=form.password1.data
        )
        db.session.add(user_to_create)
        db.session.commit()

        # Send verification email via Mailtrap
        send_verification_email(user_to_create)

        flash('Account created! A verification link has been sent to your email. '
              'Please verify before logging in.', category='success')
        return redirect(url_for('login_page'))

    if form.errors != {}:
        for err_msg in form.errors.values():
            flash(f'There was an error with creating a user: {err_msg}', category='danger')

    return render_template('register.html', form=form)


@app.route('/confirm/<token>')
def confirm_email(token):
    """User clicks the link in their email — verify token, mark account as verified."""
    try:
        email = serializer.loads(token, salt='email-confirm', max_age=3600)  # 1-hour expiry
    except Exception:
        flash('The verification link is invalid or has expired. Please register again.',
              category='danger')
        return redirect(url_for('register_page'))

    user = User.query.filter_by(email_address=email).first()
    if user is None:
        flash('No account found for this link.', category='danger')
        return redirect(url_for('register_page'))

    if user.email_verified:
        flash('Your email is already verified. Please log in.', category='info')
    else:
        user.email_verified = True
        db.session.commit()
        flash('✅ Email verified successfully! You can now log in.', category='success')

    return redirect(url_for('login_page'))


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    form = LoginForm()
    if form.validate_on_submit():
        attempted_user = User.query.filter_by(username=form.username.data).first()
        if attempted_user and attempted_user.check_password_correction(
                attempted_password=form.password.data
        ):
            if not attempted_user.email_verified:
                flash('Please verify your email before logging in. Check your inbox.',
                      category='danger')
                return redirect(url_for('login_page'))

            login_user(attempted_user)
            flash(f'Success! You are logged in as: {attempted_user.username}', category='success')
            return redirect(url_for('market_page'))
        else:
            flash('Username and password do not match! Please try again.', category='danger')

    return render_template('login.html', form=form)


@app.route('/logout')
def logout_page():
    logout_user()
    flash('You have been logged out!', category='info')
    return redirect(url_for('home_page'))
