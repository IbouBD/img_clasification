from flask import Flask, session
from flask_session import Session
import os
import torch
import torchvision.models as models
import torchvision.transforms as transforms
from PIL import Image
import numpy as np
import pandas as pd
from sklearn.manifold import TSNE
from sklearn.cluster import KMeans
import plotly.express as px
import shutil
from celery import Celery
import redis
import aspose.zip as az



app = Flask(__name__)
app.secret_key = 'CHANGEME'

# Configuration de l'upload de fichiers
UPLOAD_FOLDER = 'uploads'
SORTED_FOLDER = 'data'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SORTED_FOLDER'] = SORTED_FOLDER

# Configuration de Flask-Session
app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_REDIS'] = redis.StrictRedis(host='localhost', port=6379)
Session(app)

# Configuration Celery
def make_celery(app):
    celery = Celery(app.import_name, backend='redis://localhost:6379/0', broker='redis://localhost:6379/0')
    celery.conf.update(app.config)
    return celery


celery = make_celery(app)

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

for f in os.listdir(UPLOAD_FOLDER):
    os.remove(os.path.join(UPLOAD_FOLDER, f))

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

@celery.task(bind=True)
def process_images(self, image_folder, nb_cluster):
    if not os.path.exists(image_folder):
        os.makedirs(image_folder)

    if not os.path.exists(SORTED_FOLDER):
        os.makedirs(SORTED_FOLDER)

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
    tsne = TSNE(n_components=3, random_state=0, perplexity=30)
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
    output_path = os.path.join('static', 'cluster_plot.html')
    fig.write_html(output_path)


    return output_path, df.to_dict()


@celery.task(bind=True)
def organize_files(self, df_dict, image_folder):
    df = pd.DataFrame.from_dict(df_dict)

    if not os.path.exists(SORTED_FOLDER):
        os.makedirs(SORTED_FOLDER)

    clusters = df['cluster'].unique()
    clustered_files = {cluster: df[df['cluster'] == cluster]['image'].tolist() for cluster in clusters}

    for cluster in clusters:
        current_cluster = clustered_files[cluster]
        folder_path = os.path.join(SORTED_FOLDER, f'group_{cluster + 1}')

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        for img in current_cluster:
            src_path = os.path.join(image_folder, img)
            dest_path = os.path.join(folder_path, img)
            shutil.move(src_path, dest_path)