import json
import os
import datetime
from flask import Flask, request, redirect, url_for, render_template_string, session

app = Flask(__name__)
app.secret_key = 'super_secret_key' # Daha güçlü bir anahtarla değiştirin

# Global dictionary to store user data
users = {}
USERS_FILE = 'users.json'

def load_user_data():
    """Loads user data from users.json file."""
    global users
    if os.path.exists(USERS_FILE) and os.path.getsize(USERS_FILE) > 0:
        try:
            with open(USERS_FILE, 'r', encoding='utf-8') as f:
                users = json.load(f)
            print("Kullanıcı verileri 'users.json' dosyasından başarıyla yüklendi.")
        except json.JSONDecodeError:
            print("Hata: 'users.json' dosyası bozuk veya geçersiz JSON formatında. Yeni bir sözlük oluşturuluyor.")
            users = {}
        except FileNotFoundError:
            print("Hata: 'users.json' dosyası bulunamadı. Yeni bir sözlük oluşturuluyor.")
            users = {}
    else:
        print("'users.json' dosyası bulunamadı veya boş. Yeni bir kullanıcı sözlüğü oluşturuluyor.")
        users = {}

    # Ensure all users have lockout and new fields for backward compatibility
    for user_data in users.values():
        user_data.setdefault("failed_password_attempts", 0)
        user_data.setdefault("lockout_until", None)
        user_data.setdefault("security_question", "")
        user_data.setdefault("security_answer", "")
        user_data.setdefault("daily_withdrawal_limit", 10000.0)
        user_data.setdefault("current_day_withdrawal_amount", 0.0)
        user_data.setdefault("last_withdrawal_date", None)
        user_data.setdefault("user_history", [])

def save_user_data():
    """Saves user data to users.json file."""
    global users
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, indent=4, ensure_ascii=False)
        print("Kullanıcı verileri 'users.json' dosyasına başarıyla kaydedildi.")
    except Exception as e:
        print(f"Hata: Kullanıcı verileri kaydedilirken bir sorun oluştu: {e}")

# Flask uygulamasının kapatıldıktan sonra çağrılacak olaylar
@app.teardown_appcontext
def save_data_on_shutdown(exception=None):
    save_user_data()

# Adapted register_user for Flask
def register_user_web(kullanıcı_adı, parola, güvenlik_sorusu, güvenlik_cevabı):
    global users
    if not kullanıcı_adı:
        return False, "Kullanıcı adı boş bırakılamaz."
    if kullanıcı_adı in users:
        return False, f"Hata: '{kullanıcı_adı}' kullanıcı adı zaten alınmış. Lütfen başka bir kullanıcı adı seçiniz."

    if not parola:
        return False, "Parola boş bırakılamaz."

    has_uppercase = any(char.isupper() for char in parola)
    has_digit = any(char.isdigit() for char in parola)

    if not has_uppercase or not has_digit:
        return False, "Hata: Parola en az bir büyük harf ve bir rakam içermelidir."

    users[kullanıcı_adı] = {
        "parola": parola,
        "accounts": {
            "Vadesiz": {
                "bakiye": 50000.0,
                "işlem_geçmişi": []
            },
            "Birikim": {
                "bakiye": 0.0,
                "işlem_geçmişi": []
            }
        },
        "failed_password_attempts": 0,
        "lockout_until": None,
        "security_question": güvenlik_sorusu,
        "security_answer": güvenlik_cevabı,
        "daily_withdrawal_limit": 10000.0,
        "current_day_withdrawal_amount": 0.0,
        "last_withdrawal_date": None,
        "user_history": []
    }
    save_user_data()
    return True, f"Kullanıcı '{kullanıcı_adı}' başarıyla kaydedildi. Varsayılan hesaplar oluşturuldu."

