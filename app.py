from flask import Flask, request, jsonify, render_template, redirect, url_for
from apscheduler.schedulers.background import BackgroundScheduler
import sqlite3
import os

app = Flask(__name__)

# ==========================================
# ১. ডেটাবেস সেটআপ (SQLite)
# ==========================================
def init_db():
    conn = sqlite3.connect('invest.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            deposit_wallet REAL DEFAULT 0,
            earnings_wallet REAL DEFAULT 0,
            plan_name TEXT,
            daily_earn REAL DEFAULT 0,
            remaining_days INTEGER DEFAULT 0,
            refer_code TEXT UNIQUE,
            referred_by TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect('invest.db')
    conn.row_factory = sqlite3.Row
    return conn

# ==========================================
# ২. ফ্রন্টএন্ড রাউটস
# ==========================================

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login')
def login_page():
    return render_template('login.html')

@app.route('/admin')
def admin_page():
    return render_template('admin.html')

# ==========================================
# ৩. এপিআই রাউটস
# ==========================================

# ৩.১ রেজিস্ট্রেশন
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name', '').strip()
    phone = data.get('phone', '').strip()
    password = data.get('password', '').strip()

    if not name or not phone or not password:
        return jsonify({"message": "সব তথ্য পূরণ করুন।"}), 400

    import random, string
    refer_code = "RK" + str(random.randint(1000,9999)) + ''.join(random.choices(string.ascii_uppercase, k=4))

    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (name, phone, password, refer_code) VALUES (?, ?, ?, ?)",
            (name, phone, password, refer_code)
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return jsonify({
            "message": "অ্যাকাউন্ট সফলভাবে তৈরি হয়েছে!",
            "user": {
                "id": "INV-" + str(1000 + user_id),
                "name": name,
                "phone": phone,
                "referCode": refer_code,
                "depositWallet": 0,
                "earningsWallet": 0
            }
        }), 201
    except sqlite3.IntegrityError:
        return jsonify({"message": "এই ফোন নম্বরটি আগেই ব্যবহৃত হয়েছে!"}), 400

# ৩.২ লগইন
@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    phone = data.get('phone', '').strip()
    password = data.get('password', '').strip()

    if not phone or not password:
        return jsonify({"message": "ফোন ও পাসওয়ার্ড দিন।"}), 400

    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    conn.close()

    if not user:
        return jsonify({"message": "ইউজার পাওয়া যায়নি।"}), 404
    if user['password'] != password:
        return jsonify({"message": "পাসওয়ার্ড ভুল হয়েছে।"}), 401

    return jsonify({
        "message": "লগইন সফল!",
        "user": {
            "id": "INV-" + str(1000 + user['id']),
            "name": user['name'],
            "phone": user['phone'],
            "referCode": user['refer_code'],
            "depositWallet": user['deposit_wallet'],
            "earningsWallet": user['earnings_wallet'],
            "planName": user['plan_name'],
            "remainingDays": user['remaining_days']
        }
    })

# ৩.৩ ড্যাশবোর্ড ডেটা
@app.route('/api/dashboard/<phone>', methods=['GET'])
def dashboard(phone):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()
    conn.close()
    if not user:
        return jsonify({"message": "ইউজার পাওয়া যায়নি।"}), 404
    return jsonify({
        "id": "INV-" + str(1000 + user['id']),
        "name": user['name'],
        "phone": user['phone'],
        "referCode": user['refer_code'],
        "depositWallet": user['deposit_wallet'],
        "earningsWallet": user['earnings_wallet'],
        "planName": user['plan_name'],
        "dailyEarn": user['daily_earn'],
        "remainingDays": user['remaining_days']
    })

# ৩.৪ ডিপোজিট
@app.route('/api/deposit', methods=['POST'])
def deposit():
    data = request.json
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET deposit_wallet = deposit_wallet + ? WHERE phone = ?",
        (data['amount'], data['phone'])
    )
    if cursor.rowcount == 0:
        conn.close()
        return jsonify({"message": "ইউজার পাওয়া যায়নি।"}), 404
    conn.commit()
    conn.close()
    return jsonify({"message": f"{data['amount']} টাকা সফলভাবে জমা হয়েছে।"})

# ৩.৫ প্ল্যান কেনা
@app.route('/api/buy-plan', methods=['POST'])
def buy_plan():
    data = request.json
    phone = data['phone']
    plan_price = data['planPrice']

    conn = get_db()
    cursor = conn.cursor()
    user = cursor.execute("SELECT * FROM users WHERE phone = ?", (phone,)).fetchone()

    if not user:
        conn.close()
        return jsonify({"message": "ইউজার পাওয়া যায়নি।"}), 404

    if user['deposit_wallet'] >= plan_price:
        new_balance = user['deposit_wallet'] - plan_price
        cursor.execute("""
            UPDATE users
            SET deposit_wallet = ?, plan_name = ?, daily_earn = ?, remaining_days = ?
            WHERE phone = ?
        """, (new_balance, data['planName'], data['dailyEarn'], data['planDays'], phone))
        conn.commit()
        conn.close()
        return jsonify({"message": f"অভিনন্দন! আপনি '{data['planName']}' কিনেছেন।"})
    else:
        conn.close()
        return jsonify({"message": "ডিপোজিট ব্যালেন্স পর্যাপ্ত নয়।"}), 400

# ==========================================
# ৪. ডেইলি আর্নিং ক্রন জব
# ==========================================
def distribute_daily_earnings():
    print("⏳ প্রতিদিনের আয় বন্টন শুরু হয়েছে...")
    conn = get_db()
    cursor = conn.cursor()
    active_users = cursor.execute(
        "SELECT id, earnings_wallet, daily_earn, remaining_days FROM users WHERE remaining_days > 0"
    ).fetchall()

    for user in active_users:
        new_earnings = user['earnings_wallet'] + user['daily_earn']
        new_days = user['remaining_days'] - 1
        if new_days == 0:
            cursor.execute(
                "UPDATE users SET earnings_wallet = ?, remaining_days = 0, plan_name = NULL, daily_earn = 0 WHERE id = ?",
                (new_earnings, user['id'])
            )
        else:
            cursor.execute(
                "UPDATE users SET earnings_wallet = ?, remaining_days = ? WHERE id = ?",
                (new_earnings, new_days, user['id'])
            )

    conn.commit()
    conn.close()
    print(f"✅ {len(active_users)} জনের অ্যাকাউন্টে টাকা যোগ হয়েছে!")

scheduler = BackgroundScheduler()
scheduler.add_job(func=distribute_daily_earnings, trigger="cron", hour=0, minute=0)
scheduler.start()

# ==========================================
# ৫. সার্ভার চালু
# ==========================================
if __name__ == '__main__':
    app.run(port=3000, debug=True, use_reloader=False)