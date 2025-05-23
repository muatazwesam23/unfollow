from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from instabot import Bot
import os
import traceback

app = Flask(__name__)
app.secret_key = 'your_secret_key'

bot = None
user_info = {}

def get_user_profile():
    global bot
    try:
        user_id = bot.user_id
        info = bot.get_user_info(user_id)
        print("USER INFO:", info)
        return {
            'username': info.get('username', ''),
            'full_name': info.get('full_name', ''),
            'bio': info.get('biography', ''),
            'profile_pic_url': info.get('profile_pic_url_hd') or info.get('profile_pic_url', ''),
            'followers': info.get('follower_count', 0),
            'following': info.get('following_count', 0),
            'media_count': info.get('media_count', 0),
            'is_private': info.get('is_private', False),
            'is_verified': info.get('is_verified', False),
            'external_url': info.get('external_url', ''),
            'user_id': user_id,
        }
    except Exception as e:
        print("Error in get_user_profile:", e)
        traceback.print_exc()
        return {}

def get_following():
    global bot
    try:
        user_id = bot.user_id
        following_ids = bot.get_user_following(user_id)
        users = []
        for uid in following_ids:
            info = bot.get_user_info(uid)
            users.append({
                'user_id': uid,
                'username': info.get('username', ''),
                'full_name': info.get('full_name', ''),
                'profile_pic_url': info.get('profile_pic_url_hd') or info.get('profile_pic_url', ''),
                'is_private': info.get('is_private', False),
                'is_verified': info.get('is_verified', False),
            })
        return users
    except Exception as e:
        print("Error in get_following:", e)
        traceback.print_exc()
        return []

def unfollow_user(user_id):
    global bot
    try:
        if bot:
            bot.unfollow(user_id)
            return True
    except Exception as e:
        print("Error in unfollow_user:", e)
        traceback.print_exc()
    return False

@app.route('/', methods=['GET'])
def index():
    if 'logged_in' in session and session['logged_in']:
        return redirect(url_for('profile'))
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    global bot, user_info
    username = request.form['username']
    password = request.form['password']
    try:
        if os.path.exists('config'):
            import shutil
            shutil.rmtree('config')
        bot = Bot()
        bot.login(username=username, password=password)
        session['logged_in'] = True
        user_info = get_user_profile()
        if not user_info.get('username'):
            flash("فشل في جلب معلومات الحساب. تأكد من صحة البيانات أو من عدم وجود حماية على الحساب.")
            return redirect(url_for('index'))
        return redirect(url_for('profile'))
    except Exception as e:
        print("Login error:", e)
        traceback.print_exc()
        flash(f"فشل تسجيل الدخول: {e}")
        return redirect(url_for('index'))

@app.route('/profile', methods=['GET'])
def profile():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('index'))
    global user_info
    user_info = get_user_profile()
    if not user_info.get('username'):
        flash("تعذر جلب معلومات الحساب. قد يكون هناك حماية على الحساب أو مشكلة في الاتصال بإنستغرام.")
        return redirect(url_for('index'))
    return render_template('profile.html', user=user_info)

@app.route('/following', methods=['GET'])
def following():
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('index'))
    users = get_following()
    return render_template('following.html', users=users)

@app.route('/unfollow', methods=['POST'])
def unfollow():
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'success': False, 'message': 'لم يتم تسجيل الدخول'})
    user_id = request.form['user_id']
    success = unfollow_user(user_id)
    return jsonify({'success': success})

@app.route('/logout', methods=['POST'])
def logout():
    global bot, user_info
    try:
        if bot:
            bot.logout()
    except Exception as e:
        print("Logout error:", e)
        traceback.print_exc()
    bot = None
    user_info = {}
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
