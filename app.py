import os
import torch
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image
import numpy as np
import pandas as pd
from sklearn.manifold import TSNE
from sklearn.cluster import KMeans
from flask import Flask, jsonify, request, render_template, redirect, url_for, flash, send_from_directory
from werkzeug.utils import secure_filename
import asyncio
import plotly.express as px
import shutil
import zipfile

app = Flask(__name__)
app.secret_key = 'CHANGEME'

# Configuration de l'upload de fichiers
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# Vérifier et créer le dossier 'static'
STATIC_FOLDER = 'webapp_flask/static'
if not os.path.exists(STATIC_FOLDER):
    os.makedirs(STATIC_FOLDER)

# Charger le modèle VGG pré-entraîné
vgg = models.vgg19(pretrained=True)
feature_extractor = torch.nn.Sequential(*list(vgg.features.children()), vgg.avgpool)
feature_extractor.eval()

# Préparer la transformation pour les images
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_features(image_path):
    try:
        image = Image.open(image_path).convert('RGB')
        image = transform(image)
        with torch.no_grad():
            features = feature_extractor(image.unsqueeze(0))
        return features.flatten().numpy()
    except Exception as e:
        print(f"Erreur lors de l'extraction des caractéristiques de {image_path}: {e}")
        return None

async def process_images(image_folder, nb_cluster):
    features = []
    image_names = []

    # Parcourir les fichiers dans les sous-dossiers
    for root, dirs, files in os.walk(image_folder):
        for image_file in files:
            if allowed_file(image_file):
                image_path = os.path.join(root, image_file)
                feat = extract_features(image_path)
                if feat is not None:
                    features.append(feat)
                    image_names.append(image_file)

    assert len(features) == len(image_names), "Toutes les listes doivent avoir la même longueur"

    features_array = np.array(features)
    print(features_array.shape)

    # Appliquer t-SNE avec une perplexité de 30
    nb_file = (len(UPLOAD_FOLDER)-1)
    print("nb fichier", nb_file)
    optimal_perplexity = int(nb_file-2)
    tsne = TSNE(n_components=3, random_state=0, perplexity=optimal_perplexity)
    projections = tsne.fit_transform(features_array)

    df = pd.DataFrame({
        'x': projections[:, 0],
        'y': projections[:, 1],
        'z': projections[:, 2],
        'image': image_names,
    })

    # Appliquer KMeans
    km = KMeans(random_state=42, n_init=10, max_iter=100, n_clusters=nb_cluster)
    df['cluster'] = km.fit_predict(df[['x', 'y', 'z']])

    # Visualisation des clusters avec Plotly
    fig = px.scatter_3d(
        df,
        x='x',
        y='y',
        z='z',
        color='cluster',
        title='T-SNE with K-Mean Clustering',
        hover_data=['image'],
        color_continuous_scale='Viridis'
    )
    fig.update_traces(marker=dict(size=5))

    # Sauvegarde du graphique
    output_path = os.path.join(STATIC_FOLDER, 'cluster_plot.html')
    fig.write_html(output_path)

    return output_path

def organize_files(df, original_folder):
    sorted_folder = 'data_sorted'
    
    if not os.path.exists(sorted_folder):
        os.makedirs(sorted_folder)
    
    clusters = df['cluster'].unique()
    print(clusters)
    for cluster in clusters:
        new_folder_path = os.path.join(sorted_folder, f'group_{cluster}')
        if not os.path.exists(new_folder_path):
            os.makedirs(new_folder_path)
        
        cluster_images = df[df['cluster'] == cluster]['image'].tolist()
        for img in cluster_images:
            src_path = os.path.join(original_folder, img)
            dest_path = os.path.join(new_folder_path, img)
            shutil.move(src_path, dest_path)

    return sorted_folder

def zip_folder(folder_path, zip_name):
    zipf = zipfile.ZipFile(zip_name, 'w', zipfile.ZIP_DEFLATED)
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            zipf.write(os.path.join(root, file),
                       os.path.relpath(os.path.join(root, file),
                                       os.path.join(folder_path, '..')))
    zipf.close()

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
        
        output_path = await process_images(app.config['UPLOAD_FOLDER'], nb_cluster)
        return redirect(url_for('show_plot'))
    
    return render_template("index.html")

@app.route('/download/')
def download_file(filename):
    return send_from_directory(directory=os.getcwd(), filename=filename, as_attachment=True)


@app.route('/show_plot', methods=["GET", "POST"])
def show_plot():
    if request.method == "POST":
        df = pd.read_pickle('df.pkl')
        sorted_folder = organize_files(df, app.config['UPLOAD_FOLDER'])
        zip_name = 'sorted_files.zip'
        zip_folder(sorted_folder, zip_name)
        return redirect(url_for('download_file', filename=zip_name))
    
    return render_template('show_plot.html')


if __name__ == '__main__':
    app.run(debug=True)