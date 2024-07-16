import os
import shutil
import torch
import torchvision.models as models
import torchvision.transforms as transforms
import umap.umap_ as umap


UPLOAD_FOLDER = 'uploads'
SORTED_FOLDER = 'data'
ARCHIVE_NAME = 'sorted_folder'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp'}

if os.path.exists(UPLOAD_FOLDER):
    shutil.rmtree(UPLOAD_FOLDER)

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

if os.path.exists(SORTED_FOLDER):
    shutil.rmtree(SORTED_FOLDER)

if not os.path.exists(SORTED_FOLDER):
    os.makedirs(SORTED_FOLDER)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS