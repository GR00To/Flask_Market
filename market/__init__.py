from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_mail import Mail
from itsdangerous import URLSafeTimedSerializer

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///market.db'
app.config['SECRET_KEY'] = 'ec9439cfc6c796ae2029594d'

# ── Real Gmail SMTP Configuration ─────────────────────────────────────────────
app.config['MAIL_SERVER']         = 'smtp.gmail.com'
app.config['MAIL_PORT']           = 587
app.config['MAIL_USE_TLS']        = True
app.config['MAIL_USERNAME']       = 'mohammadshamil225@gmail.com'
app.config['MAIL_PASSWORD']       = 'joak hkjn jehy kvnh'
app.config['MAIL_DEFAULT_SENDER'] = ('Flask Market', 'mohammadshamil225@gmail.com')

db           = SQLAlchemy(app)
bcrypt       = Bcrypt(app)
mail         = Mail(app)
serializer   = URLSafeTimedSerializer(app.config['SECRET_KEY'])
login_manager = LoginManager(app)
login_manager.login_view             = 'login_page'
login_manager.login_message_category = 'info'

from market import routes