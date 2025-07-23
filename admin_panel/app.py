import os
import uuid
import json
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore, storage

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY")

try:
    cred = credentials.Certificate("service_account.json")
    firebase_admin.initialize_app(cred, {
        'storageBucket': 'shrutipaath-app-c3db2.appspot.com'
    })
    db = firestore.client()
    bucket = storage.bucket()
except Exception as e:
    print(f"Firebase initialization error: {e}")
    db = None
    bucket = None

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# --- আগের রুটগুলো অপরিবর্তিত ---
@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username == os.getenv('ADMIN_USERNAME') and password == os.getenv('ADMIN_PASSWORD'):
            session['logged_in'] = True
            flash('সফলভাবে লগইন করেছেন!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('ভুল ইউজারনেম বা পাসওয়ার্ড।', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('সফলভাবে লগআউট হয়েছেন।', 'info')
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    config = {}
    subjects = []
    if db:
        config_ref = db.collection('config').document('app_settings').get()
        config = config_ref.to_dict() if config_ref.exists else {}
        subjects_ref = db.collection('subjects').order_by('order').stream()
        subjects = [{'id': doc.id, **doc.to_dict()} for doc in subjects_ref]
    return render_template('dashboard.html', config=config, subjects=subjects)

@app.route('/manage_notices', methods=['POST'])
@login_required
def manage_notices():
    # ... (অপরিবর্তিত)
    if not db:
        flash('ডেটাবেস সংযোগে সমস্যা।', 'danger')
        return redirect(url_for('dashboard'))
    try:
        scrolling_notice = request.form['scrollingNotice']
        db.collection('config').document('app_settings').set({
            'scrollingNotice': {'text': scrolling_notice}
        }, merge=True)
        flash('নোটিশ সফলভাবে আপডেট করা হয়েছে!', 'success')
    except Exception as e:
        flash(f'একটি ত্রুটি ঘটেছে: {e}', 'danger')
    return redirect(url_for('dashboard'))

@app.route('/manage_content', methods=['GET', 'POST'])
@login_required
def manage_content():
    if request.method == 'POST':
        if not db:
            flash('ডেটাবেস সংযোগে সমস্যা।', 'danger')
            return redirect(url_for('dashboard'))
        try:
            subject_name = request.form['subjectName']
            order = int(request.form['order'])
            is_active = 'isActive' in request.form
            
            audio_options_str = request.form.get('audioOptionsTemplate', '[]')
            audio_options_template = json.loads(audio_options_str)

            new_subject = {
                'subjectName': subject_name,
                'order': order,
                'is_active': is_active,
                'audio_options_template': audio_options_template,
                'chapters': []
            }
            
            db.collection('subjects').add(new_subject)
            flash(f'বিষয় "{subject_name}" সফলভাবে যোগ করা হয়েছে!', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            flash(f'একটি ত্রুটি ঘটেছে: {e}', 'danger')
    return render_template('manage_content.html', subject=None)

@app.route('/edit_content/<subject_id>', methods=['GET', 'POST'])
@login_required
def edit_content(subject_id):
    if not db:
        flash('ডেটাবেস সংযোগে সমস্যা।', 'danger')
        return redirect(url_for('dashboard'))
    subject_ref = db.collection('subjects').document(subject_id)
    
    if request.method == 'POST':
        try:
            subject_data = subject_ref.get().to_dict()
            chapters = subject_data.get('chapters', [])

            # --- অ্যাকশন অনুযায়ী কাজ করা ---

            # ১. বিষয়ের বিবরণ আপডেট করা
            if 'update_subject' in request.form:
                subject_ref.update({
                    'subjectName': request.form['subjectName'],
                    'order': int(request.form['order']),
                    'is_active': 'isActive' in request.form,
                    'audio_options_template': json.loads(request.form.get('audioOptionsTemplate', '[]'))
                })
                flash('বিষয়টি সফলভাবে আপডেট করা হয়েছে!', 'success')

            # ২. নতুন অধ্যায় যোগ করা
            elif 'add_chapter' in request.form:
                chapter_name = request.form['chapterName']
                new_chapter = {'chapterName': chapter_name, 'options': {}}
                
                for option in subject_data.get('audio_options_template', []):
                    option_key = option['key']
                    if option_key in request.files and request.files[option_key].filename != '':
                        file = request.files[option_key]
                        unique_filename = str(uuid.uuid4()) + "_" + file.filename
                        blob = bucket.blob(f"audio/{unique_filename}")
                        blob.upload_from_file(file, content_type=file.content_type)
                        blob.make_public()
                        new_chapter['options'][option_key] = blob.public_url
                
                chapters.append(new_chapter)
                subject_ref.update({'chapters': chapters})
                flash('নতুন অধ্যায় যোগ করা হয়েছে!', 'success')
            
            # ৩. অধ্যায় মুছে ফেলা
            elif 'delete_chapter' in request.form:
                chapter_index = int(request.form['chapter_index'])
                if 0 <= chapter_index < len(chapters):
                    del chapters[chapter_index]
                    subject_ref.update({'chapters': chapters})
                    flash('অধ্যায় মুছে ফেলা হয়েছে!', 'warning')

            # ৪. অধ্যায় এডিট/আপডেট করা
            elif 'update_chapter' in request.form:
                chapter_index = int(request.form['chapter_index'])
                if 0 <= chapter_index < len(chapters):
                    # অধ্যায়ের নাম আপডেট
                    chapters[chapter_index]['chapterName'] = request.form['chapterName']
                    
                    # নতুন অডিও ফাইল আপলোড (যদি থাকে)
                    for option in subject_data.get('audio_options_template', []):
                        option_key = option['key']
                        if option_key in request.files and request.files[option_key].filename != '':
                            file = request.files[option_key]
                            # পুরনো ফাইল স্টোরেজ থেকে ডিলিট করা যেতে পারে, কিন্তু আপাতত আমরা তা করছি না
                            unique_filename = str(uuid.uuid4()) + "_" + file.filename
                            blob = bucket.blob(f"audio/{unique_filename}")
                            blob.upload_from_file(file, content_type=file.content_type)
                            blob.make_public()
                            chapters[chapter_index]['options'][option_key] = blob.public_url
                    
                    subject_ref.update({'chapters': chapters})
                    flash('অধ্যায় সফলভাবে আপডেট করা হয়েছে!', 'success')

        except Exception as e:
            flash(f'একটি ত্রুটি ঘটেছে: {e}', 'danger')
        return redirect(url_for('edit_content', subject_id=subject_id))

    subject = subject_ref.get().to_dict()
    if not subject:
        flash('বিষয়টি খুঁজে পাওয়া যায়নি।', 'danger')
        return redirect(url_for('dashboard'))
        
    subject['id'] = subject_id
    # প্রতিটি অধ্যায়ের সাথে তার ইনডেক্স যোগ করা হচ্ছে, যা টেমপ্লেটে প্রয়োজন হবে
    for i, chapter in enumerate(subject.get('chapters', [])):
        chapter['index'] = i
        
    return render_template('manage_content.html', subject=subject)

@app.route('/delete_subject/<subject_id>', methods=['POST'])
@login_required
def delete_subject(subject_id):
    # ... (অপরিবর্তিত)
    if not db:
        flash('ডেটাবেস সংযোগে সমস্যা।', 'danger')
        return redirect(url_for('dashboard'))
    try:
        db.collection('subjects').document(subject_id).delete()
        flash('বিষয়টি সফলভাবে মুছে ফেলা হয়েছে!', 'success')
    except Exception as e:
        flash(f'মুছতে গিয়ে একটি ত্রুটি ঘটেছে: {e}', 'danger')
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    app.run(debug=True, port=5001)