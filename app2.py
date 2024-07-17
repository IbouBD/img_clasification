import shutil
from flask import Flask, request, redirect, url_for, render_template, session, flash, send_file, jsonify
from werkzeug.utils import secure_filename
from flask_security import Security, SQLAlchemyUserDatastore, UserMixin, RoleMixin
from database import create_app, db, User, Role, user_datastore
from flask_security.utils import hash_password
from forms import UploadForm, RegistrationForm
from tasks import  process_images, celery
from utils import *
from celery.result import AsyncResult
from flask_bcrypt import Bcrypt


app, celery = create_app()
db.init_app(app=app)
bcrypt = Bcrypt(app)

@app.route("/", methods=["GET", "POST"])
async def index():
    if request.method == "POST":
        if 'files' not in request.files:
            flash('No file part')
            return redirect(request.url)

        files = request.files.getlist('files')
        nb_cluster = int(request.form.get('nb_cluster'))
        print("nb_cluster", nb_cluster)
        image_data = []

        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                image_data.append((filename, os.path.join(app.config['UPLOAD_FOLDER'], filename)))

        task = process_images.apply_async(args=[image_data, nb_cluster, app.config['UPLOAD_FOLDER'], app.config['SORTED_FOLDER']])
        #organize_task = organize_files.apply_async(args=[df, app.config['SORTED_FOLDER']])
        session['task_id'] = task.id
        
        return redirect(url_for('show_plot', task_id=task.id))

    return render_template("index.html", plot_url=None)

@app.route('/task_status/<task_id>')
def task_status(task_id):
    task = AsyncResult(task_id, app=celery)
    if task.state == 'SUCCESS':
        return jsonify({'status': 'SUCCESS', 'result': url_for('static', filename='cluster_plot.html')})
    elif task.state == 'PENDING':
        return jsonify({'status': 'PENDING'})
    else:
        return jsonify({'status': 'FAILURE'})

@app.route('/show_plot/<task_id>', methods=["GET", "POST"])
def show_plot(task_id):
    return render_template('show_plot.html', task_id=task_id)


@app.route('/download_zip/<task_id>', methods=["GET"])
def download_zip(task_id):
    zip_path = shutil.make_archive(
        base_name=os.path.join(app.config['SORTED_FOLDER']),
        format='zip',
        root_dir=app.config['SORTED_FOLDER']
    )
    if os.path.exists(zip_path):
        shutil.rmtree(app.config['SORTED_FOLDER'])
        return send_file(zip_path, as_attachment=True)
    else:
        flash('The zip file does not exist.')
        return redirect(url_for('show_plot', task_id=task_id))
    
@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegistrationForm()
    if form.validate_on_submit():
        username = form.username.data
        email = form.email.data
        password = form.password.data
        hash_password = bcrypt.generate_password_hash(password).decode('utf-8')
        print(f"Username: {username}, Email: {email}, Password: {password}")
        if User.query.filter_by(username=username).first() is None and User.query.filter_by(email=email).first() is None:
            user_datastore.create_user(
                email=email,
                password=hash_password,
                username=username,
            )
            db.session.commit()
            flash('Registration successful. You can now log in.')
            return redirect(url_for('index'))
        else:
            flash('Username or Email already exists.')
    return render_template('register.html', form=form)

if __name__ == '__main__':
    app.run(debug=True)