# Adapted login for Flask
def login_web(kullanıcı_adı, parola):
    global users
    if kullanıcı_adı not in users:
        return False, "Kullanıcı Adı Bulunamadı...", None

    user_data = users[kullanıcı_adı]
    if user_data["lockout_until"] and datetime.datetime.fromisoformat(user_data["lockout_until"]) > datetime.datetime.now():
        locked_until_dt = datetime.datetime.fromisoformat(user_data["lockout_until"])
        remaining_time = locked_until_dt - datetime.datetime.now()
        hours, remainder = divmod(remaining_time.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        return False, f"Hesabınız kilitli. Lütfen {int(hours)} saat {int(minutes)} dakika {int(seconds)} sonra tekrar deneyiniz.", None

    if user_data["parola"] == parola:
        user_data["failed_password_attempts"] = 0
        user_data["lockout_until"] = None
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_data["user_history"].append(f"[{timestamp}] Başarılı giriş.")
        save_user_data()
        return True, "Başarıyla Giriş Yaptınız...", kullanıcı_adı
    else:
        user_data["failed_password_attempts"] += 1
        MAX_LOGIN_ATTEMPTS = 3
        if user_data["failed_password_attempts"] >= MAX_LOGIN_ATTEMPTS:
            lockout_duration_minutes = 2 ** user_data["failed_password_attempts"]
            lockout_time = datetime.datetime.now() + datetime.timedelta(minutes=lockout_duration_minutes)
            user_data["lockout_until"] = lockout_time.isoformat()
            message = f"Çok fazla hatalı deneme. Hesabınız {lockout_duration_minutes} dakika kilitlendi."
        else:
            message = "Parola Hatalı..."
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        user_data["user_history"].append(f"[{timestamp}] Hatalı giriş denemesi.")
        save_user_data()
        return False, message, None

# Flask routes
@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Banka Sistemi</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; color: #333; }
                .container { background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.1); text-align: center; max-width: 400px; width: 90%; animation: fadeIn 0.8s ease-out; }
                h1 { color: #0056b3; margin-bottom: 25px; font-size: 2.5em; font-weight: 600; }
                p { margin: 15px 0; font-size: 1.1em; line-height: 1.6; }
                a { color: #007bff; text-decoration: none; margin: 0 15px; font-weight: 500; transition: color 0.3s ease; }
                a:hover { color: #0056b3; text-decoration: underline; }
                @keyframes fadeIn { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Gökçen Bankıng welcome 44 EN BUYUK BAYBURT</h1>
                <p>
                    <a href="/login">Giriş Yap</a>
                    <a href="/register">Kayıt Ol</a>
                </p>
            </div>
        </body>
        </html>
    ''')

@app.route('/login', methods=['GET', 'POST'])
def login_route():
    message = request.args.get('message', '')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        success, msg, logged_in_username = login_web(username, password)
        if success:
            session['username'] = logged_in_username
            return redirect(url_for('dashboard'))
        else:
            # Explicitly redirect with the message on failure
            return redirect(url_for('login_route', message=msg))
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Giriş Yap</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; color: #333; }
                .container { background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.1); max-width: 400px; width: 90%; animation: slideIn 0.8s ease-out; }
                h1 { color: #0056b3; text-align: center; margin-bottom: 30px; font-size: 2em; font-weight: 600; }
                form p { margin-bottom: 20px; text-align: left; }
                form label { display: block; margin-bottom: 8px; color: #555; font-weight: 500; }
                form input[type="text"], form input[type="password"] { width: calc(100% - 22px); padding: 12px; border: 1px solid #ced4da; border-radius: 8px; font-size: 1em; transition: border-color 0.3s ease, box-shadow 0.3s ease; }
                form input[type="text"]:focus, form input[type="password"]:focus { border-color: #007bff; box-shadow: 0 0 0 0.2rem rgba(0,123,255,.25); outline: none; }
                form input[type="submit"] { width: 100%; padding: 12px; border: none; border-radius: 8px; background-color: #007bff; color: white; font-size: 1.1em; cursor: pointer; transition: background-color 0.3s ease, transform 0.2s ease; margin-top: 20px; }
                form input[type="submit"]:hover { background-color: #0056b3; transform: translateY(-2px); }
                .message { color: #dc3545; text-align: center; margin-bottom: 20px; font-weight: 500; animation: shake 0.5s; }
                .back-link { display: block; text-align: center; margin-top: 25px; color: #007bff; text-decoration: none; font-weight: 500; transition: color 0.3s ease; }
                .back-link:hover { color: #0056b3; text-decoration: underline; }
                @keyframes slideIn { from { opacity: 0; transform: translateY(-30px); } to { opacity: 1; transform: translateY(0); } }
                @keyframes shake { 0%, 100% { transform: translateX(0); } 10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); } 20%, 40%, 60%, 80% { transform: translateX(5px); } })
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Giriş Yap</h1>
                {% if message %}<p class="message">{{ message }}</p>{% endif %}
                <form method="post">
                    <p>
                        <label for="username">Kullanıcı Adı:</label>
                        <input type="text" id="username" name="username" required>
                    </p>
                    <p>
                        <label for="password">Parola:</label>
                        <input type="password" id="password" name="password" required>
                    </p>
                    <p>
                        <input type="submit" value="Giriş">
                    </p>
                </form>
                <a href="/" class="back-link">Ana Sayfa</a>
            </div>
        </body>
        </html>
    ''', message=message)

@app.route('/register', methods=['GET', 'POST'])
def register_route():
    message = ""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        security_q = request.form['security_question']
        security_a = request.form['security_answer']
        success, msg = register_user_web(username, password, security_q, security_a)
        message = msg
        if success:
            return redirect(url_for('login_route', message="Kayıt başarılı! Lütfen giriş yapın."))
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Kayıt Ol</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; color: #333; }
                .container { background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.1); max-width: 500px; width: 90%; animation: slideIn 0.8s ease-out; }
                h1 { color: #28a745; text-align: center; margin-bottom: 30px; font-size: 2em; font-weight: 600; }
                form p { margin-bottom: 20px; text-align: left; }
                form label { display: block; margin-bottom: 8px; color: #555; font-weight: 500; }
                form input[type="text"], form input[type="password"] { width: calc(100% - 22px); padding: 12px; border: 1px solid #ced4da; border-radius: 8px; font-size: 1em; transition: border-color 0.3s ease, box-shadow 0.3s ease; }
                form input[type="text"]:focus, form input[type="password"]:focus { border-color: #28a745; box-shadow: 0 0 0 0.2rem rgba(40,167,69,.25); outline: none; }
                form input[type="submit"] { width: 100%; padding: 12px; border: none; border-radius: 8px; background-color: #28a745; color: white; font-size: 1.1em; cursor: pointer; transition: background-color 0.3s ease, transform 0.2s ease; margin-top: 20px; }
                form input[type="submit"]:hover { background-color: #218838; transform: translateY(-2px); }
                .message { color: #dc3545; text-align: center; margin-bottom: 20px; font-weight: 500; animation: shake 0.5s; }
                .back-link { display: block; text-align: center; margin-top: 25px; color: #007bff; text-decoration: none; font-weight: 500; transition: color 0.3s ease; }
                .back-link:hover { color: #0056b3; text-decoration: underline; }
                @keyframes slideIn { from { opacity: 0; transform: translateY(-30px); } to { opacity: 1; transform: translateY(0); } }
                @keyframes shake { 0%, 100% { transform: translateX(0); } 10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); } 20%, 40%, 60%, 80% { transform: translateX(5px); } }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Kayıt Ol</h1>
                {% if message %}<p class="message">{{ message }}</p>{% endif %}
                <form method="post">
                    <p>
                        <label for="username">Yeni Kullanıcı Adı:</label>
                        <input type="text" id="username" name="username" required>
                    </p>
                    <p>
                        <label for="password">Yeni Parola:</label>
                        <input type="password" id="password" name="password" required>
                    </p>
                    <p>
                        <label for="security_question">Güvenlik Sorusu:</label>
                        <input type="text" id="security_question" name="security_question" required>
                    </p>
                    <p>
                        <label for="security_answer">Güvenlik Cevabı:</label>
                        <input type="text" id="security_answer" name="security_answer" required>
                    </p>
                    <p>
                        <input type="submit" value="Kayıt Ol">
                    </p>
                </form>
                <a href="/" class="back-link">Ana Sayfa</a>
            </div>
        </body>
        </html>
    ''', message=message)

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        return redirect(url_for('login_route'))
    username = session['username']
    user_data = users.get(username)
    if not user_data:
        return redirect(url_for('logout')) # Kullanıcı verisi bulunamazsa çıkış yap

    # Lockout check (moved here from console version)
    if user_data["lockout_until"] and datetime.datetime.fromisoformat(user_data["lockout_until"]) > datetime.datetime.now():
        locked_until_dt = datetime.datetime.fromisoformat(user_data["lockout_until"])
        remaining_time = locked_until_dt - datetime.datetime.now()
        hours, remainder = divmod(remaining_time.total_seconds(), 3600)
        minutes, seconds = divmod(remainder, 60)
        message = f"Hesabınız kilitli olduğu için işlem yapamazsınız. Lütfen {int(hours)} saat {int(minutes)} dakika {int(seconds)} saniye sonra tekrar deneyiniz."
        session.pop('username', None) # Kilitliyse oturumu kapat
        return redirect(url_for('login_route', message=message))

    user_accounts = user_data['accounts']
    return render_template_string('''
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Kontrol Paneli</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; color: #333; }
                .container { background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.1); max-width: 600px; width: 90%; animation: fadeIn 0.8s ease-out; }
                h1 { color: #0056b3; margin-bottom: 25px; font-size: 2.5em; font-weight: 600; text-align: center; }
                h2 { color: #007bff; margin-top: 30px; margin-bottom: 20px; font-size: 1.8em; font-weight: 500; text-align: center; }
                ul { list-style: none; padding: 0; margin: 20px 0; }
                ul li { background-color: #e9ecef; padding: 15px 20px; margin-bottom: 12px; border-radius: 8px; display: flex; justify-content: space-between; align-items: center; transition: transform 0.2s ease, box-shadow 0.2s ease; }
                ul li:hover { transform: translateY(-3px); box-shadow: 0 4px 8px rgba(0,0,0,0.1); }
                .account-details { flex-grow: 1; text-align: left; font-size: 1.1em; }
                .account-details strong { color: #0056b3; font-weight: 600; }
                .account-actions a { margin-left: 15px; color: #28a745; text-decoration: none; font-weight: 500; padding: 8px 12px; border-radius: 5px; border: 1px solid #28a745; transition: background-color 0.3s ease, color 0.3s ease; }
                .account-actions a:hover { background-color: #28a745; color: white; text-decoration: none; }
                .logout-link { display: block; text-align: center; margin-top: 30px; color: #dc3545; text-decoration: none; font-weight: 500; font-size: 1.1em; transition: color 0.3s ease; }
                .logout-link:hover { color: #c82333; text-decoration: underline; }
                @keyframes fadeIn { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Hoş Geldiniz, {{ username }}!</h1>
                <h2>Hesaplarınız:</h2>
                <ul>
                    {% for account_name, account_info in accounts.items() %}
                    <li>
                        <div class="account-details">
                            <strong>{{ account_name }}</strong> (Bakiye: {{ '{:,.2f}'.format(account_info.bakiye) }} TL)
                        </div>
                        <div class="account-actions">
                            <a href="{{ url_for('account_operations', account_name=account_name) }}">İşlemler</a>
                        </div>
                    </li>
                    {% endfor %}
                </ul>
                <a href="/logout" class="logout-link">Çıkış Yap</a>
            </div>
        </body>
        </html>
    ''', username=username, accounts=user_accounts)

@app.route('/account/<account_name>')
def account_operations(account_name):
    if 'username' not in session:
        return redirect(url_for('login_route'))
    username = session['username']
    user_data = users.get(username)
    if not user_data or account_name not in user_data['accounts']:
        return redirect(url_for('dashboard')) # Geçersiz hesap veya kullanıcı yoksa kontrol paneline dön

    selected_account = user_data['accounts'][account_name]
    message = request.args.get('message', '') # Get messages from redirects

    return render_template_string('''
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{{ account_name }} Hesap İşlemleri</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; color: #333; }
                .container { background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.1); max-width: 500px; width: 90%; animation: fadeIn 0.8s ease-out; }
                h1 { color: #0056b3; text-align: center; margin-bottom: 30px; font-size: 2em; font-weight: 600; }
                ul { list-style: none; padding: 0; margin: 20px 0; }
                ul li { background-color: #e9ecef; padding: 15px 20px; margin-bottom: 10px; border-radius: 8px; transition: transform 0.2s ease, box-shadow 0.2s ease; }
                ul li:hover { background-color: #dbe3eb; transform: translateY(-2px); }
                ul li a { color: #007bff; text-decoration: none; display: block; font-size: 1.1em; font-weight: 500; transition: color 0.3s ease; }
                ul li a:hover { color: #0056b3; }
                .back-link, .home-link { display: block; text-align: center; margin-top: 30px; color: #6c757d; text-decoration: none; font-weight: 500; transition: color 0.3s ease; }
                .back-link:hover, .home-link:hover { color: #495057; text-decoration: underline; }
                .message { text-align: center; margin-bottom: 20px; padding: 10px; border-radius: 8px; font-weight: 500; }
                .message.success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; animation: slideInFromTop 0.5s ease; }
                .message.error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; animation: shake 0.5s; }
                @keyframes fadeIn { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
                @keyframes slideInFromTop { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
                @keyframes shake { 0%, 100% { transform: translateX(0); } 10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); } 20%, 40%, 60%, 80% { transform: translateX(5px); } }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{{ account_name }} Hesabı İşlemleri</h1>
                {% if message %}<p class="message {% if 'Hata' not in message %}success{% else %}error{% endif %}">{{ message }}</p>{% endif %}
                <ul>
                    <li><a href="{{ url_for('withdraw_route', account_name=account_name) }}">1. Para Çekme</a></li>
                    <li><a href="{{ url_for('deposit_route', account_name=account_name) }}">2. Para Yatırma</a></li>
                    <li><a href="{{ url_for('balance_route', account_name=account_name) }}">3. Bakiye Sorgulama</a></li>
                    <li><a href="{{ url_for('history_route', account_name=account_name) }}">4. Geçmiş İşlemler</a></li>
                    <li><a href="{{ url_for('external_transfer_route', account_name=account_name) }}">5. Havale/EFT (Diğer kullanıcılara)</a></li>
                    <li><a href="{{ url_for('internal_transfer_route', account_name=account_name) }}">6. Hesaplarım Arası Havale</a></li>
                    <li><a href="{{ url_for('change_password_route', account_name=account_name) }}">7. Parola Değiştir</a></li>
                    <li><a href="{{ url_for('user_history_route', account_name=account_name) }}">8. Kullanıcı Hareket Geçmişi</a></li>
                </ul>
                <a href="{{ url_for('dashboard') }}" class="back-link">Hesap Seçimine Geri Dön</a>
                <a href="/logout" class="home-link">Çıkış Yap</a>
            </div>
        </body>
        </html>
    ''', username=username, account_name=account_name, account_info=selected_account, message=message)


@app.route('/account/<account_name>/withdraw', methods=['GET', 'POST'])
def withdraw_route(account_name):
    if 'username' not in session:
        return redirect(url_for('login_route'))
    username = session['username']
    user_data = users.get(username)
    if not user_data or account_name not in user_data['accounts']:
        return redirect(url_for('dashboard'))

    selected_account = user_data['accounts'][account_name]
    message = ""

    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])

            if amount <= 0:
                message = "Hata: Çekilecek tutar pozitif olmalıdır."
            elif selected_account["bakiye"] - amount < 0:
                message = f"Yetersiz bakiye! Hesabınızda {selected_account['bakiye']:.2f} TL var."
            elif amount < 50 or amount % 50 != 0:
                message = "En az 50 TL ve 50'nin katlarında para çekebilirsiniz."
            else:
                today_str = datetime.date.today().isoformat()

                if user_data["last_withdrawal_date"] != today_str:
                    user_data["current_day_withdrawal_amount"] = 0.0
                    user_data["last_withdrawal_date"] = today_str

                proposed_total_withdrawal = amount + user_data["current_day_withdrawal_amount"]

                if proposed_total_withdrawal > user_data["daily_withdrawal_limit"]:
                    remaining_limit = user_data["daily_withdrawal_limit"] - user_data["current_day_withdrawal_amount"]
                    message = f"Hata: Günlük çekim limitini aşmaktasınız. Kalan günlük çekim limitiniz: {remaining_limit:.2f} TL. Bugüne kadar çektiğiniz: {user_data['current_day_withdrawal_amount']:.2f} TL."
                else:
                    selected_account["bakiye"] -= amount
                    user_data["current_day_withdrawal_amount"] += amount

                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    selected_account["işlem_geçmişi"].append(f"[{timestamp}] Para Çekme: {amount:.2f} TL. Kalan Bakiye: {selected_account['bakiye']:.2f} TL")
                    user_data["user_history"].append(f"[{timestamp}] '{account_name}' hesabından {amount:.2f} TL çekildi.")
                    save_user_data()
                    message = f"Çekilen tutar: {amount:.2f} TL. Kalan bakiye: {selected_account['bakiye']:.2f} TL"
        except ValueError:
            message = "Hata: Geçersiz tutar girdiniz. Lütfen sayısal bir değer giriniz."

    return render_template_string('''
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Para Çekme</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; color: #333; }
                .container { background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.1); max-width: 450px; width: 90%; animation: slideIn 0.8s ease-out; }
                h1 { color: #0056b3; text-align: center; margin-bottom: 30px; font-size: 2em; font-weight: 600; }
                .message { text-align: center; margin-bottom: 20px; padding: 10px; border-radius: 8px; font-weight: 500; }
                .message.success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; animation: slideInFromTop 0.5s ease; }
                .message.error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; animation: shake 0.5s; }
                form p { margin-bottom: 20px; text-align: left; }
                form label { display: block; margin-bottom: 8px; color: #555; font-weight: 500; }
                form input[type="number"] { width: calc(100% - 22px); padding: 12px; border: 1px solid #ced4da; border-radius: 8px; font-size: 1em; transition: border-color 0.3s ease, box-shadow 0.3s ease; }
                form input[type="number"]:focus { border-color: #007bff; box-shadow: 0 0 0 0.2rem rgba(0,123,255,.25); outline: none; }
                form input[type="submit"] { width: 100%; padding: 12px; border: none; border-radius: 8px; background-color: #007bff; color: white; font-size: 1.1em; cursor: pointer; transition: background-color 0.3s ease, transform 0.2s ease; margin-top: 20px; }
                form input[type="submit"]:hover { background-color: #0056b3; transform: translateY(-2px); }
                .back-link { display: block; text-align: center; margin-top: 25px; color: #6c757d; text-decoration: none; font-weight: 500; transition: color 0.3s ease; }
                .back-link:hover { color: #495057; text-decoration: underline; }
                @keyframes slideIn { from { opacity: 0; transform: translateY(-30px); } to { opacity: 1; transform: translateY(0); } }
                @keyframes slideInFromTop { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
                @keyframes shake { 0%, 100% { transform: translateX(0); } 10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); } 20%, 40%, 60%, 80% { transform: translateX(5px); } }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{{ account_name }} Hesabından Para Çekme</h1>
                {% if message %}<p class="message {% if 'Hata' not in message %}success{% else %}error{% endif %}">{{ message }}</p>{% endif %}
                <form method="post">
                    <p>
                        <label for="amount">Çekilecek Tutar:</label>
                        <input type="number" id="amount" name="amount" step="50" min="50" required>
                    </p>
                    <p>
                        <input type="submit" value="Para Çek">
                    </p>
                </form>
                <a href="{{ url_for('account_operations', account_name=account_name) }}" class="back-link">Geri Dön</a>
            </div>
        </body>
        </html>
    ''', account_name=account_name, message=message)

@app.route('/account/<account_name>/deposit', methods=['GET', 'POST'])
def deposit_route(account_name):
    if 'username' not in session:
        return redirect(url_for('login_route'))
    username = session['username']
    user_data = users.get(username)
    if not user_data or account_name not in user_data['accounts']:
        return redirect(url_for('dashboard'))

    selected_account = user_data['accounts'][account_name]
    message = ""

    if request.method == 'POST':
        try:
            amount = float(request.form['amount'])

            if amount <= 0:
                message = "Hata: Yatırılacak tutar pozitif olmalıdır."
            elif amount < 50 or amount % 50 != 0:
                message = "En az 50 TL ve 50'nin katlarında para yatırabilirsiniz."
            else:
                selected_account["bakiye"] += amount
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                selected_account["işlem_geçmişi"].append(f"[{timestamp}] Para Yatırma: {amount:.2f} TL. Güncel Bakiye: {selected_account['bakiye']:.2f} TL")
                user_data["user_history"].append(f"[{timestamp}] '{account_name}' hesabına {amount:.2f} TL yatırıldı.")
                save_user_data()
                message = f"Yatırılan tutar: {amount:.2f} TL. Güncel bakiye: {selected_account['bakiye']:.2f} TL"
        except ValueError:
            message = "Hata: Geçersiz tutar girdiniz. Lütfen sayısal bir değer giriniz."

    return render_template_string('''
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Para Yatırma</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; color: #333; }
                .container { background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.1); max-width: 450px; width: 90%; animation: slideIn 0.8s ease-out; }
                h1 { color: #28a745; text-align: center; margin-bottom: 30px; font-size: 2em; font-weight: 600; }
                .message { text-align: center; margin-bottom: 20px; padding: 10px; border-radius: 8px; font-weight: 500; }
                .message.success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; animation: slideInFromTop 0.5s ease; }
                .message.error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; animation: shake 0.5s; }
                form p { margin-bottom: 20px; text-align: left; }
                form label { display: block; margin-bottom: 8px; color: #555; font-weight: 500; }
                form input[type="number"] { width: calc(100% - 22px); padding: 12px; border: 1px solid #ced4da; border-radius: 8px; font-size: 1em; transition: border-color 0.3s ease, box-shadow 0.3s ease; }
                form input[type="number"]:focus { border-color: #28a745; box-shadow: 0 0 0 0.2rem rgba(40,167,69,.25); outline: none; }
                form input[type="submit"] { width: 100%; padding: 12px; border: none; border-radius: 8px; background-color: #28a745; color: white; font-size: 1.1em; cursor: pointer; transition: background-color 0.3s ease, transform 0.2s ease; margin-top: 20px; }
                form input[type="submit"]:hover { background-color: #218838; transform: translateY(-2px); }
                .back-link { display: block; text-align: center; margin-top: 25px; color: #6c757d; text-decoration: none; font-weight: 500; transition: color 0.3s ease; }
                .back-link:hover { color: #495057; text-decoration: underline; }
                @keyframes slideIn { from { opacity: 0; transform: translateY(-30px); } to { opacity: 1; transform: translateY(0); } }
                @keyframes slideInFromTop { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
                @keyframes shake { 0%, 100% { transform: translateX(0); } 10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); } 20%, 40%, 60%, 80% { transform: translateX(5px); } }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{{ account_name }} Hesabına Para Yatırma</h1>
                {% if message %}<p class="message {% if 'Hata' not in message %}success{% else %}error{% endif %}">{{ message }}</p>{% endif %}
                <form method="post">
                    <p>
                        <label for="amount">Yatırılacak Tutar:</label>
                        <input type="number" id="amount" name="amount" step="50" min="50" required>
                    </p>
                    <p>
                        <input type="submit" value="Para Yatır">
                    </p>
                </form>
                <a href="{{ url_for('account_operations', account_name=account_name) }}" class="back-link">Geri Dön</a>
            </div>
        </body>
        </html>
    ''', account_name=account_name, message=message)

@app.route('/account/<account_name>/balance')
def balance_route(account_name):
    if 'username' not in session:
        return redirect(url_for('login_route'))
    username = session['username']
    user_data = users.get(username)
    if not user_data or account_name not in user_data['accounts']:
        return redirect(url_for('dashboard'))

    selected_account = user_data['accounts'][account_name]
    current_balance = selected_account['bakiye']

    # Record balance inquiry in user history
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    selected_account["işlem_geçmişi"].append(f"[{timestamp}] Bakiye Sorgulama: {current_balance:.2f} TL")
    user_data["user_history"].append(f"[{timestamp}] '{account_name}' bakiyesi sorgulandı.")
    save_user_data()

    return render_template_string('''
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Bakiye Sorgulama</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; color: #333; }
                .container { background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.1); max-width: 400px; width: 90%; animation: fadeIn 0.8s ease-out; }
                h1 { color: #0056b3; text-align: center; margin-bottom: 25px; font-size: 2em; font-weight: 600; }
                .balance-info { text-align: center; margin-top: 30px; }
                .balance-label { font-size: 1.2em; color: #555; margin-bottom: 10px; }
                .balance-amount { font-size: 2.5em; font-weight: bold; color: #28a745; margin-top: 10px; letter-spacing: 0.05em; }
                .back-link { display: block; text-align: center; margin-top: 40px; color: #6c757d; text-decoration: none; font-weight: 500; transition: color 0.3s ease; }
                .back-link:hover { color: #495057; text-decoration: underline; }
                @keyframes fadeIn { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{{ account_name }} Hesabı Bakiye Sorgulama</h1>
                <div class="balance-info">
                    <p class="balance-label">Hesabınızdaki güncel bakiye:</p>
                    <p class="balance-amount">{{ '{:,.2f}'.format(current_balance) }} TL</p>
                </div>
                <a href="{{ url_for('account_operations', account_name=account_name) }}" class="back-link">Geri Dön</a>
            </div>
        </body>
        </html>
    ''', account_name=account_name, current_balance=current_balance)

@app.route('/account/<account_name>/history')
def history_route(account_name):
    if 'username' not in session:
        return redirect(url_for('login_route'))
    username = session['username']
    user_data = users.get(username)
    if not user_data or account_name not in user_data['accounts']:
        return redirect(url_for('dashboard'))

    selected_account = user_data['accounts'][account_name]
    # Display last 10 transactions, newest first
    transaction_history = selected_account['işlem_geçmişi'][-10:][::-1]

    return render_template_string('''
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>İşlem Geçmişi</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; color: #333; }
                .container { background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.1); max-width: 700px; width: 90%; animation: fadeIn 0.8s ease-out; }
                h1 { color: #0056b3; text-align: center; margin-bottom: 30px; font-size: 2em; font-weight: 600; }
                .history-list { list-style: none; padding: 0; max-height: 350px; overflow-y: auto; border: 1px solid #e0e6ed; border-radius: 8px; background-color: #fdfefe; margin-bottom: 20px; }
                .history-list li { padding: 12px 15px; border-bottom: 1px solid #f0f0f0; text-align: left; font-size: 0.95em; line-height: 1.4; }
                .history-list li:last-child { border-bottom: none; }
                .no-history { text-align: center; color: #777; padding: 30px; font-size: 1.1em; background-color: #f8f9fa; border: 1px solid #e0e6ed; border-radius: 8px; }
                .back-link { display: block; text-align: center; margin-top: 30px; color: #6c757d; text-decoration: none; font-weight: 500; transition: color 0.3s ease; }
                .back-link:hover { color: #495057; text-decoration: underline; }
                @keyframes fadeIn { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{{ account_name }} Hesabı İşlem Geçmişi</h1>
                {% if transaction_history %}
                <ul class="history-list">
                    {% for transaction in transaction_history %}
                    <li>{{ transaction }}</li>
                    {% endfor %}
                </ul>
                {% else %}
                <p class="no-history">Bu hesapta henüz bir işlem kaydı yok.</p>
                {% endif %}
                <a href="{{ url_for('account_operations', account_name=account_name) }}" class="back-link">Geri Dön</a>
            </div>
        </body>
        </html>
    ''', account_name=account_name, transaction_history=transaction_history)

@app.route('/account/<account_name>/internal_transfer', methods=['GET', 'POST'])
def internal_transfer_route(account_name):
    if 'username' not in session:
        return redirect(url_for('login_route'))
    username = session['username']
    user_data = users.get(username)
    if not user_data or account_name not in user_data['accounts']:
        return redirect(url_for('dashboard'))

    selected_account = user_data['accounts'][account_name] # This is the currently selected account for operations
    user_accounts = user_data['accounts']
    message = request.args.get('message', '')

    if request.method == 'POST':
        try:
            source_account_name = request.form['source_account']
            destination_account_name = request.form['destination_account']
            amount = float(request.form['amount'])

            if source_account_name == destination_account_name:
                message = "Hata: Kaynak ve hedef hesap aynı olamaz. Lütfen farklı bir hedef hesap seçiniz."
            elif amount <= 0:
                message = "Hata: Transfer tutarı pozitif olmalıdır."
            elif source_account_name not in user_accounts or destination_account_name not in user_accounts:
                message = "Hata: Geçersiz kaynak veya hedef hesap seçimi."
            else:
                source_account = user_accounts[source_account_name]
                destination_account = user_accounts[destination_account_name]

                if source_account["bakiye"] < amount:
                    message = f"Yetersiz bakiye! {source_account_name} hesabınızda {source_account['bakiye']:.2f} TL var."
                else:
                    source_account["bakiye"] -= amount
                    destination_account["bakiye"] += amount
                    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    source_account["işlem_geçmişi"].append(f"[{timestamp}] Hesaplar Arası Havale: {amount:.2f} TL ({destination_account_name} hesabına). Kalan Bakiye: {source_account['bakiye']:.2f} TL")
                    destination_account["işlem_geçmişi"].append(f"[{timestamp}] Hesaplar Arası Havale: {amount:.2f} TL ({source_account_name} hesabından). Güncel Bakiye: {destination_account['bakiye']:.2f} TL")
                    user_data["user_history"].append(f"[{timestamp}] '{source_account_name}' hesabından '{destination_account_name}' hesabına {amount:.2f} TL dahili havale yapıldı.")

                    save_user_data()
                    message = f"Transfer başarılı! {source_account_name} hesabından {destination_account_name} hesabına {amount:.2f} TL gönderildi."
                    return redirect(url_for('account_operations', account_name=account_name, message=message))

        except ValueError:
            message = "Hata: Geçersiz tutar girdiniz. Lütfen sayısal bir değer giriniz."
        except Exception as e:
            message = f"Bir hata oluştu: {e}"

    return render_template_string('''
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Hesaplar Arası Havale</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; color: #333; }
                .container { background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.1); max-width: 500px; width: 90%; animation: slideIn 0.8s ease-out; }
                h1 { color: #0056b3; text-align: center; margin-bottom: 30px; font-size: 2em; font-weight: 600; }
                .message { text-align: center; margin-bottom: 20px; padding: 10px; border-radius: 8px; font-weight: 500; }
                .message.success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; animation: slideInFromTop 0.5s ease; }
                .message.error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; animation: shake 0.5s; }
                form p { margin-bottom: 20px; text-align: left; }
                form label { display: block; margin-bottom: 8px; color: #555; font-weight: 500; }
                form select, form input[type="number"] { width: calc(100% - 22px); padding: 12px; border: 1px solid #ced4da; border-radius: 8px; font-size: 1em; transition: border-color 0.3s ease, box-shadow 0.3s ease; }
                form input[type="number"]:focus { border-color: #007bff; box-shadow: 0 0 0 0.2rem rgba(0,123,255,.25); outline: none; }
                form input[type="submit"] { width: 100%; padding: 12px; border: none; border-radius: 8px; background-color: #007bff; color: white; font-size: 1.1em; cursor: pointer; transition: background-color 0.3s ease, transform 0.2s ease; margin-top: 20px; }
                form input[type="submit"]:hover { background-color: #0056b3; transform: translateY(-2px); }
                .back-link { display: block; text-align: center; margin-top: 25px; color: #6c757d; text-decoration: none; font-weight: 500; transition: color 0.3s ease; }
                .back-link:hover { color: #495057; text-decoration: underline; }
                @keyframes slideIn { from { opacity: 0; transform: translateY(-30px); } to { opacity: 1; transform: translateY(0); } }
                @keyframes slideInFromTop { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
                @keyframes shake { 0%, 100% { transform: translateX(0); } 10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); } 20%, 40%, 60%, 80% { transform: translateX(5px); } }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Hesaplar Arası Havale</h1>
                {% if message %}<p class="message {% if 'Hata' not in message %}success{% else %}error{% endif %}">{{ message }}</p>{% endif %}
                <form method="post">
                    <p>
                        <label for="source_account">Kaynak Hesap:</label>
                        <select id="source_account" name="source_account" class="form-select" required>
                            {% for acc_name, acc_info in user_accounts.items() %}
                                <option value="{{ acc_name }}" {% if acc_name == account_name %}selected{% endif %}>{{ acc_name }} (Bakiye: {{ '{:,.2f}'.format(acc_info.bakiye) }} TL)</option>
                            {% endfor %}
                        </select>
                    </p>
                    <p>
                        <label for="destination_account">Hedef Hesap:</label>
                        <select id="destination_account" name="destination_account" class="form-select" required>
                            {% for acc_name, acc_info in user_accounts.items() %}
                                <option value="{{ acc_name }}">{{ acc_name }} (Bakiye: {{ '{:,.2f}'.format(acc_info.bakiye) }} TL)</option>
                            {% endfor %}
                        </select>
                    </p>
                    <p>
                        <label for="amount">Tutar:</label>
                        <input type="number" id="amount" name="amount" step="any" min="0.01" class="form-control" required>
                    </p>
                    <p>
                        <input type="submit" value="Transfer Et">
                    </p>
                </form>
                <a href="{{ url_for('account_operations', account_name=account_name) }}" class="back-link">Geri Dön</a>
            </div>
        </body>
        </html>
    ''', account_name=account_name, user_accounts=user_accounts, message=message)

@app.route('/account/<account_name>/external_transfer', methods=['GET', 'POST'])
def external_transfer_route(account_name):
    if 'username' not in session:
        return redirect(url_for('login_route'))
    username = session['username']
    user_data = users.get(username)
    if not user_data or account_name not in user_data['accounts']:
        return redirect(url_for('dashboard'))

    selected_account = user_data['accounts'][account_name]
    message = request.args.get('message', '')
    havale_ucreti = 6.39

    if request.method == 'POST':
        recipient_username = request.form.get('recipient_username', '').strip()
        recipient_account_name = request.form.get('recipient_account_name', '').strip()
        amount_str = request.form.get('amount', '').strip()

        if recipient_username.lower() == 'c' or recipient_account_name.lower() == 'c' or amount_str.lower() == 'c':
            message = "Havale işlemi iptal edildi."
            return redirect(url_for('account_operations', account_name=account_name, message=message))

        try:
            amount = float(amount_str)
            if amount <= 0:
                message = "Hata: Gönderilecek tutar pozitif olmalıdır."
            elif recipient_username == username:
                message = "Hata: Kendi hesabınıza harici havale yapamazsınız. Hesaplarım Arası Havale'yi kullanın."
            elif recipient_username not in users:
                message = "Hata: Belirtilen kullanıcı bulunamadı."
            else:
                recipient_user_data = users[recipient_username]
                if recipient_account_name not in recipient_user_data['accounts']:
                    message = "Hata: Alıcının belirtilen hesabı bulunamadı."
                else:
                    recipient_account = recipient_user_data['accounts'][recipient_account_name]
                    total_deduction = amount + havale_ucreti

                    if selected_account["bakiye"] < total_deduction:
                        message = f"Yetersiz bakiye! İşlem için {total_deduction} TL gerekmektedir. Mevcut bakiyeniz: {selected_account['bakiye']} TL."
                    else:
                        selected_account["bakiye"] -= total_deduction
                        recipient_account["bakiye"] += amount

                        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        selected_account["işlem_geçmişi"].append(f"[{timestamp}] Havale/EFT: {amount} TL (alıcı: {recipient_username} - {recipient_account_name}), Ücret: {havale_ucreti} TL. Kalan Bakiye: {selected_account['bakiye']} TL")
                        user_data["user_history"].append(f"[{timestamp}] '{account_name}' hesabından '{recipient_username}' kullanıcısının '{recipient_account_name}' hesabına {amount} TL havale yapıldı.")
                        recipient_account["işlem_geçmişi"].append(f"[{timestamp}] Havale/EFT: {amount} TL (gönderen: {username} - {account_name}). Güncel Bakiye: {recipient_account['bakiye']} TL")

                        save_user_data()
                        message = f"Transfer başarılı! '{recipient_username}' kullanıcısının '{recipient_account_name}' hesabına {amount} TL gönderildi. Havale ücreti: {havale_ucreti} TL."
                        return redirect(url_for('account_operations', account_name=account_name, message=message))

        except ValueError:
            message = "Hata: Geçersiz tutar girdiniz. Lütfen sayısal bir değer giriniz."
        except Exception as e:
            message = f"Bir hata oluştu: {e}"

    return render_template_string('''
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Harici Havale/EFT</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; color: #333; }
                .container { background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.1); max-width: 500px; width: 90%; animation: slideIn 0.8s ease-out; }
                h1 { color: #0056b3; text-align: center; margin-bottom: 30px; font-size: 2em; font-weight: 600; }
                .message { text-align: center; margin-bottom: 20px; padding: 10px; border-radius: 8px; font-weight: 500; }
                .message.success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; animation: slideInFromTop 0.5s ease; }
                .message.error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; animation: shake 0.5s; }
                form p { margin-bottom: 20px; text-align: left; }
                form label { display: block; margin-bottom: 8px; color: #555; font-weight: 500; }
                form input[type="text"], form input[type="number"] { width: calc(100% - 22px); padding: 12px; border: 1px solid #ced4da; border-radius: 8px; font-size: 1em; transition: border-color 0.3s ease, box-shadow 0.3s ease; }
                form input[type="text"]:focus, form input[type="number"]:focus { border-color: #007bff; box-shadow: 0 0 0 0.2rem rgba(0,123,255,.25); outline: none; }
                form input[type="submit"] { width: 100%; padding: 12px; border: none; border-radius: 8px; background-color: #007bff; color: white; font-size: 1.1em; cursor: pointer; transition: background-color 0.3s ease, transform 0.2s ease; margin-top: 20px; }
                form input[type="submit"]:hover { background-color: #0056b3; transform: translateY(-2px); }
                .back-link { display: block; text-align: center; margin-top: 25px; color: #6c757d; text-decoration: none; font-weight: 500; transition: color 0.3s ease; }
                .back-link:hover { color: #495057; text-decoration: underline; }
                @keyframes slideIn { from { opacity: 0; transform: translateY(-30px); } to { opacity: 1; transform: translateY(0); } }
                @keyframes slideInFromTop { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
                @keyframes shake { 0%, 100% { transform: translateX(0); } 10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); } 20%, 40%, 60%, 80% { transform: translateX(5px); } }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Harici Havale/EFT İşlemi</h1>
                {% if message %}<p class="message {% if 'Hata' not in message %}success{% else %}error{% endif %}">{{ message }}</p>{% endif %}
                <form method="post">
                    <p>
                        <label for="recipient_username">Alıcı Kullanıcı Adı (İptal için 'c'):</label>
                        <input type="text" id="recipient_username" name="recipient_username" required>
                    </p>
                    <p>
                        <label for="recipient_account_name">Alıcı Hesap Adı (örn: Vadesiz, Birikim) (İptal için 'c'):</label>
                        <input type="text" id="recipient_account_name" name="recipient_account_name" required>
                    </p>
                    <p>
                        <label for="amount">Gönderilecek Tutar (İptal için 'c'):</label>
                        <input type="number" id="amount" name="amount" step="any" min="0.01" required>
                    </p>
                    <p>
                        <input type="submit" value="Havale Yap">
                    </p>
                </form>
                <a href="{{ url_for('account_operations', account_name=account_name) }}" class="back-link">Geri Dön</a>
            </div>
        </body>
        </html>
    ''', account_name=account_name, message=message, havale_ucreti=havale_ucreti)


@app.route('/user/<account_name>/user_history') # Updated route for user history
def user_history_route(account_name):
    if 'username' not in session:
        return redirect(url_for('login_route'))
    username = session['username']
    user_data = users.get(username)
    if not user_data:
        return redirect(url_for('logout'))

    user_activity_history = user_data['user_history'][-10:][::-1] # Son 10 hareketi al ve en yeniyi başa getir

    return render_template_string('''
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Kullanıcı Hareket Geçmişi</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; color: #333; }
                .container { background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.1); max-width: 700px; width: 90%; animation: fadeIn 0.8s ease-out; }
                h1 { color: #0056b3; text-align: center; margin-bottom: 30px; font-size: 2em; font-weight: 600; }
                .history-list { list-style: none; padding: 0; max-height: 350px; overflow-y: auto; border: 1px solid #e0e6ed; border-radius: 8px; background-color: #fdfefe; margin-bottom: 20px; }
                .history-list li { padding: 12px 15px; border-bottom: 1px solid #f0f0f0; text-align: left; font-size: 0.95em; line-height: 1.4; }
                .history-list li:last-child { border-bottom: none; }
                .no-history { text-align: center; color: #777; padding: 30px; font-size: 1.1em; background-color: #f8f9fa; border: 1px solid #e0e6ed; border-radius: 8px; }
                .back-link { display: block; text-align: center; margin-top: 30px; color: #6c757d; text-decoration: none; font-weight: 500; transition: color 0.3s ease; }
                .back-link:hover { color: #495057; text-decoration: underline; }
                @keyframes fadeIn { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Kullanıcı Hareket Geçmişi</h1>
                {% if user_activity_history %}
                <ul class="history-list">
                    {% for activity in user_activity_history %}
                    <li>{{ activity }}</li>
                    {% endfor %}
                </ul>
                {% else %}
                <p class="no-history">Henüz bir kullanıcı hareket kaydı yok.</p>
                {% endif %}
                <a href="{{ url_for('account_operations', account_name=account_name) }}" class="back-link">Geri Dön</a>
            </div>
        </body>
        </html>
    ''', account_name=account_name, user_activity_history=user_activity_history)


@app.route('/account/<account_name>/change_password', methods=['GET', 'POST'])
def change_password_route(account_name):
    if 'username' not in session:
        return redirect(url_for('login_route'))
    username = session['username']
    user_data = users.get(username)
    if not user_data:
        return redirect(url_for('logout'))

    message = request.args.get('message', '')

    # Check if user is currently locked out
    if user_data["lockout_until"] and datetime.datetime.fromisoformat(user_data["lockout_until"]) > datetime.datetime.now():
        locked_until_dt = datetime.datetime.fromisoformat(user_data["lockout_until"])
        print(f"Hesabınız kilitli. Lütfen {locked_until_dt.strftime('%H:%M:%S')} tarihine kadar bekleyiniz.")
        return redirect(url_for('account_operations', account_name=account_name, message="Hesabınız kilitli olduğu için parola değiştiremezsiniz."))

    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']

        attempts = session.get('change_password_attempts', 0)
        MAX_ATTEMPTS = 3

        if user_data["parola"] == current_password:
            # Correct password, reset failed attempts and lockout
            user_data["failed_password_attempts"] = 0
            user_data["lockout_until"] = None
            session['change_password_attempts'] = 0

            # Password policy checks for new password
            has_uppercase = any(char.isupper() for char in new_password)
            has_digit = any(char.isdigit() for char in new_password)

            if not has_uppercase or not has_digit:
                message = "Hata: Yeni parola en az bir büyük harf ve bir rakam içermelidir."
            else:
                user_data["parola"] = new_password
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                user_data["user_history"].append(f"[{timestamp}] Parola değiştirildi.")
                save_user_data()
                message = "Parolanız başarıyla değiştirildi."
                return redirect(url_for('account_operations', account_name=account_name, message=message))
        else:
            attempts += 1
            session['change_password_attempts'] = attempts
            user_data["failed_password_attempts"] += 1

            if attempts >= MAX_ATTEMPTS:
                current_failed_attempts_for_cpw = user_data["failed_password_attempts"]
                lockout_duration_minutes = 2 ** current_failed_attempts_for_cpw
                lockout_time = datetime.datetime.now() + datetime.timedelta(minutes=lockout_duration_minutes)
                user_data["lockout_until"] = lockout_time.isoformat()
                message = f"Hata: Mevcut parola yanlış. Çok fazla hatalı deneme. Hesabınız {lockout_duration_minutes} dakika kilitlendi."
                session.pop('username', None) # Kilitlendiği için oturumu kapat
                save_user_data()
                return redirect(url_for('login_route', message=message))
            else:
                message = f"Hata: Mevcut parola yanlış. Kalan deneme hakkı: {MAX_ATTEMPTS - attempts}"
            save_user_data() # Save failed attempt count after each try

    return render_template_string('''
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Parola Değiştir</title>
            <style>
                body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f0f2f5; margin: 0; display: flex; justify-content: center; align-items: center; height: 100vh; color: #333; }
                .container { background-color: #ffffff; padding: 40px; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.1); max-width: 450px; width: 90%; animation: slideIn 0.8s ease-out; }
                h1 { color: #0056b3; text-align: center; margin-bottom: 30px; font-size: 2em; font-weight: 600; }
                .message { text-align: center; margin-bottom: 20px; padding: 10px; border-radius: 8px; font-weight: 500; }
                .message.success { background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; animation: slideInFromTop 0.5s ease; }
                .message.error { background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; animation: shake 0.5s; }
                form p { margin-bottom: 20px; text-align: left; }
                form label { display: block; margin-bottom: 8px; color: #555; font-weight: 500; }
                form input[type="password"] { width: calc(100% - 22px); padding: 12px; border: 1px solid #ced4da; border-radius: 8px; font-size: 1em; transition: border-color 0.3s ease, box-shadow 0.3s ease; }
                form input[type="password"]:focus { border-color: #007bff; box-shadow: 0 0 0 0.2rem rgba(0,123,255,.25); outline: none; }
                form input[type="submit"] { width: 100%; padding: 12px; border: none; border-radius: 8px; background-color: #007bff; color: white; font-size: 1.1em; cursor: pointer; transition: background-color 0.3s ease, transform 0.2s ease; margin-top: 20px; }
                form input[type="submit"]:hover { background-color: #0056b3; transform: translateY(-2px); }
                .back-link { display: block; text-align: center; margin-top: 25px; color: #6c757d; text-decoration: none; font-weight: 500; transition: color 0.3s ease; }
                .back-link:hover { color: #495057; text-decoration: underline; }
                @keyframes slideIn { from { opacity: 0; transform: translateY(-30px); } to { opacity: 1; transform: translateY(0); } }
                @keyframes slideInFromTop { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
                @keyframes shake { 0%, 100% { transform: translateX(0); } 10%, 30%, 50%, 70%, 90% { transform: translateX(-5px); } 20%, 40%, 60%, 80% { transform: translateX(5px); } }
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Parola Değiştir</h1>
                {% if message %}<p class="message {% if 'Hata' not in message %}success{% else %}error{% endif %}">{{ message }}</p>{% endif %}
                <form method="post">
                    <p>
                        <label for="current_password">Mevcut Parolanız:</label>
                        <input type="password" id="current_password" name="current_password" required>
                    </p>
                    <p>
                        <label for="new_password">Yeni Parolanız:</label>
                        <input type="password" id="new_password" name="new_password" required>
                    </p>
                    <p>
                        <input type="submit" value="Parolayı Değiştir">
                    </p>
                </form>
                <a href="{{ url_for('account_operations', account_name=account_name) }}" class="back-link">Geri Dön</a>
            </div>
        </body>
        </html>
    ''', account_name=account_name, message=message)

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('home'))

# Call load_user_data outside of any request context
load_user_data()

if __name__ == '__main__':
    app.run(debug=False, use_reloader=False, port=8000)
