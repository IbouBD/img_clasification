from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, send_file
from werkzeug.utils import secure_filename
import os
import pandas as pd
from tasks import process_images, organize_files, celery
from celery.result import AsyncResult
import shutil
import aspose.zip as az

# Configuration Flask
app = Flask(__name__)
app.secret_key = 'CHANGEME'
UPLOAD_FOLDER = 'uploads'
SORTED_FOLDER = 'data'
ARCHIVE_NAME = 'sorted_folder'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SORTED_FOLDER'] = SORTED_FOLDER
app.config['ARCHIVE_NAME'] = ARCHIVE_NAME

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if os.path.exists(SORTED_FOLDER):
    shutil.rmtree(SORTED_FOLDER)

if not os.path.exists(SORTED_FOLDER):
    os.makedirs(SORTED_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'png', 'jpg', 'jpeg', 'bmp'}

@app.route("/", methods=["GET", "POST"])
async def index():
    if request.method == "POST":
        if 'files' not in request.files:
            flash('No file part')
            return redirect(request.url)

        files = request.files.getlist('files')
        nb_cluster = int(request.form.get('nb_cluster'))
        print("nb_cluster", nb_cluster)
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        task = process_images.apply_async(args=[app.config['UPLOAD_FOLDER'], nb_cluster])
        session['task_id'] = task.id
        return redirect(url_for('show_plot', task_id=task.id))

    return render_template("index.html")

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
async def show_plot(task_id):
    
    if request.method == "GET":
        
        df = None
        df_dict = session.get('df')

        if df_dict:
            df = pd.DataFrame.from_dict(df_dict)
        task = organize_files.apply_async(args=[df, app.config['UPLOAD_FOLDER']])

            # Créer une archive à partir du dossier trié
        #shutil.make_archive(ARCHIVE_NAME,"zip", SORTED_FOLDER)

        #shutil.rmtree(SORTED_FOLDER)
        print("file removed succesfully")
        
    return render_template('show_plot.html', task_id=task_id)


@app.route('/download_zip/<task_id>', methods=["GET"])
def download_zip(task_id):
    zip_path = shutil.make_archive(
        base_name=os.path.join(app.config['SORTED_FOLDER']),
        format='zip',
        root_dir=app.config['SORTED_FOLDER']
    )
    if os.path.exists(zip_path):
        return send_file(zip_path, as_attachment=True)
    else:
        flash('The zip file does not exist.')
        return redirect(url_for('show_plot', task_id=task_id))


if __name__ == '__main__':
    app.run(debug=True)