import os
import re
import sqlite3
import hashlib
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage

import joblib
import streamlit as st

st.set_page_config(page_title="Fake News Detection", page_icon="📰", layout="centered")


def get_connection():
    return sqlite3.connect("users.db", check_same_thread=False)


conn = get_connection()
c = conn.cursor()


def ensure_tables():
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS history(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            news TEXT,
            prediction TEXT,
            date TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS reset_tokens(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            token TEXT UNIQUE,
            expires_at TEXT,
            used INTEGER DEFAULT 0
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS remember_tokens(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            token TEXT UNIQUE,
            expires_at TEXT,
            revoked INTEGER DEFAULT 0
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS auth_attempts(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT,
            identifier TEXT,
            created_at TEXT
        )
        """
    )
    # Best-effort migrations for older DBs that may lack constraints.
    # Existing duplicate rows in legacy DBs can make UNIQUE index creation fail.
    try:
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email_unique ON users(email)")
    except sqlite3.IntegrityError:
        c.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")

    try:
        c.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_username_unique ON users(username)")
    except sqlite3.IntegrityError:
        c.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
    conn.commit()


ensure_tables()


def hash_password(password):
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def is_valid_email(email):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def add_user(username, email, password, role="user"):
    try:
        c.execute(
            "INSERT INTO users(username,email,password,role) VALUES (?,?,?,?)",
            (username.strip(), email.strip().lower(), hash_password(password), role),
        )
        conn.commit()
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        c.execute("SELECT 1 FROM users WHERE email=?", (email.strip().lower(),))
        if c.fetchone():
            return False, "This email is already registered. Try login or reset password."
        c.execute("SELECT 1 FROM users WHERE username=?", (username.strip(),))
        if c.fetchone():
            return False, "This username is already taken. Please choose a different one."
        return False, "Unable to register right now. Please try again."


def login_user(login_value, password):
    login_value = login_value.strip()
    c.execute(
        "SELECT id, username, email, role FROM users WHERE (username=? OR email=?) AND password=?",
        (login_value, login_value.lower(), hash_password(password)),
    )
    return c.fetchone()


def record_attempt(action, identifier):
    c.execute(
        "INSERT INTO auth_attempts(action,identifier,created_at) VALUES (?,?,?)",
        (action, identifier.lower().strip(), datetime.utcnow().isoformat()),
    )
    conn.commit()


def is_rate_limited(action, identifier, max_attempts, window_minutes):
    window_start = (datetime.utcnow() - timedelta(minutes=window_minutes)).isoformat()
    c.execute(
        """
        SELECT COUNT(*)
        FROM auth_attempts
        WHERE action=? AND identifier=? AND created_at>=?
        """,
        (action, identifier.lower().strip(), window_start),
    )
    count = c.fetchone()[0]
    return count >= max_attempts


def create_remember_token(user_id):
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(days=14)).isoformat()
    c.execute(
        "INSERT INTO remember_tokens(user_id, token, expires_at, revoked) VALUES (?,?,?,0)",
        (user_id, token, expires_at),
    )
    conn.commit()
    return token


def login_with_remember_token(token):
    c.execute(
        """
        SELECT u.id, u.username, u.email, u.role, rt.id, rt.expires_at, rt.revoked
        FROM remember_tokens rt
        JOIN users u ON u.id = rt.user_id
        WHERE rt.token=?
        """,
        (token,),
    )
    row = c.fetchone()
    if not row:
        return None
    if row[6] == 1:
        return None
    if datetime.utcnow() > datetime.fromisoformat(row[5]):
        return None
    return row


def revoke_remember_token(token):
    c.execute("UPDATE remember_tokens SET revoked=1 WHERE token=?", (token,))
    conn.commit()


def create_reset_token(login_value):
    c.execute(
        "SELECT id, username, email FROM users WHERE username=? OR email=?",
        (login_value.strip(), login_value.strip().lower()),
    )
    user = c.fetchone()
    if not user:
        return False, "No account found for that username/email.", None, None

    token = secrets.token_urlsafe(24)
    expires_at = (datetime.utcnow() + timedelta(minutes=20)).isoformat()
    c.execute(
        "INSERT INTO reset_tokens(user_id, token, expires_at, used) VALUES (?,?,?,0)",
        (user[0], token, expires_at),
    )
    conn.commit()
    return True, token, user[2], user[1]


def send_reset_email(receiver_email, token):
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    mail_from = os.getenv("SMTP_FROM", smtp_user if smtp_user else "")

    if not smtp_host or not smtp_user or not smtp_pass or not mail_from:
        return False, "SMTP not configured. Showing token on screen for development."

    msg = EmailMessage()
    msg["Subject"] = "Fake News Detection - Password Reset Token"
    msg["From"] = mail_from
    msg["To"] = receiver_email
    msg.set_content(
        "Your password reset token is:\n\n"
        f"{token}\n\n"
        "Token expiry: 20 minutes.\n"
        "If you did not request this, ignore this email."
    )

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True, "Reset token sent to your email."
    except Exception:
        return False, "Unable to send email. Showing token on screen for development."


def reset_password_with_token(token, new_password):
    c.execute(
        """
        SELECT rt.id, rt.user_id, rt.expires_at, rt.used
        FROM reset_tokens rt
        WHERE rt.token=?
        """,
        (token.strip(),),
    )
    row = c.fetchone()
    if not row:
        return False, "Invalid reset token."
    if row[3] == 1:
        return False, "This token has already been used."
    if datetime.utcnow() > datetime.fromisoformat(row[2]):
        return False, "This token has expired. Request a new one."

    c.execute("UPDATE users SET password=? WHERE id=?", (hash_password(new_password), row[1]))
    c.execute("UPDATE reset_tokens SET used=1 WHERE id=?", (row[0],))
    conn.commit()
    return True, "Password updated successfully. You can now log in."


def save_prediction(username, news, prediction):
    c.execute(
        "INSERT INTO history(username,news,prediction,date) VALUES (?,?,?,?)",
        (username, news, prediction, datetime.now().strftime("%Y-%m-%d %H:%M")),
    )
    conn.commit()


def get_user_history(username):
    c.execute(
        "SELECT news,prediction,date FROM history WHERE username=? ORDER BY id DESC LIMIT 10",
        (username,),
    )
    return c.fetchall()


@st.cache_resource
def load_model():
    model = joblib.load("fake_news_model.pkl")
    vectorizer = joblib.load("tfidf_vectorizer.pkl")
    return model, vectorizer


model, vectorizer = load_model()

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "role" not in st.session_state:
    st.session_state.role = "user"
if "remember_token" not in st.session_state:
    st.session_state.remember_token = ""

query_token = st.query_params.get("remember_token", "")
if query_token and not st.session_state.logged_in:
    remembered_user = login_with_remember_token(query_token)
    if remembered_user:
        st.session_state.logged_in = True
        st.session_state.user_id = remembered_user[0]
        st.session_state.username = remembered_user[1]
        st.session_state.role = remembered_user[3]
        st.session_state.remember_token = query_token
    else:
        st.query_params.clear()

st.title("📰 Fake News Detection System")
st.markdown(
    """
### 🔍 AI-powered news authenticity checker
Use your account to predict whether a news article appears **Fake** or **Real**.
"""
)

if not st.session_state.logged_in:
    login_tab, register_tab, reset_tab = st.tabs(["Login", "Register", "Forgot Password"])

    with login_tab:
        st.subheader("Login")
        login_value = st.text_input("Email or Username", key="login_value")
        login_password = st.text_input("Password", type="password", key="login_password")
        remember_me = st.checkbox("Remember me for 14 days", key="remember_me")
        if st.button("Login", key="login_btn"):
            identifier = login_value.strip() or "anonymous"
            if is_rate_limited("login", identifier, max_attempts=5, window_minutes=10):
                st.error("Too many login attempts. Please wait 10 minutes and try again.")
            else:
                user = login_user(login_value, login_password)
                if user:
                    st.session_state.logged_in = True
                    st.session_state.user_id = user[0]
                    st.session_state.username = user[1]
                    st.session_state.role = user[3]
                    if remember_me:
                        remember_token = create_remember_token(user[0])
                        st.session_state.remember_token = remember_token
                        st.query_params["remember_token"] = remember_token
                    st.success(f"Welcome {user[1]}")
                    st.rerun()
                else:
                    record_attempt("login", identifier)
                    st.error("Invalid credentials. Use correct email/username and password.")

    with register_tab:
        st.subheader("Create Account")
        new_user = st.text_input("Username", key="reg_username")
        new_email = st.text_input("Email", key="reg_email")
        new_password = st.text_input("Password", type="password", key="reg_password")
        confirm_password = st.text_input("Confirm Password", type="password", key="reg_confirm")

        if st.button("Register", key="register_btn"):
            if not new_user.strip() or not new_email.strip() or not new_password:
                st.error("Please fill all required fields.")
            elif not is_valid_email(new_email.strip()):
                st.error("Please enter a valid email address.")
            elif len(new_password) < 8:
                st.error("Password must be at least 8 characters long.")
            elif new_password != confirm_password:
                st.error("Password and confirm password do not match.")
            else:
                ok, message = add_user(new_user, new_email, new_password)
                if ok:
                    st.success(message)
                else:
                    st.error(message)

    with reset_tab:
        st.subheader("Request Reset Token")
        reset_login = st.text_input("Enter your Email or Username", key="reset_login")
        if st.button("Send Reset Token", key="send_token_btn"):
            identifier = reset_login.strip() or "anonymous"
            if is_rate_limited("reset_request", identifier, max_attempts=3, window_minutes=15):
                st.error("Too many reset requests. Please wait 15 minutes before trying again.")
            else:
                record_attempt("reset_request", identifier)
                ok, payload, user_email, _username = create_reset_token(reset_login)
                if not ok:
                    st.error(payload)
                else:
                    sent, message = send_reset_email(user_email, payload)
                    if sent:
                        st.success(message)
                    else:
                        st.warning(message)
                        st.info(f"Development reset token: `{payload}`")

        st.subheader("Set New Password")
        reset_token = st.text_input("Reset Token", key="reset_token")
        new_password = st.text_input("New Password", type="password", key="new_pass")
        confirm_new_password = st.text_input(
            "Confirm New Password", type="password", key="confirm_new_pass"
        )
        if st.button("Reset Password", key="reset_btn"):
            token_identifier = reset_token.strip() or "anonymous"
            if is_rate_limited("reset_submit", token_identifier, max_attempts=5, window_minutes=15):
                st.error("Too many reset attempts for this token. Please request a new token.")
            elif not reset_token.strip() or not new_password:
                record_attempt("reset_submit", token_identifier)
                st.error("Token and new password are required.")
            elif len(new_password) < 8:
                record_attempt("reset_submit", token_identifier)
                st.error("New password must be at least 8 characters long.")
            elif new_password != confirm_new_password:
                record_attempt("reset_submit", token_identifier)
                st.error("Passwords do not match.")
            else:
                ok, message = reset_password_with_token(reset_token, new_password)
                if ok:
                    st.success(message)
                else:
                    record_attempt("reset_submit", token_identifier)
                    st.error(message)
else:
    st.sidebar.success(f"Logged in as {st.session_state.username}")
    if st.sidebar.button("Logout"):
        if st.session_state.remember_token:
            revoke_remember_token(st.session_state.remember_token)
        st.query_params.clear()
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.session_state.user_id = None
        st.session_state.role = "user"
        st.session_state.remember_token = ""
        st.rerun()

    st.divider()
    news_text = st.text_area(
        "📝 Paste the news article here",
        height=250,
        placeholder="Enter a full news article (paragraph-style text gives best results)...",
    )
    predict_button = st.button("🔍 Predict News")

    if predict_button:
        if not news_text.strip():
            st.error("Please enter some news text before prediction.")
        else:
            data = vectorizer.transform([news_text])
            proba = model.predict_proba(data)[0]

            fake_conf = proba[0]
            real_conf = proba[1]

            st.write(f"🔎 REAL confidence: {real_conf * 100:.2f}%")
            st.write(f"🔎 FAKE confidence: {fake_conf * 100:.2f}%")

            if real_conf >= 0.65:
                prediction = "REAL"
                st.success("✅ REAL News")
            elif real_conf <= 0.35:
                prediction = "FAKE"
                st.error("🚨 FAKE News")
            else:
                prediction = "UNCERTAIN"
                st.warning("⚠️ UNCERTAIN — News requires fact-checking")

            save_prediction(st.session_state.username, news_text, prediction)

    st.divider()
    st.markdown("### 🧪 Try Sample News")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📌 Sample REAL News"):
            st.session_state.sample = (
                "The Government of India announced a new healthcare scheme aimed at "
                "providing free medical treatment to senior citizens across the country."
            )
            st.rerun()
    with col2:
        if st.button("📌 Sample FAKE News"):
            st.session_state.sample = (
                "Aliens secretly met government officials in Delhi last night "
                "to discuss a hidden interplanetary agreement."
            )
            st.rerun()

    if "sample" in st.session_state:
        st.text_area("Sample News Text", st.session_state.sample, height=150)

    st.markdown("### Your Recent Prediction History")
    st.table(get_user_history(st.session_state.username))

with st.expander("ℹ️ How does this system work?"):
    st.write(
        """
    1. The input news text is cleaned and processed.
    2. TF-IDF converts text into numerical features.
    3. A trained Machine Learning model analyzes patterns.
    4. The model predicts whether the news is Fake or Real.
    """
    )

st.warning(
    """
⚠️ **Disclaimer**
This system predicts news authenticity based on linguistic patterns learned from data.
It does **not** verify facts from the internet or real-time sources.
"""
)