import os
import sys
import re
from decimal import Decimal

import mysql.connector
from mysql.connector import Error

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QPixmap, QFont, QPainter
from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QHBoxLayout,
    QGridLayout,
    QVBoxLayout,
    QFrame,
    QMessageBox,
    QSizePolicy,
    QDialog,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QInputDialog,
    QHeaderView,
    QLineEdit,
    QComboBox,
    QStackedWidget,
)

# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DB_HOST = "127.0.0.1"
DB_PORT = 3306
DB_NAME = "car_customizer"
DB_USER = "root"
DB_PASSWORD = "P14Y3R"


# ============================================================
# ASSETS
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSET_DIR = os.path.join(BASE_DIR, "assets", "car")


# ============================================================
# ROLES
# ============================================================

ROLE_GUEST = "Guest"
ROLE_PLAYER = "Player"
ROLE_SHOP_MANAGER = "Shop Manager"
ROLE_ADMIN = "Administrator"

# Car purchase prices. The existing Skyline is the starter car;
# the Toyota Supra MK4 is an additional car that can be purchased.
CAR_PRICES = {
    "Skyline GT-R R34": Decimal("0.00"),
    "Supra MK4": Decimal("45000.00"),
    "Lexus LFA": Decimal("150000.00"),
    "Lancer Evolution IX": Decimal("55000.00"),
    "Honda NSX": Decimal("75000.00"),
    "RX-7": Decimal("40000.00"),
}

# Optional per-model base images. If a model image is not present,
# the application falls back to assets/car/base.png.
MODEL_ASSET_DIRS = {
    "Skyline GT-R R34": "r34",
    "Supra MK4": "supra",
}

MODEL_ASSETS = {
    "Skyline GT-R R34": ["base.png"],
    "Supra MK4": ["supra_base.png", "base.png"],
}


# ============================================================
# HELPERS
# ============================================================

def money(value):
    try:
        return f"₹{float(value):,.2f}"
    except Exception:
        return "₹0.00"


# ============================================================
# DATABASE
# ============================================================

