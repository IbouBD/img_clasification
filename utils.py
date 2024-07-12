import os
from tasks import app

# Configuration de l'upload de fichiers
UPLOAD_FOLDER = 'uploads'
SORTED_FOLDER = 'data'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['SORTED_FOLDER'] = SORTED_FOLDER