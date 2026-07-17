"""
routes/auth.py
──────────────
Blueprint untuk autentikasi: login, register, logout.
"""
import sqlite3
import psycopg2
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user

from models.user import User, find_by_username, create_user, verify_password

# Kredensial admin hardcoded – tidak disimpan di database
ADMIN_USERNAME = 'admin'
ADMIN_PASSWORD = 'admin123'
ADMIN_USER     = User(id=0, username=ADMIN_USERNAME, is_admin=True)

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        # Cek admin hardcoded terlebih dahulu
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            login_user(ADMIN_USER, remember=False)
            return redirect(url_for('admin.dashboard'))

        # Cek user di database
        row = find_by_username(username)
        if row:
            if verify_password(row, password):
                login_user(User(row['id'], row['username'], row['is_admin']), remember=True)
                next_page = request.args.get('next')
                return redirect(next_page or url_for('main.index'))
            flash('Password salah.', 'danger')
        else:
            flash('Akun belum terdaftar.', 'danger')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username  = request.form.get('username', '').strip()
        password  = request.form.get('password', '')
        password2 = request.form.get('password2', '')

        if not username or not password:
            flash('Username dan password tidak boleh kosong.', 'danger')
        elif len(username) < 6:
            flash('Username minimal 6 karakter.', 'danger')
        elif len(password) < 6:
            flash('Password minimal 6 karakter.', 'danger')
        elif password != password2:
            flash('Konfirmasi password tidak cocok.', 'danger')
        elif username == ADMIN_USERNAME:
            flash('Username tersebut tidak tersedia.', 'danger')
        else:
            try:
                create_user(username, password)
                # Auto-login setelah daftar - tidak perlu login lagi
                row = find_by_username(username)
                if row:
                    login_user(User(row['id'], row['username']), remember=True)
                    flash(f'Selamat datang, {username}! Akun berhasil dibuat. 🎉', 'success')
                    return redirect(url_for('main.index'))
            except psycopg2.IntegrityError:
                flash('Username sudah digunakan.', 'danger')

    return render_template('register.html')



@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Kamu telah logout.', 'info')
    return redirect(url_for('auth.login'))