class Database:

    def __init__(self):
        self.conn = None
        self.connect()
        self.ensure_schema()

    def connect(self):

        self.conn = mysql.connector.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            autocommit=True
        )

        print("Connected to MySQL")

    def ensure_schema(self):

        """Ensure soft-delete support exists for the parts catalog."""

        self.ensure_connection_if_needed()

        cursor = self.conn.cursor(dictionary=True)

        try:

            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM information_schema.columns
                WHERE table_schema = %s
                  AND table_name = 'parts'
                  AND column_name = 'is_active'
                """,
                (DB_NAME,)
            )

            row = cursor.fetchone()

        finally:

            cursor.close()

        if not row or int(row["count"]) == 0:

            cursor = self.conn.cursor()

            try:
                cursor.execute(
                    """
                    ALTER TABLE parts
                    ADD COLUMN is_active TINYINT(1) NOT NULL DEFAULT 1
                    """
                )
            finally:
                cursor.close()

    def ensure_connection_if_needed(self):

        if self.conn is None or not self.conn.is_connected():

            self.connect()

    def ensure_connection(self):

        if self.conn is None or not self.conn.is_connected():

            self.connect()

        else:

            self.conn.ping(
                reconnect=True,
                attempts=3,
                delay=1
            )

    def query(self, sql, params=()):

        self.ensure_connection()

        cursor = self.conn.cursor(
            dictionary=True
        )

        try:

            cursor.execute(
                sql,
                params
            )

            return cursor.fetchall()

        finally:

            cursor.close()

    def one(self, sql, params=()):

        rows = self.query(
            sql,
            params
        )

        return rows[0] if rows else None

    def execute(self, sql, params=()):

        self.ensure_connection()

        cursor = self.conn.cursor()

        try:

            cursor.execute(
                sql,
                params
            )

            return cursor.lastrowid

        finally:

            cursor.close()

    def close(self):

        if self.conn and self.conn.is_connected():

            self.conn.close()

# ============================================================
# LOGIN WINDOW — PROFESSIONAL BLACK / PURPLE UI
# ============================================================

class LoginWindow(QWidget):

    def __init__(self, db, login_success_callback):

        super().__init__()

        self.db = db
        self.login_success_callback = login_success_callback

        self.setWindowTitle(
            "Car Customizer — Sign In"
        )

        self.setMinimumSize(
            560,
            700
        )

        self.resize(
            500,
            700
        )

        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowCloseButtonHint |
            Qt.WindowType.WindowMinimizeButtonHint
        )

        self.build_ui()

        # Login is intentionally fullscreen so it matches the Garage UI.
        # The in-window CLOSE button below provides a visible way to exit.
        self.showFullScreen()

        self.username_input.setFocus()

    def build_ui(self):

        # ====================================================
        # MAIN LOGIN WINDOW STYLE
        # ====================================================

        self.setStyleSheet(
            """
            QWidget {
                background:
                    qlineargradient(
                        x1:0,
                        y1:0,
                        x2:1,
                        y2:1,
                        stop:0 #050507,
                        stop:0.45 #0b0910,
                        stop:1 #130b1c
                    );

                color:#f4f1f8;
                font-family:"Segoe UI";
            }

            /* ==============================================
               LOGIN CARD
               ============================================== */

            QFrame#loginCard {

                background:
                    qlineargradient(
                        x1:0,
                        y1:0,
                        x2:1,
                        y2:1,
                        stop:0 #111116,
                        stop:1 #17121d
                    );

                border:1px solid #30263b;
                border-radius:22px;
            }

            QFrame#accentBar {

                background:
                    qlineargradient(
                        x1:0,
                        y1:0,
                        x2:1,
                        y2:0,
                        stop:0 #6d28d9,
                        stop:0.5 #8b5cf6,
                        stop:1 #a855f7
                    );

                border:none;
                border-radius:3px;
            }

            QLabel#brandIcon {

                color:#a855f7;
                font-size:44px;
                font-weight:900;

                background:transparent;
                border:none;
            }

            QLabel#logo {

                color:#ffffff;
                font-size:31px;
                font-weight:900;

                background:transparent;
                border:none;

                letter-spacing:1px;
            }

            QLabel#subtitle {

                color:#9f98a8;
                font-size:13px;

                background:transparent;
                border:none;
            }

            QLabel#welcome {

                color:#eee8f4;
                font-size:25px;
                font-weight:700;

                background:transparent;
                border:none;
            }

            QLabel#loginHint {

                color:#756d80;
                font-size:13px;

                background:transparent;
                border:none;
            }

            QLabel#fieldLabel {

                color:#bdb5c8;
                font-size:11px;
                font-weight:800;

                background:transparent;
                border:none;

                letter-spacing:1px;
            }

            QLineEdit {

                background:#0b0a0f;
                color:#f5f2f8;

                border:1px solid #302a37;
                border-radius:11px;

                padding:0px 15px;

                font-size:14px;

                selection-background-color:#6d28d9;
                selection-color:white;
            }

            QLineEdit:hover {

                border:1px solid #443650;
                background:#0d0b11;
            }

            QLineEdit:focus {

                border:1px solid #8b5cf6;
                background:#100c15;
            }

            QLineEdit::placeholder {

                color:#5f5868;
            }

            QPushButton#loginButton {

                background:
                    qlineargradient(
                        x1:0,
                        y1:0,
                        x2:1,
                        y2:0,
                        stop:0 #6d28d9,
                        stop:1 #8b5cf6
                    );

                color:white;

                border:1px solid #9b6cff;
                border-radius:11px;

                font-size:14px;
                font-weight:800;

                padding:11px 20px;
            }

            QPushButton#loginButton:hover {

                background:
                    qlineargradient(
                        x1:0,
                        y1:0,
                        x2:1,
                        y2:0,
                        stop:0 #7c3aed,
                        stop:1 #a855f7
                    );

                border:1px solid #b78aff;
            }

            QPushButton#loginButton:pressed {

                background:#5b21b6;
            }

            QPushButton#guestButton {

                background:#111016;
                color:#b8b0c1;

                border:1px solid #342d3d;
                border-radius:10px;

                font-size:13px;
                font-weight:700;

                padding:10px 16px;
            }

            QPushButton#guestButton:hover {

                background:#17121e;
                color:#e2d9eb;

                border:1px solid #574366;
            }

            QPushButton#signupButton {

                background:#17121f;
                color:#cfc5da;

                border:1px solid #4b3a5d;
                border-radius:10px;

                font-size:13px;
                font-weight:700;

                padding:10px 16px;
            }

            QPushButton#signupButton:hover {

                background:#21182d;
                color:#eee7f5;

                border:1px solid #72568d;
            }

            QPushButton#closeCornerButton {

                background:#111016;
                color:#aaa1b2;

                border:1px solid #342d3d;
                border-radius:10px;

                font-size:18px;
                font-weight:700;
            }

            QPushButton#closeCornerButton:hover {

                background:#381b25;
                color:#ffffff;

                border:1px solid #a34b61;
            }

            QPushButton#closeCornerButton:pressed {

                background:#24121a;
            }

            QFrame#verticalDivider {

                background:#2d2635;
                border:none;
                max-width:1px;
            }
            """
        )

        # ====================================================
        # FULLSCREEN OUTER LAYOUT
        # ====================================================

        outer = QVBoxLayout(self)

        outer.setContentsMargins(
            34,
            28,
            34,
            34
        )

        outer.setSpacing(0)

        # ====================================================
        # TOP-LEFT CLOSE BUTTON
        # ====================================================

        top_bar = QHBoxLayout()

        top_bar.setContentsMargins(
            0,
            0,
            0,
            0
        )

        top_bar.setSpacing(0)

        close_corner = QPushButton(
            "✕"
        )

        close_corner.setObjectName(
            "closeCornerButton"
        )

        close_corner.setFixedSize(
            46,
            46
        )

        close_corner.setToolTip(
            "Close application"
        )

        close_corner.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        close_corner.clicked.connect(
            QApplication.quit
        )

        top_bar.addWidget(
            close_corner,
            0,
            Qt.AlignmentFlag.AlignLeft |
            Qt.AlignmentFlag.AlignTop
        )

        top_bar.addStretch()

        outer.addLayout(
            top_bar
        )

        # ====================================================
        # CENTER AREA
        # ====================================================

        center = QVBoxLayout()

        center.setContentsMargins(
            0,
            0,
            0,
            0
        )

        center.setSpacing(0)

        center.addStretch(1)

        # ====================================================
        # WIDE LOGIN CARD
        # ====================================================

        card = QFrame()

        card.setObjectName(
            "loginCard"
        )

        card.setFixedSize(
            1050,
            520
        )

        card_layout = QHBoxLayout(
            card
        )

        card_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        card_layout.setSpacing(0)

        # ====================================================
        # LEFT BRAND / WELCOME PANEL
        # ====================================================

        left_panel = QFrame()

        left_panel.setStyleSheet(
            """
            QFrame {
                background:transparent;
                border:none;
            }
            """
        )

        left_layout = QVBoxLayout(
            left_panel
        )

        left_layout.setContentsMargins(
            60,
            45,
            45,
            45
        )

        left_layout.setSpacing(0)

        left_layout.addStretch(1)

        brand_icon = QLabel(
            "⌁"
        )

        brand_icon.setObjectName(
            "brandIcon"
        )

        brand_icon.setAlignment(
            Qt.AlignmentFlag.AlignLeft
        )

        left_layout.addWidget(
            brand_icon
        )

        left_layout.addSpacing(
            8
        )

        logo = QLabel(
            "CAR CUSTOMIZER"
        )

        logo.setObjectName(
            "logo"
        )

        logo.setAlignment(
            Qt.AlignmentFlag.AlignLeft
        )

        left_layout.addWidget(
            logo
        )

        left_layout.addSpacing(
            5
        )

        subtitle = QLabel(
            "GARAGE MANAGEMENT SYSTEM"
        )

        subtitle.setObjectName(
            "subtitle"
        )

        subtitle.setAlignment(
            Qt.AlignmentFlag.AlignLeft
        )

        left_layout.addWidget(
            subtitle
        )

        left_layout.addSpacing(
            42
        )

        welcome = QLabel(
            "Welcome back"
        )

        welcome.setObjectName(
            "welcome"
        )

        welcome.setAlignment(
            Qt.AlignmentFlag.AlignLeft
        )

        left_layout.addWidget(
            welcome
        )

        left_layout.addSpacing(
            8
        )

        login_hint = QLabel(
            "Sign in to access your garage,\n"
            "manage your vehicle and start customizing."
        )

        login_hint.setObjectName(
            "loginHint"
        )

        login_hint.setAlignment(
            Qt.AlignmentFlag.AlignLeft
        )

        login_hint.setWordWrap(
            True
        )

        left_layout.addWidget(
            login_hint
        )

        left_layout.addStretch(1)

        card_layout.addWidget(
            left_panel,
            1
        )

        # ====================================================
        # DIVIDER
        # ====================================================

        divider = QFrame()

        divider.setObjectName(
            "verticalDivider"
        )

        divider.setFixedWidth(
            1
        )

        card_layout.addWidget(
            divider
        )

        # ====================================================
        # RIGHT LOGIN PANEL
        # ====================================================

        right_panel = QFrame()

        right_panel.setStyleSheet(
            """
            QFrame {
                background:transparent;
                border:none;
            }
            """
        )

        right_layout = QVBoxLayout(
            right_panel
        )

        right_layout.setContentsMargins(
            55,
            50,
            60,
            50
        )

        right_layout.setSpacing(0)

        right_layout.addStretch(1)

        panel_title = QLabel(
            "SIGN IN"
        )

        panel_title.setStyleSheet(
            """
            QLabel {
                color:#eee8f4;
                font-size:20px;
                font-weight:800;
                background:transparent;
                border:none;
            }
            """
        )

        right_layout.addWidget(
            panel_title
        )

        right_layout.addSpacing(
            6
        )

        panel_hint = QLabel(
            "Enter your account details below."
        )

        panel_hint.setObjectName(
            "loginHint"
        )

        right_layout.addWidget(
            panel_hint
        )

        right_layout.addSpacing(
            25
        )

        username_label = QLabel(
            "USERNAME"
        )

        username_label.setObjectName(
            "fieldLabel"
        )

        right_layout.addWidget(
            username_label
        )

        right_layout.addSpacing(
            7
        )

        self.username_input = QLineEdit()

        self.username_input.setPlaceholderText(
            "Enter your username"
        )

        self.username_input.setMinimumHeight(
            48
        )

        self.username_input.setClearButtonEnabled(
            True
        )

        right_layout.addWidget(
            self.username_input
        )

        right_layout.addSpacing(
            18
        )

        password_label = QLabel(
            "PASSWORD"
        )

        password_label.setObjectName(
            "fieldLabel"
        )

        right_layout.addWidget(
            password_label
        )

        right_layout.addSpacing(
            7
        )

        self.password_input = QLineEdit()

        self.password_input.setPlaceholderText(
            "Enter your password"
        )

        self.password_input.setEchoMode(
            QLineEdit.EchoMode.Password
        )

        self.password_input.setMinimumHeight(
            48
        )

        self.password_input.returnPressed.connect(
            self.login
        )

        right_layout.addWidget(
            self.password_input
        )

        right_layout.addSpacing(
            22
        )

        login_button = QPushButton(
            "SIGN IN"
        )

        login_button.setObjectName(
            "loginButton"
        )

        login_button.setMinimumHeight(
            46
        )

        login_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        login_button.clicked.connect(
            self.login
        )

        right_layout.addWidget(
            login_button
        )

        right_layout.addSpacing(
            10
        )

        # Secondary actions are placed side-by-side.
        secondary = QHBoxLayout()

        secondary.setSpacing(
            10
        )

        guest_button = QPushButton(
            "CONTINUE AS GUEST"
        )

        guest_button.setObjectName(
            "guestButton"
        )

        guest_button.setMinimumHeight(
            42
        )

        guest_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        guest_button.clicked.connect(
            self.login_guest
        )

        signup_button = QPushButton(
            "CREATE ACCOUNT"
        )

        signup_button.setObjectName(
            "signupButton"
        )

        signup_button.setMinimumHeight(
            42
        )

        signup_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        signup_button.clicked.connect(
            self.open_signup
        )

        secondary.addWidget(
            guest_button,
            1
        )

        secondary.addWidget(
            signup_button,
            1
        )

        right_layout.addLayout(
            secondary
        )

        right_layout.addStretch(1)

        card_layout.addWidget(
            right_panel,
            1
        )

        # ====================================================
        # CENTER THE WIDE CARD
        # ====================================================

        center.addWidget(
            card,
            0,
            Qt.AlignmentFlag.AlignCenter
        )

        center.addStretch(1)

        outer.addLayout(
            center,
            1
        )

    # ========================================================
    # LOGIN
    # ========================================================

    def login(self):

        username = self.username_input.text().strip()

        password = self.password_input.text()

        if not username or not password:

            QMessageBox.warning(
                self,
                "Login Required",
                "Please enter both username and password."
            )

            if not username:

                self.username_input.setFocus()

            else:

                self.password_input.setFocus()

            return

        try:

            user = self.db.one(
                """
                    SELECT
                    u.user_id,
                    u.username,
                    u.nickname,
                    u.money,
                    u.role_id,
                    u.is_active,
                    r.role_name
                FROM users u
                JOIN roles r
                    ON r.role_id = u.role_id
                WHERE u.username = %s
                    AND u.password = %s
                    AND u.is_active = 1
                """,
                (
                    username,
                    password
                )
            )

            if not user:

                QMessageBox.warning(
                    self,
                    "Login Failed",
                    "Invalid username or password."
                )

                self.password_input.clear()

                self.password_input.setFocus()

                return

            print(
                f"Logged in as {user['username']} "
                f"(user_id={user['user_id']})"
            )

            self.login_success_callback(
                user
            )

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Login Error",
                str(exc)
            )

    # ========================================================
    # GUEST LOGIN
    # ========================================================

    def login_guest(self):

        guest = {
            "user_id": None,
            "username": "Guest",
            "money": Decimal("0"),
            "role_id": None,
            "role_name": ROLE_GUEST
        }

        print(
            "Continuing as Guest"
        )

        self.login_success_callback(
            guest
        )

        # ========================================================
    # SIGN UP
    # ========================================================

    def open_signup(self):

        dialog = SignupDialog(
            self.db,
            self
        )

        if dialog.exec() == QDialog.DialogCode.Accepted:

            self.username_input.clear()
            self.password_input.clear()

            QMessageBox.information(
                self,
                "Account Created",
                "Your account has been created successfully.\n\n"
                "You can now sign in with your new username and password."
            )

# ============================================================
# SIGN UP DIALOG
# ============================================================

class SignupDialog(QDialog):

    def __init__(self, db, parent=None):

        super().__init__(parent)

        self.db = db

        self.setWindowTitle(
            "Create Account"
        )

        self.setMinimumSize(
            820,
            650
        )

        self.resize(
            900,
            680
        )

        self.build_ui()

    def build_ui(self):

        self.setStyleSheet(
            """
            QDialog {
                background:#09070d;
                color:#f4f1f8;
            }

            QLabel {
                background:transparent;
                color:#dce1e6;
            }

            QLabel#title {
                color:#c4b5fd;
                font-size:26px;
                font-weight:800;
            }

            QLabel#hint {
                color:#8f8799;
                font-size:12px;
            }

            QLabel#sectionTitle {
                color:#e8e1ef;
                font-size:14px;
                font-weight:800;
            }

            QLabel#fieldLabel {
                color:#bdb5c8;
                font-size:11px;
                font-weight:800;
                letter-spacing:0.5px;
            }

            QLabel#requirementsTitle {
                color:#d9d1e3;
                font-size:12px;
                font-weight:800;
                letter-spacing:0.5px;
            }

            QLabel#passwordRule {
                color:#82798c;
                font-size:12px;
                background:transparent;
                border:none;
            }

            QLabel#passwordRuleValid {
                color:#78d6a0;
                font-size:12px;
                background:transparent;
                border:none;
                font-weight:600;
            }

            QFrame#panel {
                background:#100d15;
                border:1px solid #292230;
                border-radius:14px;
            }

            QFrame#requirementsPanel {
                background:#0d0a12;
                border:1px solid #292230;
                border-radius:14px;
            }

            QLineEdit {
                background:#121019;
                color:#f4f1f8;
                border:1px solid #30263d;
                border-radius:9px;
                padding:0px 13px;
                min-height:44px;
                font-size:13px;
            }

            QLineEdit:focus {
                border:1px solid #8b5cf6;
                background:#15111b;
            }

            QPushButton {
                background:#8b5cf6;
                color:white;
                border:none;
                border-radius:9px;
                padding:10px 18px;
                font-weight:700;
                min-height:44px;
                font-size:13px;
            }

            QPushButton:hover {
                background:#7c3aed;
            }

            QPushButton#cancelButton {
                background:#211b29;
                color:#c9c2d2;
                border:1px solid #3a3047;
            }

            QPushButton#cancelButton:hover {
                background:#2a2233;
            }

            QFrame#separator {
                background:#2d2635;
                border:none;
                max-height:1px;
            }
            """
        )

        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            42,
            30,
            42,
            30
        )

        layout.setSpacing(0)

        # ====================================================
        # HEADER
        # ====================================================

        title = QLabel(
            "CREATE ACCOUNT"
        )

        title.setObjectName(
            "title"
        )

        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(
            title
        )

        layout.addSpacing(
            5
        )

        subtitle = QLabel(
            "Create your Player account"
        )

        subtitle.setObjectName(
            "hint"
        )

        subtitle.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(
            subtitle
        )

        layout.addSpacing(
            24
        )

        # ====================================================
        # TWO-COLUMN CONTENT
        # ====================================================

        columns = QHBoxLayout()

        columns.setSpacing(
            20
        )

        # ----------------------------------------------------
        # LEFT: ACCOUNT DETAILS
        # ----------------------------------------------------

        account_panel = QFrame()

        account_panel.setObjectName(
            "panel"
        )

        account_layout = QVBoxLayout(
            account_panel
        )

        account_layout.setContentsMargins(
            24,
            22,
            24,
            22
        )

        account_layout.setSpacing(
            0
        )

        account_title = QLabel(
            "ACCOUNT DETAILS"
        )

        account_title.setObjectName(
            "sectionTitle"
        )

        account_layout.addWidget(
            account_title
        )

        account_layout.addSpacing(
            20
        )

        username_label = QLabel(
            "USERNAME"
        )

        username_label.setObjectName(
            "fieldLabel"
        )

        account_layout.addWidget(
            username_label
        )

        account_layout.addSpacing(
            7
        )

        self.username_input = QLineEdit()

        self.username_input.setPlaceholderText(
            "3–20 characters: letters, numbers, _"
        )

        self.username_input.setMaxLength(
            20
        )

        account_layout.addWidget(
            self.username_input
        )

        account_layout.addSpacing(
            22
        )

        nickname_label = QLabel(
            "NICKNAME"
        )

        nickname_label.setObjectName(
            "fieldLabel"
        )

        account_layout.addWidget(
            nickname_label
        )

        account_layout.addSpacing(
            7
        )

        self.nickname_input = QLineEdit()

        self.nickname_input.setPlaceholderText(
            "What should we call you?"
        )

        self.nickname_input.setMaxLength(
            30
        )

        account_layout.addWidget(
            self.nickname_input
        )

        account_layout.addSpacing(
            7
        )

        nickname_hint = QLabel(
            "2–30 characters. Used when the app greets you."
        )

        nickname_hint.setObjectName(
            "hint"
        )

        nickname_hint.setWordWrap(
            True
        )

        account_layout.addWidget(
            nickname_hint
        )

        account_layout.addStretch()

        columns.addWidget(
            account_panel,
            1
        )

        # ----------------------------------------------------
        # RIGHT: PASSWORD
        # ----------------------------------------------------

        password_panel = QFrame()

        password_panel.setObjectName(
            "panel"
        )

        password_layout = QVBoxLayout(
            password_panel
        )

        password_layout.setContentsMargins(
            24,
            22,
            24,
            22
        )

        password_layout.setSpacing(
            0
        )

        password_title = QLabel(
            "SECURITY"
        )

        password_title.setObjectName(
            "sectionTitle"
        )

        password_layout.addWidget(
            password_title
        )

        password_layout.addSpacing(
            20
        )

        password_label = QLabel(
            "PASSWORD"
        )

        password_label.setObjectName(
            "fieldLabel"
        )

        password_layout.addWidget(
            password_label
        )

        password_layout.addSpacing(
            7
        )

        self.password_input = QLineEdit()

        self.password_input.setPlaceholderText(
            "Enter a strong password"
        )

        self.password_input.setEchoMode(
            QLineEdit.EchoMode.Password
        )

        password_layout.addWidget(
            self.password_input
        )

        password_layout.addSpacing(
            18
        )

        confirm_label = QLabel(
            "CONFIRM PASSWORD"
        )

        confirm_label.setObjectName(
            "fieldLabel"
        )

        password_layout.addWidget(
            confirm_label
        )

        password_layout.addSpacing(
            7
        )

        self.confirm_password_input = QLineEdit()

        self.confirm_password_input.setPlaceholderText(
            "Re-enter your password"
        )

        self.confirm_password_input.setEchoMode(
            QLineEdit.EchoMode.Password
        )

        password_layout.addWidget(
            self.confirm_password_input
        )

        password_layout.addSpacing(
            20
        )

        requirements_title = QLabel(
            "PASSWORD REQUIREMENTS"
        )

        requirements_title.setObjectName(
            "requirementsTitle"
        )

        password_layout.addWidget(
            requirements_title
        )

        password_layout.addSpacing(
            9
        )

        requirements_panel = QFrame()

        requirements_panel.setObjectName(
            "requirementsPanel"
        )

        requirements_grid = QGridLayout(
            requirements_panel
        )

        requirements_grid.setContentsMargins(
            14,
            11,
            14,
            11
        )

        requirements_grid.setHorizontalSpacing(
            18
        )

        requirements_grid.setVerticalSpacing(
            7
        )

        self.password_rule_labels = []

        rule_texts = [
            "8+ characters",
            "1 uppercase letter (A–Z)",
            "1 lowercase letter (a–z)",
            "1 number (0–9)",
            "1 special character (!@#$...)"
        ]

        for index, text in enumerate(rule_texts):

            rule_label = QLabel(
                "○  " + text
            )

            rule_label.setObjectName(
                "passwordRule"
            )

            self.password_rule_labels.append(
                rule_label
            )

            requirements_grid.addWidget(
                rule_label,
                index // 2,
                index % 2
            )

        password_layout.addWidget(
            requirements_panel
        )

        self.password_input.textChanged.connect(
            self.update_password_requirements
        )

        password_layout.addStretch()

        columns.addWidget(
            password_panel,
            1
        )

        layout.addLayout(
            columns,
            1
        )

        # ====================================================
        # BUTTONS
        # ====================================================

        layout.addSpacing(
            24
        )

        separator = QFrame()

        separator.setObjectName(
            "separator"
        )

        separator.setFrameShape(
            QFrame.Shape.HLine
        )

        layout.addWidget(
            separator
        )

        layout.addSpacing(
            18
        )

        button_layout = QHBoxLayout()

        button_layout.setSpacing(
            14
        )

        cancel_button = QPushButton(
            "CANCEL"
        )

        cancel_button.setObjectName(
            "cancelButton"
        )

        cancel_button.clicked.connect(
            self.reject
        )

        button_layout.addWidget(
            cancel_button
        )

        create_button = QPushButton(
            "CREATE ACCOUNT"
        )

        create_button.clicked.connect(
            self.create_account
        )

        button_layout.addWidget(
            create_button
        )

        layout.addLayout(
            button_layout
        )
    def update_password_requirements(self, password):

        checks = [
            len(password) >= 8,
            bool(re.search(r"[A-Z]", password)),
            bool(re.search(r"[a-z]", password)),
            bool(re.search(r"[0-9]", password)),
            bool(re.search(r"[^A-Za-z0-9]", password))
        ]

        for label, valid in zip(
            self.password_rule_labels,
            checks
        ):

            text = label.text()

            if text.startswith("✓  ") or text.startswith("○  "):
                text = text[3:]

            if valid:

                label.setObjectName(
                    "passwordRuleValid"
                )

                label.setText(
                    "✓  " + text
                )

            else:

                label.setObjectName(
                    "passwordRule"
                )

                label.setText(
                    "○  " + text
                )

            # Re-polish the label so the stylesheet responds immediately.
            label.style().unpolish(label)
            label.style().polish(label)
            label.update()

    def create_account(self):

        username = self.username_input.text().strip()
        password = self.password_input.text()
        confirm_password = self.confirm_password_input.text()
        nickname = self.nickname_input.text().strip()

        # ----------------------------------------------------
        # USERNAME VALIDATION
        # ----------------------------------------------------

        if not re.fullmatch(
            r"[A-Za-z0-9_]{3,20}",
            username
        ):

            QMessageBox.warning(
                self,
                "Invalid Username",
                "Username must be 3–20 characters long "
                "and contain only letters, numbers, or underscores."
            )

            self.username_input.setFocus()

            return

        # ----------------------------------------------------
        # PASSWORD VALIDATION
        # ----------------------------------------------------

        if len(password) < 8:

            QMessageBox.warning(
                self,
                "Invalid Password",
                "Password must contain at least 8 characters."
            )

            self.password_input.setFocus()

            return

        if not re.search(
            r"[A-Z]",
            password
        ):

            QMessageBox.warning(
                self,
                "Invalid Password",
                "Password must contain at least one uppercase letter."
            )

            self.password_input.setFocus()

            return

        if not re.search(
            r"[a-z]",
            password
        ):

            QMessageBox.warning(
                self,
                "Invalid Password",
                "Password must contain at least one lowercase letter."
            )

            self.password_input.setFocus()

            return

        if not re.search(
            r"[0-9]",
            password
        ):

            QMessageBox.warning(
                self,
                "Invalid Password",
                "Password must contain at least one number."
            )

            self.password_input.setFocus()

            return

        if not re.search(
            r"[^A-Za-z0-9]",
            password
        ):

            QMessageBox.warning(
                self,
                "Invalid Password",
                "Password must contain at least one special character."
            )

            self.password_input.setFocus()

            return

        # ----------------------------------------------------
        # CONFIRM PASSWORD
        # ----------------------------------------------------

        if password != confirm_password:

            QMessageBox.warning(
                self,
                "Password Mismatch",
                "The two passwords do not match."
            )

            self.confirm_password_input.clear()
            self.confirm_password_input.setFocus()

            return

        # ----------------------------------------------------
        # NICKNAME VALIDATION
        # ----------------------------------------------------

        if not 2 <= len(nickname) <= 30:

            QMessageBox.warning(
                self,
                "Invalid Nickname",
                "Nickname must be between 2 and 30 characters."
            )

            self.nickname_input.setFocus()

            return

        if not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9 _'-]*",
            nickname
        ):

            QMessageBox.warning(
                self,
                "Invalid Nickname",
                "Nickname may contain letters, numbers, spaces, "
                "apostrophes, hyphens, and underscores."
            )

            self.nickname_input.setFocus()

            return

        try:

            # ------------------------------------------------
            # CHECK USERNAME
            # ------------------------------------------------

            existing = self.db.one(
                """
                SELECT user_id
                FROM users
                WHERE username = %s
                """,
                (
                    username,
                )
            )

            if existing:

                QMessageBox.warning(
                    self,
                    "Username Taken",
                    "That username is already in use.\n\n"
                    "Please choose another username."
                )

                self.username_input.setFocus()

                return

            # ------------------------------------------------
            # FIND PLAYER ROLE
            # ------------------------------------------------

            player_role = self.db.one(
                """
                SELECT role_id
                FROM roles
                WHERE role_name = %s
                LIMIT 1
                """,
                (
                    ROLE_PLAYER,
                )
            )

            if not player_role:

                QMessageBox.critical(
                    self,
                    "Registration Error",
                    "The Player role could not be found in the database."
                )

                return

            # ------------------------------------------------
            # CREATE ACCOUNT
            # ------------------------------------------------

            user_id = self.db.execute(
                """
                INSERT INTO users
                    (
                        username,
                        nickname,
                        password,
                        money,
                        role_id,
                        is_active
                    )
                VALUES
                    (
                        %s,
                        %s,
                        %s,
                        %s,
                        %s,
                        1
                    )
                """,
                (
                    username,
                    nickname,
                    password,
                    Decimal("50000.00"),
                    player_role["role_id"]
                )
            )

            print(
                f"Created new Player account "
                f"{username} (user_id={user_id})"
            )

            self.accept()

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Registration Error",
                str(exc)
            )

# ============================================================
# PART BUTTON
# ============================================================

class PartButton(QPushButton):

    def __init__(self, part):

        super().__init__()

        self.part = part

        self.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.setMinimumHeight(104)

        self.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed
        )

        price = Decimal(str(part.get("price", 0) or 0))
        hp = int(part.get("hp_bonus", 0) or 0)
        weight = int(part.get("weight_change", 0) or 0)
        speed = int(part.get("top_speed_bonus", 0) or 0)
        accel = Decimal(str(part.get("acceleration_bonus", 0) or 0))
        stock = int(part.get("stock", 0) or 0)
        manufacturer = str(part.get("manufacturer") or "OEM")

        is_stock = str(part.get("part_name", "")).lower().startswith("stock ")

        price_text = "FREE" if is_stock or price == 0 else money(price)

        self.setText(
            f"{part['part_name']}\n"
            f"{manufacturer}  •  {price_text}\n"
            f"HP {hp:+d}  •  Weight {weight:+d} kg  •  "
            f"Top Speed {speed:+d} km/h  •  Accel {accel:+.2f}\n"
            f"Stock: {stock}"
        )

        self.setStyleSheet(
            """
            QPushButton {
                background:#17131e;
                color:#f3efff;
                border:1px solid #30263d;
                border-radius:9px;
                padding:8px 10px;
                text-align:left;
                font-size:11px;
            }
            QPushButton:hover {
                background:#211a2d;
                border:1px solid #6d4d91;
            }
            """
        )


# ============================================================
# PURCHASE HISTORY
# ============================================================

class PurchaseHistoryDialog(QDialog):

    def __init__(
        self,
        db,
        user_id,
        username,
        parent=None
    ):

        super().__init__(
            parent
        )

        self.db = db
        self.user_id = user_id

        self.setWindowTitle(
            f"Purchase History — {username}"
        )

        self.resize(
            950,
            600
        )

        self.setStyleSheet(
            """
            QDialog {
                background:;#09070d
                color:#e8edf2;
            }

            QLabel {
                color:#e8edf2;
            }

            QTableWidget {
                background:#181520;
                color:#e8edf2;
                border:1px solid #454c55;
                gridline-color:#3d444c;
                selection-background-color:#66502f;
                selection-color:white;
            }

            QHeaderView::section {
                background:#30363e;
                color:#f0f2f4;
                padding:8px;
                border:1px solid #454c55;
                font-weight:bold;
            }

            QPushButton {
                background:#251d31;
                color:white;
                border:1px solid #68517f;
                border-radius:8px;
                padding:9px 18px;
                font-weight:bold;
            }

            QPushButton:hover {
                background:#4a5662;
            }
            """
        )

        layout = QVBoxLayout(
            self
        )

        title = QLabel(
            "PURCHASE HISTORY"
        )

        title.setFont(
            QFont(
                "Segoe UI",
                20,
                QFont.Weight.Bold
            )
        )

        title.setStyleSheet(
            "color:#c4b5fd;"
        )

        layout.addWidget(
            title
        )

        self.summary_label = QLabel()

        self.summary_label.setStyleSheet(
            "color:#b8afc4;font-size:14px;padding:5px;"
        )

        layout.addWidget(
            self.summary_label
        )

        self.table = QTableWidget()

        self.table.setColumnCount(
            6
        )

        self.table.setHorizontalHeaderLabels(
            [
                "Part",
                "Category",
                "Quantity",
                "Amount Paid",
                "Purchase Date",
                "Purchase ID"
            ]
        )

        self.table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        self.table.horizontalHeader().setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.Stretch
        )

        for index in range(1, 6):

            self.table.horizontalHeader().setSectionResizeMode(
                index,
                QHeaderView.ResizeMode.ResizeToContents
            )

        layout.addWidget(
            self.table,
            1
        )

        bottom = QHBoxLayout()

        self.total_label = QLabel()

        self.total_label.setFont(
            QFont(
                "Segoe UI",
                14,
                QFont.Weight.Bold
            )
        )

        self.total_label.setStyleSheet(
            "color:#c4b5fd;"
        )

        bottom.addWidget(
            self.total_label
        )

        bottom.addStretch()

        refresh = QPushButton(
            "REFRESH"
        )

        refresh.clicked.connect(
            self.load_history
        )

        bottom.addWidget(
            refresh
        )

        close = QPushButton(
            "CLOSE"
        )

        close.clicked.connect(
            self.accept
        )

        bottom.addWidget(
            close
        )

        layout.addLayout(
            bottom
        )

        self.load_history()

    def load_history(self):

        try:

            rows = self.db.query(
                """
                SELECT
                    pu.purchase_id,
                    p.part_name,
                    c.category_name,
                    pu.quantity,
                    pu.total_price,
                    pu.purchase_date
                FROM purchases pu
                JOIN parts p
                    ON p.part_id = pu.part_id
                JOIN categories c
                    ON c.category_id = p.category_id
                WHERE pu.user_id = %s
                ORDER BY pu.purchase_date DESC,
                         pu.purchase_id DESC
                """,
                (
                    self.user_id,
                )
            )

            self.table.setRowCount(
                len(rows)
            )

            total_spent = Decimal("0")
            total_items = 0

            for r, row in enumerate(rows):

                quantity = int(
                    row["quantity"] or 0
                )

                amount = Decimal(
                    str(
                        row["total_price"] or 0
                    )
                )

                total_spent += amount
                total_items += quantity

                date = row["purchase_date"]

                date_text = (
                    date.strftime(
                        "%d-%m-%Y %H:%M"
                    )
                    if date
                    else "-"
                )

                values = [
                    row["part_name"],
                    row["category_name"],
                    quantity,
                    money(amount),
                    date_text,
                    row["purchase_id"]
                ]

                for c, value in enumerate(values):

                    self.table.setItem(
                        r,
                        c,
                        QTableWidgetItem(
                            str(value)
                        )
                    )

            self.summary_label.setText(
                f"Total purchases: {len(rows)}    •    "
                f"Items purchased: {total_items}"
            )

            self.total_label.setText(
                f"TOTAL SPENT: {money(total_spent)}"
            )

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Purchase History Error",
                str(exc)
            )


# ============================================================
# MANAGEMENT
# ============================================================

class ManagementDialog(QDialog):

    def __init__(
        self,
        db,
        role_name,
        parent=None
    ):

        super().__init__(
            parent
        )

        self.db = db
        self.role_name = role_name

        self.setWindowTitle(
            f"{role_name} Management"
        )

        self.resize(
            1050,
            680
        )

        self.setStyleSheet(
            """
            QDialog {
                background:#09070d;
                color:#e8edf2;
            }

            QTabWidget::pane {
                border:1px solid #424a54;
                background:#181520;
            }

            QTabBar::tab {
                background:#2d333a;
                color:#cfd5db;
                padding:10px 18px;
                border:1px solid #424a54;
            }

            QTabBar::tab:selected {
                background:#8b5cf6;
                color:white;
            }

            QTableWidget {
                background:#181520;
                color:#e8edf2;
                gridline-color:#3d444c;
                border:1px solid #424a54;
            }

            QHeaderView::section {
                background:#30363e;
                color:white;
                padding:8px;
                font-weight:bold;
            }

            QPushButton {
                background:#251d31;
                color:white;
                border:1px solid #68517f;
                border-radius:8px;
                padding:9px 14px;
                font-weight:bold;
            }

            QPushButton:hover {
                background:#4a5662;
            }
            """
        )

        layout = QVBoxLayout(
            self
        )

        title = QLabel(
            f"{role_name.upper()} MANAGEMENT"
        )

        title.setFont(
            QFont(
                "Segoe UI",
                18,
                QFont.Weight.Bold
            )
        )

        title.setStyleSheet(
            "color:#c4b5fd;"
        )

        layout.addWidget(
            title
        )

        self.tabs = QTabWidget()

        layout.addWidget(
            self.tabs
        )

        if role_name in (
            ROLE_SHOP_MANAGER,
            ROLE_ADMIN
        ):

            self.build_shop_tab()
            self.build_parts_tab()

        if role_name == ROLE_ADMIN:

            self.build_users_tab()
            self.build_roles_tab()

    def build_shop_tab(self):

        tab = QWidget()

        layout = QVBoxLayout(
            tab
        )

        self.shop_table = QTableWidget()

        layout.addWidget(
            self.shop_table
        )

        buttons = QHBoxLayout()

        restock = QPushButton(
            "RESTOCK SELECTED"
        )

        restock.clicked.connect(
            self.restock_selected
        )

        buttons.addWidget(
            restock
        )

        price = QPushButton(
            "CHANGE PRICE"
        )

        price.clicked.connect(
            self.change_price
        )

        buttons.addWidget(
            price
        )

        refresh = QPushButton(
            "REFRESH"
        )

        refresh.clicked.connect(
            self.load_shop_inventory
        )

        buttons.addWidget(
            refresh
        )

        layout.addLayout(
            buttons
        )

        self.tabs.addTab(
            tab,
            "Shop Inventory"
        )

        self.load_shop_inventory()

    def load_shop_inventory(self):

        rows = self.db.query(
            """
            SELECT
                si.inventory_id,
                si.part_id,
                p.part_name,
                p.price,
                si.stock
            FROM shop_inventory si
            JOIN parts p
                ON p.part_id = si.part_id
            WHERE p.is_active = 1
            ORDER BY p.part_id
            """
        )

        self.shop_table.setColumnCount(
            5
        )

        self.shop_table.setRowCount(
            len(rows)
        )

        self.shop_table.setHorizontalHeaderLabels(
            [
                "Inventory ID",
                "Part ID",
                "Part",
                "Price",
                "Stock"
            ]
        )

        for r, row in enumerate(rows):

            values = [
                row["inventory_id"],
                row["part_id"],
                row["part_name"],
                money(row["price"]),
                row["stock"]
            ]

            for c, value in enumerate(values):

                self.shop_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(
                        str(value)
                    )
                )

        self.shop_table.resizeColumnsToContents()

    def restock_selected(self):

        row = self.shop_table.currentRow()

        if row < 0:

            QMessageBox.warning(
                self,
                "No Selection",
                "Select a part first."
            )

            return

        part_id = int(
            self.shop_table.item(
                row,
                1
            ).text()
        )

        amount, ok = QInputDialog.getInt(
            self,
            "Restock",
            "Units to add:",
            10,
            1,
            1000
        )

        if not ok:
            return

        try:

            self.db.execute(
                """
                UPDATE shop_inventory
                SET stock = stock + %s
                WHERE part_id = %s
                """,
                (
                    amount,
                    part_id
                )
            )

            self.load_shop_inventory()

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Error",
                str(exc)
            )

    def change_price(self):

        row = self.shop_table.currentRow()

        if row < 0:

            QMessageBox.warning(
                self,
                "No Selection",
                "Select a part first."
            )

            return

        part_id = int(
            self.shop_table.item(
                row,
                1
            ).text()
        )

        current = (
            self.shop_table.item(
                row,
                3
            ).text()
            .replace("₹", "")
            .replace(",", "")
        )

        try:
            current = float(current)
        except Exception:
            current = 0

        price, ok = QInputDialog.getDouble(
            self,
            "Change Price",
            "New price:",
            current,
            0,
            100000000,
            2
        )

        if not ok:
            return

        try:

            self.db.execute(
                """
                UPDATE parts
                SET price = %s
                WHERE part_id = %s
                """,
                (
                    price,
                    part_id
                )
            )

            self.load_shop_inventory()

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Error",
                str(exc)
            )

    def build_parts_tab(self):

        tab = QWidget()

        layout = QVBoxLayout(
            tab
        )

        self.parts_table = QTableWidget()

        self.parts_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.parts_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )

        layout.addWidget(
            self.parts_table
        )

        buttons = QHBoxLayout()

        refresh = QPushButton(
            "REFRESH PARTS"
        )

        refresh.clicked.connect(
            self.load_parts_table
        )

        buttons.addWidget(
            refresh
        )

        # Parts are view-only for Shop Managers.
        # Administrators can edit catalog information.
        if self.role_name == ROLE_ADMIN:

            edit = QPushButton(
                "EDIT SELECTED PART"
            )

            edit.clicked.connect(
                self.edit_selected_part
            )

            buttons.addWidget(
                edit
            )

            deactivate = QPushButton(
                "DEACTIVATE SELECTED"
            )

            deactivate.clicked.connect(
                self.deactivate_selected_part
            )

            buttons.addWidget(
                deactivate
            )

            activate = QPushButton(
                "ACTIVATE SELECTED"
            )

            activate.clicked.connect(
                self.activate_selected_part
            )

            buttons.addWidget(
                activate
            )

        layout.addLayout(
            buttons
        )

        self.tabs.addTab(
            tab,
            "Parts"
        )

        self.load_parts_table()

    def load_parts_table(self):

        rows = self.db.query(
            """
            SELECT
                p.part_id,
                c.category_name,
                p.part_name,
                p.manufacturer,
                p.price,
                p.hp_bonus,
                p.weight_change,
                p.top_speed_bonus,
                p.acceleration_bonus,
                p.is_active
            FROM parts p
            JOIN categories c
                ON c.category_id = p.category_id
            ORDER BY p.part_id
            """
        )

        self.parts_table.setColumnCount(
            10
        )

        self.parts_table.setRowCount(
            len(rows)
        )

        self.parts_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Category",
                "Part",
                "Manufacturer",
                "Price",
                "HP",
                "Weight",
                "Speed",
                "Acceleration",
                "Status"
            ]
        )

        for r, row in enumerate(rows):

            values = [
                row["part_id"],
                row["category_name"],
                row["part_name"],
                row["manufacturer"],
                money(row["price"]),
                row["hp_bonus"],
                row["weight_change"],
                row["top_speed_bonus"],
                row["acceleration_bonus"],
                "ACTIVE" if int(row["is_active"]) == 1 else "INACTIVE"
            ]

            for c, value in enumerate(values):

                self.parts_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(
                        str(value)
                    )
                )

        self.parts_table.resizeColumnsToContents()

    def edit_selected_part(self):

        if self.role_name != ROLE_ADMIN:
            return

        row = self.parts_table.currentRow()

        if row < 0:

            QMessageBox.warning(
                self,
                "No Selection",
                "Select a part first."
            )

            return

        part_id = int(
            self.parts_table.item(
                row,
                0
            ).text()
        )

        part = self.db.one(
            """
            SELECT
                part_id,
                part_name,
                manufacturer,
                price,
                hp_bonus,
                weight_change,
                top_speed_bonus,
                acceleration_bonus
            FROM parts
            WHERE part_id = %s
            """,
            (
                part_id,
            )
        )

        if not part:

            QMessageBox.warning(
                self,
                "Part Not Found",
                "The selected part no longer exists."
            )

            self.load_parts_table()
            return

        dialog = QDialog(
            self
        )

        dialog.setWindowTitle(
            "Edit Part"
        )

        dialog.resize(
            430,
            420
        )

        form = QVBoxLayout(
            dialog
        )

        title = QLabel(
            f"EDIT PART #{part_id}"
        )

        title.setFont(
            QFont(
                "Segoe UI",
                16,
                QFont.Weight.Bold
            )
        )

        title.setStyleSheet(
            "color:#c4b5fd;"
        )

        form.addWidget(
            title
        )

        name_edit = QLineEdit(
            str(part["part_name"] or "")
        )
        manufacturer_edit = QLineEdit(
            str(part["manufacturer"] or "")
        )

        form.addWidget(
            QLabel("Part Name")
        )
        form.addWidget(
            name_edit
        )

        form.addWidget(
            QLabel("Manufacturer")
        )
        form.addWidget(
            manufacturer_edit
        )

        hp_box = QLineEdit(
            str(part["hp_bonus"] or 0)
        )
        weight_box = QLineEdit(
            str(part["weight_change"] or 0)
        )
        speed_box = QLineEdit(
            str(part["top_speed_bonus"] or 0)
        )
        accel_box = QLineEdit(
            str(part["acceleration_bonus"] or 0)
        )

        for label, widget in (
            ("HP Bonus", hp_box),
            ("Weight Change", weight_box),
            ("Top Speed Bonus", speed_box),
            ("Acceleration Bonus", accel_box)
        ):

            form.addWidget(
                QLabel(label)
            )
            form.addWidget(
                widget
            )

        note = QLabel(
            "Price is managed under Shop Inventory.\n"
            "Category and rendering asset fields are protected."
        )

        note.setStyleSheet(
            "color:#9ca3af;"
        )

        form.addWidget(
            note
        )

        buttons = QHBoxLayout()

        save = QPushButton(
            "SAVE CHANGES"
        )

        cancel = QPushButton(
            "CANCEL"
        )

        buttons.addWidget(
            save
        )
        buttons.addWidget(
            cancel
        )

        form.addLayout(
            buttons
        )

        cancel.clicked.connect(
            dialog.reject
        )

        def save_changes():

            name = name_edit.text().strip()
            manufacturer = manufacturer_edit.text().strip()

            if not name:

                QMessageBox.warning(
                    dialog,
                    "Invalid Part",
                    "Part name cannot be empty."
                )

                return

            try:

                hp = int(hp_box.text().strip())
                weight = int(weight_box.text().strip())
                speed = int(speed_box.text().strip())
                accel = Decimal(
                    accel_box.text().strip()
                )

            except Exception:

                QMessageBox.warning(
                    dialog,
                    "Invalid Values",
                    "Performance values must be valid numbers."
                )

                return

            if hp < 0 or speed < 0:

                QMessageBox.warning(
                    dialog,
                    "Invalid Values",
                    "HP and Top Speed bonuses cannot be negative."
                )

                return

            try:

                self.db.execute(
                    """
                    UPDATE parts
                    SET
                        part_name = %s,
                        manufacturer = %s,
                        hp_bonus = %s,
                        weight_change = %s,
                        top_speed_bonus = %s,
                        acceleration_bonus = %s
                    WHERE part_id = %s
                    """,
                    (
                        name,
                        manufacturer,
                        hp,
                        weight,
                        speed,
                        accel,
                        part_id
                    )
                )

                dialog.accept()

            except Exception as exc:

                QMessageBox.critical(
                    dialog,
                    "Update Error",
                    str(exc)
                )

        save.clicked.connect(
            save_changes
        )

        if dialog.exec():

            self.load_parts_table()

    def deactivate_selected_part(self):

        if self.role_name != ROLE_ADMIN:
            return

        row = self.parts_table.currentRow()

        if row < 0:

            QMessageBox.warning(
                self,
                "No Selection",
                "Select a part first."
            )

            return

        part_id = int(self.parts_table.item(row, 0).text())
        part_name = self.parts_table.item(row, 2).text()
        status = self.parts_table.item(row, 9).text()

        if status == "INACTIVE":

            QMessageBox.information(
                self,
                "Already Inactive",
                f"'{part_name}' is already inactive."
            )
            return

        answer = QMessageBox.question(
            self,
            "Deactivate Part",
            f"Deactivate '{part_name}'?\n\n"
            "The part will disappear from the shop and customization choices, "
            "but purchase history, inventory, and installed vehicle records "
            "will be preserved.",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:

            self.db.execute(
                """
                UPDATE parts
                SET is_active = 0
                WHERE part_id = %s
                """,
                (part_id,)
            )

            self.load_parts_table()

            QMessageBox.information(
                self,
                "Part Deactivated",
                f"'{part_name}' is now inactive.\n\n"
                "Existing purchase, inventory, and vehicle records were preserved."
            )

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Deactivate Error",
                str(exc)
            )

    def activate_selected_part(self):

        if self.role_name != ROLE_ADMIN:
            return

        row = self.parts_table.currentRow()

        if row < 0:

            QMessageBox.warning(
                self,
                "No Selection",
                "Select a part first."
            )

            return

        part_id = int(self.parts_table.item(row, 0).text())
        part_name = self.parts_table.item(row, 2).text()
        status = self.parts_table.item(row, 9).text()

        if status == "ACTIVE":

            QMessageBox.information(
                self,
                "Already Active",
                f"'{part_name}' is already active."
            )
            return

        answer = QMessageBox.question(
            self,
            "Activate Part",
            f"Activate '{part_name}'?\n\n"
            "The part will become available again in the shop and customization choices."
            ,
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        try:

            self.db.execute(
                """
                UPDATE parts
                SET is_active = 1
                WHERE part_id = %s
                """,
                (part_id,)
            )

            self.load_parts_table()

            QMessageBox.information(
                self,
                "Part Activated",
                f"'{part_name}' is active again and can be sold/selected."
            )

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Activate Error",
                str(exc)
            )

    def build_users_tab(self):

        tab = QWidget()

        layout = QVBoxLayout(
            tab
        )

        self.users_table = QTableWidget()

        layout.addWidget(
            self.users_table
        )

        change_role = QPushButton(
            "CHANGE SELECTED USER ROLE"
        )

        change_role.clicked.connect(
            self.change_user_role
        )

        layout.addWidget(
            change_role
        )

        refresh = QPushButton(
            "REFRESH USERS"
        )

        refresh.clicked.connect(
            self.load_users
        )

        layout.addWidget(
            refresh
        )

        self.tabs.addTab(
            tab,
            "Users"
        )

        self.load_users()

    def load_users(self):

        rows = self.db.query(
            """
            SELECT
                u.user_id,
                u.username,
                u.money,
                r.role_name
            FROM users u
            JOIN roles r
                ON r.role_id = u.role_id
            ORDER BY u.user_id
            """
        )

        self.users_table.setColumnCount(
            4
        )

        self.users_table.setRowCount(
            len(rows)
        )

        self.users_table.setHorizontalHeaderLabels(
            [
                "User ID",
                "Username",
                "Money",
                "Role"
            ]
        )

        for r, row in enumerate(rows):

            values = [
                row["user_id"],
                row["username"],
                money(row["money"]),
                row["role_name"]
            ]

            for c, value in enumerate(values):

                self.users_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(
                        str(value)
                    )
                )

        self.users_table.resizeColumnsToContents()

    def change_user_role(self):

        row = self.users_table.currentRow()

        if row < 0:
            return

        user_id = int(
            self.users_table.item(
                row,
                0
            ).text()
        )

        roles = self.db.query(
            """
            SELECT role_id, role_name
            FROM roles
            ORDER BY role_id
            """
        )

        names = [
            r["role_name"]
            for r in roles
        ]

        selected, ok = QInputDialog.getItem(
            self,
            "Change Role",
            "New role:",
            names,
            0,
            False
        )

        if not ok:
            return

        role_id = next(
            r["role_id"]
            for r in roles
            if r["role_name"] == selected
        )

        try:

            self.db.execute(
                """
                UPDATE users
                SET role_id = %s
                WHERE user_id = %s
                """,
                (
                    role_id,
                    user_id
                )
            )

            self.load_users()

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Error",
                str(exc)
            )

    def build_roles_tab(self):

        tab = QWidget()

        layout = QVBoxLayout(
            tab
        )

        title = QLabel(
            "ROLE-BASED ACCESS CONTROL"
        )

        title.setFont(
            QFont(
                "Segoe UI",
                16,
                QFont.Weight.Bold
            )
        )

        title.setStyleSheet(
            "color:#c4b5fd; padding:4px 0;"
        )

        layout.addWidget(
            title
        )

        description = QLabel(
            "The four core roles define what each type of account can access in the Car Customizer system. "
            "These system roles are protected and are not renamed or deleted from this screen."
        )

        description.setWordWrap(
            True
        )

        description.setStyleSheet(
            "color:#9ca3af; padding:0 0 8px 0;"
        )

        layout.addWidget(
            description
        )

        self.roles_table = QTableWidget()

        self.roles_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )

        self.roles_table.setSelectionMode(
            QTableWidget.SelectionMode.SingleSelection
        )

        self.roles_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )

        self.roles_table.setAlternatingRowColors(
            True
        )

        layout.addWidget(
            self.roles_table
        )

        refresh = QPushButton(
            "REFRESH ROLES"
        )

        refresh.setMinimumHeight(
            42
        )

        refresh.clicked.connect(
            self.load_roles
        )

        layout.addWidget(
            refresh
        )

        self.tabs.addTab(
            tab,
            "Roles"
        )

        self.load_roles()

    def load_roles(self):

        rows = self.db.query(
            """
            SELECT role_id, role_name
            FROM roles
            ORDER BY role_id
            """
        )

        descriptions = {
            ROLE_GUEST:
                "Browse and preview vehicle customization.",

            ROLE_PLAYER:
                "Purchase and install parts and view purchase history.",

            ROLE_SHOP_MANAGER:
                "Manage shop inventory and view the parts catalog.",

            ROLE_ADMIN:
                "Full system administration and management access."
        }

        permissions = {
            ROLE_GUEST:
                "Browse • Preview",

            ROLE_PLAYER:
                "Browse • Preview • Buy / Install • Purchase History",

            ROLE_SHOP_MANAGER:
                "Player Access • Shop Inventory • Parts View",

            ROLE_ADMIN:
                "Manager Access • Users • Parts Management • Roles"
        }

        self.roles_table.setColumnCount(
            4
        )

        self.roles_table.setRowCount(
            len(rows)
        )

        self.roles_table.setHorizontalHeaderLabels(
            [
                "Role ID",
                "Role Name",
                "Description",
                "Permissions"
            ]
        )

        for r, row in enumerate(rows):

            role_name = str(
                row["role_name"]
            )

            values = [
                row["role_id"],
                role_name,
                descriptions.get(
                    role_name,
                    "System role."
                ),
                permissions.get(
                    role_name,
                    "Defined by system."
                )
            ]

            for c, value in enumerate(values):

                self.roles_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(
                        str(value)
                    )
                )

        self.roles_table.setColumnWidth(
            0,
            80
        )

        self.roles_table.setColumnWidth(
            1,
            170
        )

        self.roles_table.setColumnWidth(
            2,
            330
        )

        self.roles_table.setColumnWidth(
            3,
            430
        )

        self.roles_table.horizontalHeader().setStretchLastSection(
            True
        )

        self.roles_table.verticalHeader().setDefaultSectionSize(
            48
        )


# ============================================================
# VEHICLE SHOP / MY CARS
# ============================================================

class VehicleShopDialog(QDialog):

    def __init__(self, db, user, current_vehicle_id, parent=None):

        super().__init__(parent)

        self.db = db
        self.user = user
        self.current_vehicle_id = current_vehicle_id
        self.selected_vehicle_id = None

        self.setWindowTitle("My Cars / Car Shop")
        self.resize(900, 600)

        self.setStyleSheet(
            """
            QDialog { background:#09070d; color:#e8edf2; }
            QLabel { color:#e8edf2; background:transparent; }
            QLabel#title { color:#c4b5fd; font-size:20px; font-weight:bold; }
            QLabel#money { color:#c4b5fd; font-size:14px; font-weight:bold; }
            QListWidget { background:#121019; border:1px solid #30263d; border-radius:10px; }
            QListWidget::item { padding:12px; border-bottom:1px solid #2a2333; }
            QListWidget::item:selected { background:#211a2d; }
            QPushButton {
                background:#251d31; color:white; border:1px solid #68517f;
                border-radius:8px; padding:9px 15px; font-weight:bold;
            }
            QPushButton:hover { background:#4a3860; }
            QPushButton#buy { background:#8b5cf6; border-color:#c4b5fd; }
            QPushButton#buy:hover { background:#a78bfa; }
            QPushButton:disabled { background:#211c29; color:#81778d; border-color:#40354d; }
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 22)
        layout.setSpacing(12)

        title = QLabel("MY CARS / CAR SHOP")
        title.setObjectName("title")
        layout.addWidget(title)

        self.money_label = QLabel()
        self.money_label.setObjectName("money")
        layout.addWidget(self.money_label)

        hint = QLabel(
            "Select a car you own to switch to it, or purchase another model. "
            "Each purchased car gets its own customization and installed parts."
        )
        hint.setStyleSheet("color:#9f98a8;font-size:12px;")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.list = QListWidget()
        layout.addWidget(self.list, 1)

        buttons = QHBoxLayout()
        self.select_button = QPushButton("SELECT CAR")
        self.select_button.clicked.connect(self.select_car)
        buttons.addWidget(self.select_button)

        self.buy_button = QPushButton("BUY CAR")
        self.buy_button.setObjectName("buy")
        self.buy_button.clicked.connect(self.buy_car)
        buttons.addWidget(self.buy_button)

        close = QPushButton("CLOSE")
        close.clicked.connect(self.reject)
        buttons.addWidget(close)

        layout.addLayout(buttons)

        self.load_cars()
        self.list.currentRowChanged.connect(self.update_buttons)
        self.update_buttons()

    def load_cars(self):

        self.list.clear()

        if not self.user.get("user_id"):
            self.money_label.setText("Guest accounts cannot buy cars.")
            return

        user_id = self.user["user_id"]
        self.money_label.setText(f"Money: {money(self.user.get('money', 0))}")

        models = self.db.query(
            """
            SELECT
                cm.model_id,
                cm.model_name,
                m.manufacturer_name,
                cm.model_year,
                cm.base_hp,
                cm.base_weight,
                cm.base_top_speed,
                cm.base_acceleration
            FROM car_models cm
            JOIN manufacturers m ON m.manufacturer_id = cm.manufacturer_id
            ORDER BY cm.model_id
            """
        )

        owned = self.db.query(
            """
            SELECT
                v.vehicle_id,
                v.model_id,
                v.nickname,
                cm.model_name
            FROM vehicles v
            JOIN car_models cm ON cm.model_id = v.model_id
            WHERE v.user_id = %s
            ORDER BY v.vehicle_id
            """,
            (user_id,)
        )

        owned_by_model = {}
        for vehicle in owned:
            owned_by_model.setdefault(int(vehicle["model_id"]), []).append(vehicle)

        for model in models:
            model_id = int(model["model_id"])
            price = CAR_PRICES.get(model["model_name"], Decimal("50000.00"))
            vehicles = owned_by_model.get(model_id, [])

            if vehicles:
                ownership = "OWNED: " + ", ".join(
                    v["nickname"] or model["model_name"] for v in vehicles
                )
            else:
                ownership = "Not owned"

            price_text = "STARTER / FREE" if price == 0 else money(price)

            item = QListWidgetItem(
                f"{model['manufacturer_name']} {model['model_name']} ({model['model_year']})\n"
                f"Price: {price_text}  •  {ownership}\n"
                f"Base: {model['base_hp']} HP  •  {model['base_weight']} kg  •  "
                f"{model['base_top_speed']} km/h  •  Accel {model['base_acceleration']}"
            )
            item.setData(Qt.ItemDataRole.UserRole, model_id)
            item.setData(Qt.ItemDataRole.UserRole + 1, vehicles)
            item.setData(Qt.ItemDataRole.UserRole + 2, price)
            self.list.addItem(item)

    def update_buttons(self):

        item = self.list.currentItem()
        if item is None or not self.user.get("user_id"):
            self.select_button.setEnabled(False)
            self.buy_button.setEnabled(False)
            return

        vehicles = item.data(Qt.ItemDataRole.UserRole + 1) or []
        price = item.data(Qt.ItemDataRole.UserRole + 2) or Decimal("0")

        self.select_button.setEnabled(bool(vehicles))
        self.buy_button.setEnabled(price > 0)

        if price > 0:
            self.buy_button.setText(f"BUY — {money(price)}")
        else:
            self.buy_button.setText("STARTER CAR")
            self.buy_button.setEnabled(False)

    def selected_model_data(self):
        item = self.list.currentItem()
        if item is None:
            return None, [], Decimal("0")
        return (
            int(item.data(Qt.ItemDataRole.UserRole)),
            item.data(Qt.ItemDataRole.UserRole + 1) or [],
            item.data(Qt.ItemDataRole.UserRole + 2) or Decimal("0")
        )

    def select_car(self):

        model_id, vehicles, _ = self.selected_model_data()
        if not vehicles:
            return

        # If a model has multiple copies, choose the first one here.
        # The UI can later be extended with individual vehicle selection.
        vehicle = vehicles[0]
        self.selected_vehicle_id = int(vehicle["vehicle_id"])
        self.accept()

    def buy_car(self):

        model_id, vehicles, price = self.selected_model_data()
        if model_id is None or price <= 0:
            return

        user_id = self.user["user_id"]
        cursor = None

        try:
            self.db.ensure_connection()
            self.db.conn.autocommit = False
            self.db.conn.start_transaction()
            cursor = self.db.conn.cursor(dictionary=True)

            cursor.execute(
                "SELECT money FROM users WHERE user_id = %s FOR UPDATE",
                (user_id,)
            )
            user_row = cursor.fetchone()
            if not user_row:
                raise RuntimeError("Player account was not found.")

            current_money = Decimal(str(user_row["money"] or 0))
            if current_money < price:
                raise RuntimeError(
                    f"Not enough money.\\n\\n"
                    f"Your money: {money(current_money)}\\n"
                    f"Car price: {money(price)}"
                )

            cursor.execute(
                """
                SELECT model_name
                FROM car_models
                WHERE model_id = %s
                FOR UPDATE
                """,
                (model_id,)
            )
            model = cursor.fetchone()
            if not model:
                raise RuntimeError("Selected car model was not found.")

            cursor.execute(
                """
                UPDATE users
                SET money = money - %s
                WHERE user_id = %s
                """,
                (price, user_id)
            )

            cursor.execute(
                """
                INSERT INTO vehicles (user_id, model_id, nickname)
                VALUES (%s, %s, %s)
                """,
                (user_id, model_id, f"My {model['model_name']}")
            )
            vehicle_id = cursor.lastrowid

            # Every new car starts with the stock part in every category.
            cursor.execute(
                """
                INSERT INTO vehicle_parts (vehicle_id, category_id, part_id)
                SELECT %s, c.category_id, p.part_id
                FROM categories c
                JOIN parts p
                    ON p.category_id = c.category_id
                WHERE LOWER(p.part_name) LIKE 'stock %%'
                  AND p.is_active = 1
                """,
                (vehicle_id,)
            )

            self.db.conn.commit()
            self.db.conn.autocommit = True

            self.selected_vehicle_id = int(vehicle_id)
            self.user["money"] = current_money - price

            QMessageBox.information(
                self,
                "Car Purchased",
                f"{model['model_name']} was purchased successfully.\n\n"
                f"Amount paid: {money(price)}\n"
                "The car starts with stock parts and can now be customized separately."
            )

            self.load_cars()
            # Keep the newly purchased vehicle selected by returning it immediately.
            self.accept()

        except Exception as exc:
            try:
                self.db.conn.rollback()
                self.db.conn.autocommit = True
            except Exception:
                pass

            QMessageBox.critical(
                self,
                "Car Purchase Error",
                f"The car could not be purchased.\\n\\n{exc}"
            )

        finally:
            if cursor is not None:
                try:
                    cursor.close()
                except Exception:
                    pass


# ============================================================
# GARAGE WINDOW
# ============================================================

class GarageWindow(QMainWindow):

    def __init__(
        self,
        db,
        user,
        switch_user_callback
    ):

        super().__init__()

        self.db = db
        self.user = user
        self.switch_user_callback = switch_user_callback

        self.current_vehicle = None

        self.categories = []
        self.parts = []

        self.installed_parts = {}
        self.preview_parts = {}

        self.current_category_id = None
        self.selected_part = None

        self.role_name = (
            user.get(
                "role_name"
            )
            or ROLE_GUEST
        )

        self.setWindowTitle(
            "Car Customizer Garage"
        )

        self.resize(
            1450,
            850
        )

        self.setMinimumSize(
            1100,
            700
        )

        self.load_user_and_vehicle()

        self.load_categories()

        self.load_installed_parts()

        self.build_ui()

        self.refresh_user_display()

        self.select_first_category()

        self.refresh_car_preview()

    # ========================================================
    # VEHICLE
    # ========================================================

    def load_user_and_vehicle(self):

        if not self.user.get("user_id"):

            self.current_vehicle = {
                "vehicle_id": None,
                "user_id": None,
                "nickname": "Guest Vehicle",
                "model_id": 1,
                "model_name": "Guest Preview",
                "base_hp": 100,
                "base_weight": 1000,
                "base_top_speed": 150,
                "base_acceleration": Decimal("10")
            }

            return

        user_id = self.user["user_id"]

        self.current_vehicle = self.db.one(
            """
            SELECT
                v.vehicle_id,
                v.user_id,
                v.nickname,
                v.model_id,
                cm.model_name,
                cm.base_hp,
                cm.base_weight,
                cm.base_top_speed,
                cm.base_acceleration
            FROM vehicles v
            JOIN car_models cm
                ON cm.model_id = v.model_id
            WHERE v.user_id = %s
            ORDER BY v.vehicle_id
            LIMIT 1
            """,
            (
                user_id,
            )
        )
        if self.current_vehicle:

            return

        # ----------------------------------------------------
        # CREATE DEFAULT VEHICLE
        # ----------------------------------------------------

        model = self.db.one(
            """
            SELECT
                model_id,
                model_name,
                base_hp,
                base_weight,
                base_top_speed,
                base_acceleration
            FROM car_models
            ORDER BY model_id
            LIMIT 1
            """
        )

        if not model:

            raise RuntimeError(
                "No car model exists in the car_models table."
            )

        vehicle_id = self.db.execute(
            """
            INSERT INTO vehicles
                (
                    user_id,
                    model_id,
                    nickname
                )
            VALUES
                (
                    %s,
                    %s,
                    %s
                )
            """,
            (
                user_id,
                model["model_id"],
                f"{self.user['username'].title()}'s Car"
            )
        )

        print(
            f"Created default vehicle "
            f"{vehicle_id} for user_id={user_id}"
        )

        self.current_vehicle = {
            "vehicle_id": vehicle_id,
            "user_id": user_id,
            "nickname": f"{self.user['username'].title()}'s Car",
            "model_id": model["model_id"],
            "model_name": model["model_name"],
            "base_hp": model["base_hp"],
            "base_weight": model["base_weight"],
            "base_top_speed": model["base_top_speed"],
            "base_acceleration": model["base_acceleration"]
        }

    def load_categories(self):

        self.categories = self.db.query(
            """
            SELECT
                category_id,
                category_name
            FROM categories
            ORDER BY category_id
            """
        )

    def load_parts(self):

        if self.current_category_id is None:

            self.parts = []

            return

        self.parts = self.db.query(
            """
            SELECT
                p.part_id,
                p.category_id,
                p.part_name,
                p.manufacturer,
                p.price,
                p.hp_bonus,
                p.weight_change,
                p.top_speed_bonus,
                p.acceleration_bonus,
                p.sprite_file,
                p.layer_order,
                p.is_active,
                c.category_name,
                COALESCE(si.stock, 0) AS stock
            FROM parts p
            JOIN categories c
                ON c.category_id = p.category_id
            LEFT JOIN shop_inventory si
                ON si.part_id = p.part_id
            WHERE p.category_id = %s
              AND p.is_active = 1
            ORDER BY p.price, p.part_id
            """,
            (
                self.current_category_id,
            )
        )

    def load_installed_parts(self):

        self.installed_parts = {}

        if not self.current_vehicle:
            return

        vehicle_id = self.current_vehicle.get(
            "vehicle_id"
        )

        if not vehicle_id:
            return

        rows = self.db.query(
            """
            SELECT
                vp.vehicle_id,
                vp.category_id,
                vp.part_id,
                p.part_name,
                p.manufacturer,
                p.price,
                p.hp_bonus,
                p.weight_change,
                p.top_speed_bonus,
                p.acceleration_bonus,
                p.sprite_file,
                p.layer_order,
                c.category_name
            FROM vehicle_parts vp
            JOIN parts p
                ON p.part_id = vp.part_id
            JOIN categories c
                ON c.category_id = vp.category_id
            WHERE vp.vehicle_id = %s
            """,
            (
                vehicle_id,
            )
        )

        for row in rows:

            self.installed_parts[
                row["category_id"]
            ] = row

        # IMPORTANT:
        # Preview starts from what is actually installed.
        # Selecting a category does NOT replace the preview.
        self.preview_parts = dict(
            self.installed_parts
        )

    # ========================================================
    # UI
    # ========================================================

    def build_ui(self):

        central = QWidget()

        self.setCentralWidget(
            central
        )

        main = QVBoxLayout(
            central
        )

        main.setContentsMargins(
            18,
            18,
            18,
            18
        )

        main.setSpacing(
            14
        )

        # ----------------------------------------------------
        # HEADER
        # ----------------------------------------------------

        header = QFrame()

        header.setObjectName(
            "header"
        )

        header.setStyleSheet(
            """
            QFrame#header {
                background:#121019;
                border:1px solid #30263d;
                border-radius:15px;
            }

            QLabel {
                background:transparent;
                border:none;
            }
            """
        )

        h = QHBoxLayout(
            header
        )

        h.setContentsMargins(
            20,
            14,
            20,
            14
        )

        title = QLabel(
            "🔧  CAR CUSTOMIZER"
        )

        title.setFont(
            QFont(
                "Segoe UI",
                21,
                QFont.Weight.Bold
            )
        )

        title.setStyleSheet(
            "color:#c4b5fd;"
        )

        h.addWidget(
            title
        )

        self.vehicle_info_label = QLabel(
            f"{self.current_vehicle['nickname']}  •  "
            f"{self.current_vehicle['model_name']}"
        )

        self.vehicle_info_label.setStyleSheet(
            "color:#a9a1b5;font-size:14px;"
        )

        h.addWidget(
            self.vehicle_info_label
        )

        h.addStretch()

        # ----------------------------------------------------
        # GREETING + ROLE (single header box)
        # ----------------------------------------------------

        user_box = QFrame()

        user_box.setObjectName("userGreetingBox")

        user_box.setStyleSheet(
            """
            QFrame#userGreetingBox {
                background:#1b1624;
                border:1px solid #49385e;
                border-radius:10px;
            }

            QLabel {
                background:transparent;
                border:none;
            }
            """
        )

        user_box_layout = QVBoxLayout(user_box)
        user_box_layout.setContentsMargins(12, 7, 12, 7)
        user_box_layout.setSpacing(1)

        self.greeting_label = QLabel("Hello, Guest!")
        self.greeting_label.setStyleSheet(
            "color:#c4b5fd;font-size:14px;font-weight:bold;"
        )
        self.greeting_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.role_label = QLabel(
            f"ROLE: {self.role_name.upper()}"
        )
        self.role_label.setStyleSheet(
            "color:#a99abd;font-size:10px;font-weight:800;"
        )
        self.role_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        user_box_layout.addWidget(self.greeting_label)
        user_box_layout.addWidget(self.role_label)

        h.addWidget(user_box)

        self.money_label = QLabel()

        self.money_label.setStyleSheet(
            "color:#c4b5fd;font-size:16px;font-weight:bold;"
        )

        h.addWidget(
            self.money_label
        )

        cars_button = QPushButton(
            "🚗  MY CARS / BUY"
        )

        cars_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        cars_button.setMinimumHeight(38)

        cars_button.clicked.connect(
            self.open_vehicle_shop
        )

        cars_button.setStyleSheet(
            """
            QPushButton {
                background:#211a2c;
                color:#e9edf1;
                border:1px solid #68517f;
                border-radius:8px;
                padding:8px 12px;
                font-weight:bold;
            }
            QPushButton:hover { background:#414c57; }
            """
        )

        h.addWidget(cars_button)

        switch_button = QPushButton(
            "⇄  SWITCH USER"
        )

        switch_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        switch_button.setMinimumHeight(
            38
        )

        switch_button.clicked.connect(
            self.switch_user
        )

        switch_button.setStyleSheet(
            """
            QPushButton {
                background:#211a2c;
                color:#e9edf1;
                border:1px solid #68517f;
                border-radius:8px;
                padding:8px 12px;
                font-weight:bold;
            }

            QPushButton:hover {
                background:#414c57;
            }
            """
        )

        h.addWidget(
            switch_button
        )

        main.addWidget(
            header
        )

        # ----------------------------------------------------
        # CONTENT
        # ----------------------------------------------------

        content = QHBoxLayout()

        content.setSpacing(
            14
        )

        main.addLayout(
            content,
            1
        )

        # ----------------------------------------------------
        # LEFT
        # ----------------------------------------------------

        left = QFrame()

        left.setFixedWidth(
            190
        )

        left.setStyleSheet(
            """
            QFrame {
                background:#121019;
                border:1px solid #30263d;
                border-radius:15px;
            }

            QLabel {
                background:transparent;
                border:none;
            }

            QPushButton {
                background:#1b1624;
                color:#dce1e6;
                border:1px solid #49385e;
                border-radius:9px;
                padding:12px;
                text-align:left;
                font-size:14px;
            }

            QPushButton:hover {
                background:#2a2038;
            }

            QPushButton:checked {
                background:#8b5cf6;
                color:white;
                border-color:#c4b5fd;
            }
            """
        )

        left_layout = QVBoxLayout(
            left
        )

        left_layout.setContentsMargins(
            12,
            12,
            12,
            12
        )

        cat_title = QLabel(
            "CATEGORIES"
        )

        cat_title.setStyleSheet(
            "color:#a9a1b5;font-size:11px;font-weight:bold;"
        )

        left_layout.addWidget(
            cat_title
        )

        left_layout.addSpacing(
            6
        )

        self.category_buttons = []

        for category in self.categories:

            button = QPushButton(
                category["category_name"]
            )

            button.setCheckable(
                True
            )

            button.clicked.connect(
                lambda checked,
                cid=category["category_id"]:
                self.select_category(cid)
            )

            self.category_buttons.append(
                (
                    category["category_id"],
                    button
                )
            )

            left_layout.addWidget(
                button
            )

        left_layout.addStretch()

        content.addWidget(
            left
        )

        # ----------------------------------------------------
        # CENTER
        # ----------------------------------------------------

        center = QFrame()

        center.setStyleSheet(
            """
            QFrame {
                background:#25232d;
                border:1px solid #514866;
                border-radius:15px;
            }

            QLabel {
                background:transparent;
                border:none;
            }
            """
        )

        center_layout = QVBoxLayout(
            center
        )

        center_layout.setContentsMargins(
            20,
            18,
            20,
            18
        )

        garage_label = QLabel(
            "GARAGE WORKSPACE"
        )

        garage_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        garage_label.setStyleSheet(
            "color:#c4b5fd;font-size:12px;font-weight:bold;"
        )

        center_layout.addWidget(
            garage_label
        )

        self.car_label = QLabel()

        self.car_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.car_label.setMinimumSize(
            650,
            450
        )

        self.car_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        center_layout.addWidget(
            self.car_label,
            1
        )

        self.status_label = QLabel(
            "Select a modification."
        )

        self.status_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.status_label.setStyleSheet(
            "color:#b8afc4;font-size:14px;padding:8px;"
        )

        center_layout.addWidget(
            self.status_label
        )

        content.addWidget(
            center,
            1
        )

        # ----------------------------------------------------
        # RIGHT
        # ----------------------------------------------------

        right = QFrame()

        right.setFixedWidth(
            365
        )

        right.setStyleSheet(
            """
            QFrame {
                background:#121019;
                border:1px solid #30263d;
                border-radius:15px;
            }

            QLabel {
                background:transparent;
                border:none;
            }

            QListWidget {
                background:transparent;
                border:none;
            }

            QListWidget::item {
                background:transparent;
                border:none;
            }
            """
        )

        right_layout = QVBoxLayout(
            right
        )

        right_layout.setContentsMargins(
            14,
            14,
            14,
            14
        )

        self.parts_title = QLabel(
            "PARTS"
        )

        self.parts_title.setStyleSheet(
            "font-size:14px;font-weight:bold;color:#f0f2f4;"
        )

        right_layout.addWidget(
            self.parts_title
        )

        self.parts_list = QListWidget()

        self.parts_list.setSpacing(
            7
        )

        self.parts_list.itemClicked.connect(
            self.part_clicked
        )

        right_layout.addWidget(
            self.parts_list,
            1
        )

        self.selected_label = QLabel(
            "No part selected"
        )

        self.selected_label.setWordWrap(
            True
        )

        self.selected_label.setStyleSheet(
            "color:#b8afc4;padding:5px;"
        )

        right_layout.addWidget(
            self.selected_label
        )

        self.buy_button = QPushButton(
            "BUY / INSTALL"
        )

        self.buy_button.setMinimumHeight(
            48
        )

        self.buy_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )

        self.buy_button.clicked.connect(
            self.install_selected_part
        )

        self.buy_button.setStyleSheet(
            """
            QPushButton {
                background:#8b5cf6;
                color:white;
                border:1px solid #c4b5fd;
                border-radius:10px;
                font-size:15px;
                font-weight:bold;
                padding:10px;
            }

            QPushButton:hover {
                background:#a78bfa;
            }

            QPushButton:disabled {
                background:#211c29;
                border-color:#40354d;
                color:#81778d;
            }
            """
        )

        right_layout.addWidget(
            self.buy_button
        )

        if self.role_name != ROLE_GUEST:

            history_button = QPushButton(
                "📋  PURCHASE HISTORY"
            )

            history_button.setMinimumHeight(
                42
            )

            history_button.clicked.connect(
                self.open_purchase_history
            )

            right_layout.addWidget(
                history_button
            )

        if self.role_name in (
            ROLE_SHOP_MANAGER,
            ROLE_ADMIN
        ):

            management_button = QPushButton(
                "⚙  MANAGEMENT"
            )

            management_button.setMinimumHeight(
                42
            )

            management_button.clicked.connect(
                self.open_management
            )

            right_layout.addWidget(
                management_button
            )

        content.addWidget(
            right
        )

        # ----------------------------------------------------
        # STATS
        # ----------------------------------------------------

        stats = QFrame()

        stats.setStyleSheet(
            """
            QFrame {
                background:#121019;
                border:1px solid #30263d;
                border-radius:15px;
            }

            QLabel {
                background:transparent;
                border:none;
                color:#dce1e6;
            }
            """
        )

        stats_layout = QHBoxLayout(
            stats
        )

        stats_layout.setContentsMargins(
            18,
            12,
            18,
            12
        )

        self.hp_label = QLabel()
        self.weight_label = QLabel()
        self.speed_label = QLabel()
        self.accel_label = QLabel()

        for label in (
            self.hp_label,
            self.weight_label,
            self.speed_label,
            self.accel_label
        ):

            label.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

            label.setFont(
                QFont(
                    "Segoe UI",
                    11,
                    QFont.Weight.Bold
                )
            )

            stats_layout.addWidget(
                label,
                1
            )

        main.addWidget(
            stats
        )

        self.setStyleSheet(
            """
            QMainWindow {
                background:
                    qlineargradient(
                        x1:0,
                        y1:0,
                        x2:0,
                        y2:1,
                        stop:0 #09070d,
                        stop:0.5 #120c1b,
                        stop:1 #07050a
                    );
            }
            """
        )

    # ========================================================
    # MY CARS / VEHICLE SHOP
    # ========================================================

    def open_vehicle_shop(self):

        if not self.user.get("user_id"):
            QMessageBox.information(
                self,
                "Guest Account",
                "Guest accounts can preview the garage, but they cannot buy cars."
            )
            return

        dialog = VehicleShopDialog(
            self.db,
            self.user,
            self.current_vehicle.get("vehicle_id"),
            self
        )

        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.selected_vehicle_id:
            self.switch_vehicle(dialog.selected_vehicle_id)

    def switch_vehicle(self, vehicle_id):

        vehicle = self.db.one(
            """
            SELECT
                v.vehicle_id,
                v.user_id,
                v.nickname,
                v.model_id,
                cm.model_name,
                cm.base_hp,
                cm.base_weight,
                cm.base_top_speed,
                cm.base_acceleration
            FROM vehicles v
            JOIN car_models cm ON cm.model_id = v.model_id
            WHERE v.vehicle_id = %s
              AND v.user_id = %s
            """,
            (vehicle_id, self.user["user_id"])
        )

        if not vehicle:
            QMessageBox.warning(
                self,
                "Vehicle Not Found",
                "The selected vehicle could not be found."
            )
            return

        self.current_vehicle = vehicle
        self.load_installed_parts()
        self.preview_parts = dict(self.installed_parts)
        self.refresh_user_display()

        self.vehicle_info_label.setText(
            f"{self.current_vehicle['nickname']}  •  {self.current_vehicle['model_name']}"
        )

        self.select_first_category()
        self.refresh_car_preview()

        self.status_label.setText(
            f"Switched to {self.current_vehicle['nickname']} "
            f"({self.current_vehicle['model_name']})."
        )

    # ========================================================
    # SWITCH USER
    # ========================================================

    def switch_user(self):

        answer = QMessageBox.question(
            self,
            "Switch User",
            "Return to the login screen?\n\n"
            "Your current account will remain saved.",
            QMessageBox.StandardButton.Yes |
            QMessageBox.StandardButton.No
        )

        if answer != QMessageBox.StandardButton.Yes:
            return

        self.switch_user_callback()

    # ========================================================
    # ACCESS
    # ========================================================

    def can_buy(self):

        return self.role_name in (
            ROLE_PLAYER,
            ROLE_SHOP_MANAGER,
            ROLE_ADMIN,
            "Admin"
        )

    def can_manage_shop(self):

        return self.role_name in (
            ROLE_SHOP_MANAGER,
            ROLE_ADMIN,
            "Admin"
        )

    # ========================================================
    # HISTORY
    # ========================================================

    def open_purchase_history(self):

        if not self.user.get("user_id"):

            QMessageBox.information(
                self,
                "Guest Account",
                "Guest accounts do not have purchase history."
            )

            return

        dialog = PurchaseHistoryDialog(
            self.db,
            self.user["user_id"],
            self.user["username"],
            self
        )

        dialog.exec()

    # ========================================================
    # MANAGEMENT
    # ========================================================

    def open_management(self):

        if not self.can_manage_shop():

            QMessageBox.warning(
                self,
                "Access Denied",
                "You do not have management access."
            )

            return

        dialog = ManagementDialog(
            self.db,
            self.role_name,
            self
        )

        dialog.exec()

        self.load_parts()
        self.populate_parts()
        self.refresh_user_display()

    # ========================================================
    # CATEGORY
    # ========================================================

    def select_first_category(self):

        if self.categories:

            self.select_category(
                self.categories[0]["category_id"]
            )

    def select_category(
        self,
        category_id
    ):

        self.current_category_id = category_id

        for cid, button in self.category_buttons:

            button.setChecked(
                cid == category_id
            )

        self.load_parts()

        self.populate_parts()

        # IMPORTANT:
        # Do NOT change preview_parts here.
        #
        # This is what prevents Paint from automatically
        # switching to Red/Blue when opening the category.

        installed = self.installed_parts.get(
            category_id
        )

        if installed:

            self.status_label.setText(
                f"Currently equipped: "
                f"{installed['part_name']}"
            )

        else:

            self.status_label.setText(
                "No modification installed in this category."
            )

    # ========================================================
    # PARTS
    # ========================================================

    def populate_parts(self):

        self.parts_list.clear()

        category_name = "Parts"

        for category in self.categories:

            if int(category["category_id"]) == int(self.current_category_id):
                category_name = category["category_name"]
                break

        self.parts_title.setText(category_name.upper())

        # Always rebuild the complete list for the current category.
        # Previewing a part must never remove another choice.
        category_parts = [
            part for part in self.parts
            if int(part["category_id"]) == int(self.current_category_id)
        ]

        for part in category_parts:

            item = QListWidgetItem()
            button = PartButton(part)

            installed = self.installed_parts.get(part["category_id"])

            if installed and int(installed["part_id"]) == int(part["part_id"]):
                button.setStyleSheet(
                    """
                    QPushButton {
                        background:#211a2d;
                        color:#f3efff;
                        border:1px solid #8b5cf6;
                        border-radius:9px;
                        padding:8px;
                        text-align:left;
                        font-size:11px;
                    }
                    """
                )

            self.parts_list.addItem(item)
            self.parts_list.setItemWidget(item, button)
            item.setSizeHint(QSize(0, 110))

            # Clicking a part is always a preview. It does not alter
            # the available choices and does not write to MySQL.
            button.clicked.connect(
                lambda checked=False, p=part: self.select_part(
                    p,
                    preview=True
                )
            )

        # Do not auto-select the first part. If something is actually
        # installed, show that as the current state without changing
        # the preview. Otherwise leave the category unselected until
        # the user clicks an option.
        installed = self.installed_parts.get(self.current_category_id)

        if installed:
            self.select_part(installed, preview=False)
        else:
            self.selected_part = None
            self.selected_label.setText("Select a part to preview it.")
            self.buy_button.setText(
                "GUEST — PURCHASE DISABLED"
                if not self.can_buy()
                else "BUY / INSTALL"
            )
            self.buy_button.setEnabled(False)

    def part_clicked(
        self,
        item
    ):

        button = self.parts_list.itemWidget(
            item
        )

        if button:

            self.select_part(
                button.part,
                preview=True
            )

    def is_stock_part(self, part):

        name = str(part.get("part_name", "")).strip().lower()
        price = Decimal(str(part.get("price", 0) or 0))

        return name.startswith("stock ") or price == 0

    def select_part(
        self,
        part,
        preview=True
    ):

        self.selected_part = part

        category_id = int(
            part["category_id"]
        )

        is_stock = self.is_stock_part(part)

        if preview:

            # Stock parts are represented by the original base car.
            # Removing the category overlay gives a real stock preview.
            if is_stock:
                self.preview_parts.pop(category_id, None)
            else:
                self.preview_parts[
                    category_id
                ] = part

        price = Decimal(
            str(
                part.get(
                    "price",
                    0
                ) or 0
            )
        )

        stock = int(
            part.get(
                "stock",
                0
            ) or 0
        )

        installed = self.installed_parts.get(
            category_id
        )

        is_installed = (
            installed is not None
            and int(installed["part_id"])
            == int(part["part_id"])
        )

        # ----------------------------------------------------
        # CHECK WHETHER PLAYER ALREADY OWNS THE PART
        # ----------------------------------------------------

        is_owned = False
        owned_quantity = 0

        if self.user.get("user_id"):

            inventory_row = self.db.one(
                """
                SELECT quantity
                FROM player_inventory
                WHERE user_id = %s
                  AND part_id = %s
                  AND quantity > 0
                """,
                (
                    self.user["user_id"],
                    part["part_id"]
                )
            )

            if inventory_row:

                owned_quantity = int(
                    inventory_row["quantity"] or 0
                )

                is_owned = (
                    owned_quantity > 0
                )

        # ----------------------------------------------------
        # ALREADY INSTALLED
        # ----------------------------------------------------

        if is_installed:

            self.selected_label.setText(
                f"<b>{part['part_name']}</b><br>"
                f"{part.get('manufacturer') or 'OEM'}  •  "
                f"{'FREE' if is_stock or price == 0 else money(price)}<br>"
                f"HP {int(part.get('hp_bonus', 0) or 0):+d}  •  "
                f"Weight {int(part.get('weight_change', 0) or 0):+d} kg  •  "
                f"Top Speed {int(part.get('top_speed_bonus', 0) or 0):+d} km/h  •  "
                f"Accel {Decimal(str(part.get('acceleration_bonus', 0) or 0)):+.2f}<br>"
                f"<span style='color:#76a879;'>✓ Currently installed</span>"
            )

            self.buy_button.setText(
                "INSTALLED"
            )

            self.buy_button.setEnabled(
                False
            )

        # ----------------------------------------------------
        # OWNED BUT NOT INSTALLED
        # ----------------------------------------------------

        elif is_owned:

            self.selected_label.setText(
                f"<b>{part['part_name']}</b><br>"
                f"{part.get('manufacturer') or 'OEM'}  •  "
                f"{'FREE' if is_stock or price == 0 else money(price)}<br>"
                f"HP {int(part.get('hp_bonus', 0) or 0):+d}  •  "
                f"Weight {int(part.get('weight_change', 0) or 0):+d} kg  •  "
                f"Top Speed {int(part.get('top_speed_bonus', 0) or 0):+d} km/h  •  "
                f"Accel {Decimal(str(part.get('acceleration_bonus', 0) or 0)):+.2f}<br>"
                f"<span style='color:#76a879;'>✓ Owned × {owned_quantity} — ready to install</span>"
            )

            self.buy_button.setText(
                "INSTALL"
            )

            self.buy_button.setEnabled(
                True
            )

        # ----------------------------------------------------
        # NOT OWNED
        # ----------------------------------------------------

        else:

            self.selected_label.setText(
                f"<b>{part['part_name']}</b><br>"
                f"{part.get('manufacturer') or 'OEM'}  •  "
                f"{'FREE' if is_stock or price == 0 else money(price)}<br>"
                f"HP {int(part.get('hp_bonus', 0) or 0):+d}  •  "
                f"Weight {int(part.get('weight_change', 0) or 0):+d} kg  •  "
                f"Top Speed {int(part.get('top_speed_bonus', 0) or 0):+d} km/h  •  "
                f"Accel {Decimal(str(part.get('acceleration_bonus', 0) or 0)):+.2f}<br>"
                f"Shop stock: {stock}"
            )

            if is_stock:

                self.buy_button.setText(
                    "INSTALL FREE"
                )

                self.buy_button.setEnabled(
                    self.can_buy()
                )

            elif not self.can_buy():

                self.buy_button.setText(
                    "GUEST — PURCHASE DISABLED"
                )

                self.buy_button.setEnabled(
                    False
                )

            else:

                self.buy_button.setText(
                    "BUY / INSTALL"
                )

                self.buy_button.setEnabled(
                    stock > 0
                )

        if preview:

            self.status_label.setText(
                f"Previewing: {part['part_name']}"
            )

            self.refresh_car_preview()

        else:

            if is_installed:

                self.status_label.setText(
                    f"Currently equipped: "
                    f"{part['part_name']}"
                )

            elif is_owned:

                self.status_label.setText(
                    f"Owned: {part['part_name']}"
                )

    # ========================================================
    # ASSETS
    # ========================================================

    def find_asset(
        self,
        filename
    ):

        if not filename:
            return None

        filename = os.path.basename(
            str(filename)
        )

        model_name = str(
            self.current_vehicle.get("model_name", "")
        )

        model_folder = MODEL_ASSET_DIRS.get(model_name)

        if model_folder:
            model_dir = os.path.join(
                ASSET_DIR,
                model_folder
            )

            # 1. Normal filename, e.g.
            #    supra/base.png or r34/base.png
            candidates = [
                os.path.join(model_dir, filename)
            ]

            # 2. Support the prefixed Supra files, e.g.
            #    supra/supra_base.png
            #    supra/supra_bbs_lm.png
            if model_folder == "supra" and not filename.startswith("supra_"):
                candidates.append(
                    os.path.join(
                        model_dir,
                        "supra_" + filename
                    )
                )

            for path in candidates:
                if os.path.exists(path):
                    return path

        # Backward-compatible fallback for assets directly under assets/car/.
        fallback_path = os.path.join(
            ASSET_DIR,
            filename
        )

        if os.path.exists(fallback_path):
            return fallback_path

        return None

    def load_pixmap(
        self,
        filename
    ):

        path = self.find_asset(
            filename
        )

        if not path:
            return None

        pixmap = QPixmap(
            path
        )

        if pixmap.isNull():
            return None

        return pixmap

    def base_pixmap(self):

        model_name = str(
            self.current_vehicle.get("model_name", "")
        )

        candidates = MODEL_ASSETS.get(
            model_name,
            []
        )

        for filename in candidates:
            pixmap = self.load_pixmap(filename)
            if pixmap is not None:
                return pixmap

        # Backward-compatible fallback for projects that only have base.png.
        return self.load_pixmap("base.png")

    # ========================================================
    # PREVIEW
    # ========================================================

    def refresh_car_preview(self):

        if not hasattr(
            self,
            "car_label"
        ):
            return

        base = self.base_pixmap()

        if base is None:

            self.car_label.setText(
                "BASE CAR IMAGE NOT FOUND\n\n"
                "Put the car image inside:\n"
                "assets/car/<car-folder>/"
            )

            return

        result = QPixmap(
            base.size()
        )

        result.fill(
            Qt.GlobalColor.transparent
        )

        painter = QPainter(
            result
        )

        painter.drawPixmap(
            0,
            0,
            base
        )

        parts = list(
            self.preview_parts.values()
        )

        parts.sort(
            key=lambda p: (
                int(
                    p.get(
                        "layer_order",
                        1
                    ) or 1
                ),
                int(
                    p.get(
                        "part_id",
                        0
                    ) or 0
                )
            )
        )

        for part in parts:

            if self.is_stock_part(part):
                continue

            sprite = self.load_pixmap(
                part.get(
                    "sprite_file"
                )
            )

            if sprite is None:
                continue

            if sprite.size() == result.size():

                painter.drawPixmap(
                    0,
                    0,
                    sprite
                )

            else:

                scaled = sprite.scaled(
                    result.size(),
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )

                x = (
                    result.width()
                    - scaled.width()
                ) // 2

                y = (
                    result.height()
                    - scaled.height()
                ) // 2

                painter.drawPixmap(
                    x,
                    y,
                    scaled
                )

        painter.end()

        display = result.scaled(
            self.car_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        self.car_label.setPixmap(
            display
        )

        self.update_stats()

    # ========================================================
    # STATS
    # ========================================================

    def update_stats(self):

        hp = int(
            self.current_vehicle.get(
                "base_hp",
                100
            ) or 0
        )

        weight = int(
            self.current_vehicle.get(
                "base_weight",
                1000
            ) or 0
        )

        speed = int(
            self.current_vehicle.get(
                "base_top_speed",
                150
            ) or 0
        )

        accel = Decimal(
            str(
                self.current_vehicle.get(
                    "base_acceleration",
                    10
                ) or 0
            )
        )

        for part in self.preview_parts.values():

            hp += int(
                part.get(
                    "hp_bonus",
                    0
                ) or 0
            )

            weight += int(
                part.get(
                    "weight_change",
                    0
                ) or 0
            )

            speed += int(
                part.get(
                    "top_speed_bonus",
                    0
                ) or 0
            )

            accel += Decimal(
                str(
                    part.get(
                        "acceleration_bonus",
                        0
                    ) or 0
                )
            )

        self.hp_label.setText(
            f"⚡ HP\n{hp}"
        )

        self.weight_label.setText(
            f"⚖ Weight\n{weight} kg"
        )

        self.speed_label.setText(
            f"🏁 Top Speed\n{speed} km/h"
        )

        self.accel_label.setText(
            f"🚀 Acceleration\n{accel:.2f}"
        )

    # ========================================================
    # GREETINGS AND MONEY
    # ========================================================

    def refresh_user_display(self):

        if not self.user.get("user_id"):

            self.money_label.setText(
                "💰 Guest"
            )

            self.greeting_label.setText(
                "Hello, Guest!"
            )

            self.role_label.setText(
                "ROLE: GUEST"
            )

            return

        self.user = self.db.one(
            """
            SELECT
                u.user_id,
                u.username,
                u.nickname,
                u.money,
                u.role_id,
                u.is_active,
                r.role_name
            FROM users u
            JOIN roles r
                ON r.role_id = u.role_id
            WHERE u.user_id = %s
            """,
            (
                self.user["user_id"],
            )
        )

        if not self.user:
            return

        self.role_name = (
            self.user["role_name"]
            or ROLE_GUEST
        )

        self.money_label.setText(
            f"💰 {money(self.user['money'])}"
        )

        nickname = (
            self.user.get("nickname")
            or self.user.get("username")
            or "Guest"
        )

        self.greeting_label.setText(
            f"Hello, {nickname}!"
        )

        self.role_label.setText(
            f"ROLE: {self.role_name.upper()}"
        )

    # ========================================================
    # BUY
    # ========================================================

    def install_selected_part(self):

        if not self.can_buy():

            QMessageBox.warning(
                self,
                "Access Denied",
                "Guest accounts cannot purchase "
                "or install modifications."
            )

            return

        if not self.selected_part:

            QMessageBox.warning(
                self,
                "No Part Selected",
                "Please select a modification first."
            )

            return

        self.install_part(
            self.selected_part
        )

    def install_part(
        self,
        part
    ):

        if not self.can_buy():
            return

        if not self.current_vehicle.get(
            "vehicle_id"
        ):

            QMessageBox.warning(
                self,
                "No Vehicle",
                "This account does not have a vehicle."
            )

            return

        vehicle_id = self.current_vehicle[
            "vehicle_id"
        ]

        user_id = self.user[
            "user_id"
        ]

        part_id = int(
            part["part_id"]
        )

        category_id = int(
            part["category_id"]
        )

        price = Decimal(
            str(
                part.get(
                    "price",
                    0
                ) or 0
            )
        )

        cursor = None

        try:

            self.db.ensure_connection()

            self.db.conn.autocommit = False

            self.db.conn.start_transaction()

            cursor = self.db.conn.cursor(
                dictionary=True
            )

            # =================================================
            # CURRENT VEHICLE PART
            # =================================================

            cursor.execute(
                """
                SELECT part_id
                FROM vehicle_parts
                WHERE vehicle_id = %s
                  AND category_id = %s
                FOR UPDATE
                """,
                (
                    vehicle_id,
                    category_id
                )
            )

            installed_row = cursor.fetchone()

            if (
                installed_row
                and int(
                    installed_row["part_id"]
                ) == part_id
            ):

                raise RuntimeError(
                    "This part is already installed."
                )

            # =================================================
            # FREE STOCK PART
            # =================================================
            # Stock parts are part of the base car. They cost nothing,
            # do not consume shop stock, and do not create purchase
            # history or player-inventory entries.
            if self.is_stock_part(part):

                if installed_row:

                    cursor.execute(
                        """
                        UPDATE vehicle_parts
                        SET part_id = %s
                        WHERE vehicle_id = %s
                          AND category_id = %s
                        """,
                        (
                            part_id,
                            vehicle_id,
                            category_id
                        )
                    )

                else:

                    cursor.execute(
                        """
                        INSERT INTO vehicle_parts
                            (vehicle_id, category_id, part_id)
                        VALUES (%s, %s, %s)
                        """,
                        (
                            vehicle_id,
                            category_id,
                            part_id
                        )
                    )

                self.db.conn.commit()
                self.db.conn.autocommit = True

                self.load_installed_parts()
                self.load_parts()
                self.populate_parts()
                self.preview_parts = dict(self.installed_parts)
                self.refresh_car_preview()
                self.refresh_user_display()

                self.status_label.setText(
                    f"✓ {part['part_name']} installed for free."
                )

                QMessageBox.information(
                    self,
                    "Installation Complete",
                    f"{part['part_name']} was installed successfully.\n\n"
                    "Stock parts are included with the car and cost nothing."
                )

                return

            # =================================================
            # PLAYER INVENTORY
            # =================================================

            cursor.execute(
                """
                SELECT
                    inventory_id,
                    quantity
                FROM player_inventory
                WHERE user_id = %s
                  AND part_id = %s
                FOR UPDATE
                """,
                (
                    user_id,
                    part_id
                )
            )

            inv_row = cursor.fetchone()

            owned_quantity = 0

            if inv_row:

                owned_quantity = int(
                    inv_row["quantity"] or 0
                )

            # =================================================
            # CASE 1:
            # PLAYER ALREADY OWNS THE PART
            # =================================================

            if owned_quantity > 0:

                # ---------------------------------------------
                # REMOVE ONE FROM PLAYER INVENTORY
                # ---------------------------------------------

                if owned_quantity == 1:

                    cursor.execute(
                        """
                        DELETE FROM player_inventory
                        WHERE inventory_id = %s
                        """,
                        (
                            inv_row["inventory_id"],
                        )
                    )

                else:

                    cursor.execute(
                        """
                        UPDATE player_inventory
                        SET quantity = quantity - 1
                        WHERE inventory_id = %s
                        """,
                        (
                            inv_row["inventory_id"],
                        )
                    )

                # ---------------------------------------------
                # INSTALL INTO VEHICLE
                # ---------------------------------------------

                if installed_row:

                    cursor.execute(
                        """
                        UPDATE vehicle_parts
                        SET part_id = %s
                        WHERE vehicle_id = %s
                          AND category_id = %s
                        """,
                        (
                            part_id,
                            vehicle_id,
                            category_id
                        )
                    )

                else:

                    cursor.execute(
                        """
                        INSERT INTO vehicle_parts
                            (
                                vehicle_id,
                                category_id,
                                part_id
                            )
                        VALUES
                            (
                                %s,
                                %s,
                                %s
                            )
                        """,
                        (
                            vehicle_id,
                            category_id,
                            part_id
                        )
                    )

                self.db.conn.commit()

                self.db.conn.autocommit = True

                self.load_installed_parts()

                self.refresh_user_display()

                self.load_parts()

                self.populate_parts()

                self.preview_parts = dict(
                    self.installed_parts
                )

                self.refresh_car_preview()

                self.status_label.setText(
                    f"✓ {part['part_name']} "
                    f"installed from inventory."
                )

                QMessageBox.information(
                    self,
                    "Installation Complete",
                    f"{part['part_name']} "
                    f"was installed successfully.\n\n"
                    "No additional payment was required."
                )

                return

            # =================================================
            # CASE 2:
            # PLAYER DOES NOT OWN THE PART
            # → PURCHASE IT
            # =================================================

            # ---------------------------------------------
            # LOCK USER MONEY
            # ---------------------------------------------

            cursor.execute(
                """
                SELECT money
                FROM users
                WHERE user_id = %s
                FOR UPDATE
                """,
                (
                    user_id,
                )
            )

            user_row = cursor.fetchone()

            if not user_row:

                raise RuntimeError(
                    "Player account was not found."
                )

            current_money = Decimal(
                str(
                    user_row["money"]
                    or 0
                )
            )

            if current_money < price:

                raise RuntimeError(
                    "Not enough money.\n\n"
                    f"Your money: {money(current_money)}\n"
                    f"Part price: {money(price)}"
                )

            # ---------------------------------------------
            # LOCK SHOP STOCK
            # ---------------------------------------------

            cursor.execute(
                """
                SELECT stock
                FROM shop_inventory
                WHERE part_id = %s
                FOR UPDATE
                """,
                (
                    part_id,
                )
            )

            stock_row = cursor.fetchone()

            if not stock_row:

                raise RuntimeError(
                    "This part is not present "
                    "in shop inventory."
                )

            stock = int(
                stock_row["stock"] or 0
            )

            if stock <= 0:

                raise RuntimeError(
                    "This part is currently out of stock."
                )

            # ---------------------------------------------
            # DEDUCT MONEY
            # ---------------------------------------------

            cursor.execute(
                """
                UPDATE users
                SET money = money - %s
                WHERE user_id = %s
                """,
                (
                    price,
                    user_id
                )
            )

            # ---------------------------------------------
            # REDUCE SHOP STOCK
            # ---------------------------------------------

            cursor.execute(
                """
                UPDATE shop_inventory
                SET stock = stock - 1
                WHERE part_id = %s
                """,
                (
                    part_id,
                )
            )

            # ---------------------------------------------
            # ADD TO PLAYER INVENTORY
            # ---------------------------------------------

            cursor.execute(
                """
                INSERT INTO player_inventory
                    (
                        user_id,
                        part_id,
                        quantity
                    )
                VALUES
                    (
                        %s,
                        %s,
                        1
                    )
                """,
                (
                    user_id,
                    part_id
                )
            )

            # ---------------------------------------------
            # PURCHASE HISTORY
            # ---------------------------------------------

            cursor.execute(
                """
                INSERT INTO purchases
                    (
                        user_id,
                        part_id,
                        quantity,
                        total_price
                    )
                VALUES
                    (
                        %s,
                        %s,
                        1,
                        %s
                    )
                """,
                (
                    user_id,
                    part_id,
                    price
                )
            )

            # ---------------------------------------------
            # INSTALL THE NEWLY PURCHASED PART
            # ---------------------------------------------

            if installed_row:

                cursor.execute(
                    """
                    UPDATE vehicle_parts
                    SET part_id = %s
                    WHERE vehicle_id = %s
                      AND category_id = %s
                    """,
                    (
                        part_id,
                        vehicle_id,
                        category_id
                    )
                )

            else:

                cursor.execute(
                    """
                    INSERT INTO vehicle_parts
                        (
                            vehicle_id,
                            category_id,
                            part_id
                        )
                    VALUES
                        (
                            %s,
                            %s,
                            %s
                        )
                    """,
                    (
                        vehicle_id,
                        category_id,
                        part_id
                    )
                )

            self.db.conn.commit()

            self.db.conn.autocommit = True

            self.load_installed_parts()

            self.refresh_user_display()

            self.load_parts()

            self.populate_parts()

            self.preview_parts = dict(
                self.installed_parts
            )

            self.refresh_car_preview()

            self.status_label.setText(
                f"✓ {part['part_name']} "
                f"purchased and installed."
            )

            QMessageBox.information(
                self,
                "Purchase Complete",
                f"{part['part_name']} "
                f"was purchased and installed successfully.\n\n"
                f"Amount paid: {money(price)}"
            )

        except Exception as exc:

            try:
                self.db.conn.rollback()
            except Exception:
                pass

            try:
                self.db.conn.autocommit = True
            except Exception:
                pass

            QMessageBox.critical(
                self,
                "Purchase / Installation Error",
                f"The operation could not be completed.\n\n"
                f"{exc}"
            )

        finally:

            if cursor is not None:

                try:
                    cursor.close()
                except Exception:
                    pass

    # ========================================================
    # EVENTS
    # ========================================================

    def resizeEvent(
        self,
        event
    ):

        super().resizeEvent(
            event
        )

        if hasattr(
            self,
            "car_label"
        ):

            self.refresh_car_preview()


# ============================================================
# APPLICATION CONTROLLER
# ============================================================

class ApplicationController:

    def __init__(self):

        self.db = Database()

        self.app = QApplication.instance()

        self.login_window = None
        self.garage_window = None

        self.show_login()

    def show_login(self):

        # Close old garage window safely.
        if self.garage_window is not None:

            try:
                self.garage_window.close()
            except Exception:
                pass

            self.garage_window.deleteLater()

            self.garage_window = None

        self.login_window = LoginWindow(
            self.db,
            self.login_success
        )

        self.login_window.show()

    def login_success(
        self,
        user
    ):

        if self.login_window is not None:

            self.login_window.close()

            self.login_window.deleteLater()

            self.login_window = None

        try:

            self.garage_window = GarageWindow(
                self.db,
                user,
                self.show_login
            )

            self.garage_window.show()

        except Exception as exc:

            QMessageBox.critical(
                None,
                "Application Error",
                f"The application could not start.\n\n"
                f"{exc}"
            )

            print(
                "Application error:",
                repr(exc)
            )

            self.show_login()

    def close(self):

        if self.garage_window is not None:

            try:
                self.garage_window.close()
            except Exception:
                pass

        if self.login_window is not None:

            try:
                self.login_window.close()
            except Exception:
                pass

        self.db.close()


# ============================================================
# MAIN
# ============================================================

def main():

    app = QApplication(
        sys.argv
    )

    app.setApplicationName(
        "Car Customizer"
    )

    app.setFont(
        QFont(
            "Segoe UI",
            10
        )
    )

    controller = None

    try:

        controller = ApplicationController()

        exit_code = app.exec()

        if controller:

            controller.close()

        sys.exit(
            exit_code
        )

    except Error as exc:

        QMessageBox.critical(
            None,
            "MySQL Error",
            f"Could not connect to MySQL.\n\n{exc}"
        )

        print(
            "MySQL error:",
            exc
        )

        sys.exit(1)

    except Exception as exc:

        QMessageBox.critical(
            None,
            "Application Error",
            f"The application could not start.\n\n{exc}"
        )

        print(
            "Application error:",
            repr(exc)
        )

        sys.exit(1)


if __name__ == "__main__":

    main()