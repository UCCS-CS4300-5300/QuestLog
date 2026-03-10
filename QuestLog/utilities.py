
import os
import uuid

from django.forms import ValidationError

MEDIA_TYPES=['proofs','avatars']

def validate_upload(file):
    max_size = 2 * 1024 * 1024  # 2 MB
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.gif']

    ext = os.path.splitext(file.name)[1].lower()
    if ext not in allowed_extensions:
        raise ValidationError(f'Unsupported file extension {ext}. Allowed: {allowed_extensions}')

    if file.size > max_size:
        raise ValidationError(f'File too large. Max size: {max_size / (1024*1024)} MB')
    
def secure_upload_wrapper(media_type):
    def secure_upload_path(instance,filename):
        ext = os.path.splitext(filename)[1].lower() 
        new_filename = f"{uuid.uuid4().hex}{ext}"

        if (media_type in MEDIA_TYPES):
            return os.path.join(media_type,new_filename, ext)
        else:
            raise ValidationError("Incorrect media type")
        

    # ext = os.path.splitext(filename)[1].lower() 
    # new_filename = f"{uuid.uuid4().hex}{ext}"

    # return os.path.join(new_filename, new_filename)