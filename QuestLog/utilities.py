
import os
import uuid

from django.core.exceptions import ValidationError

MEDIA_TYPES=['proofs','avatars']

def validate_upload(file):
    max_size = 2 * 1024 * 1024  # 2 MB
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(f'Unsupported file extension {ext}. Allowed: {allowed_extensions}')

    if file.size > max_size:
        raise ValidationError(f'File too large. Max size: {max_size / (1024*1024)} MB')
 

def secure_upload_path_avatars(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    new_filename = f"{uuid.uuid4().hex}{ext}"
    return f"avatars/{new_filename}"
    

def secure_upload_path_proofs(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    new_filename = f"{uuid.uuid4().hex}{ext}"
    return f"proofs/{new_filename}"
