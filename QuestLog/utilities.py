
import os
import uuid
from PIL import Image
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
    new_filename = os.path.join("avatars",uuid.uuid4().hex,ext)
    return new_filename
    

def secure_upload_path_proofs(instance, filename):
    ext = os.path.splitext(filename)[1].lower()
    new_filename = os.path.join("proofs",uuid.uuid4().hex,ext)
    return new_filename

def scan_for_malicious_code(file):
    dangerous_patterns = [
        '<script>', '</script>', '<iframe>', '<img src=x onerror=',
        '<object>', 'javascript:', '<svg onload=', '<embed>', '<body onload=',
        '<?php', '<%', '%>', '<asp:', 'eval(', 'exec(', 'system(', 'os.system',
        'subprocess.Popen', 'subprocess.call', '../', '/etc/passwd', 'C:\\Windows\\System32',
        'require(', 'include(', 'import os', 'open(', 'SELECT ', 'DROP TABLE', '--',
        ';', '&&', '|', '`', '$(', 'curl', 'wget', 'nc ', 'pickle.load(', 'yaml.load(',
        'chmod 777', 'base64_decode(', 'str_rot13('
    ]
    content = file.read().decode(errors='ignore')
    for pattern in dangerous_patterns:
        if pattern in content:
            raise ValidationError("Malicious content detected")
    file.seek(0)  # reset file pointer after reading

import magic
from django.core.exceptions import ValidationError

# Allowed MIME types
ALLOWED_MIME_TYPES = [
    'image/jpeg',
    'image/png',
    'image/gif'
]

def validate_content_type(file):
    file.seek(0)  # make sure pointer is at start
    mime = magic.from_buffer(file.read(2048), mime=True)
    file.seek(0)  # reset pointer after reading
    if mime not in ALLOWED_MIME_TYPES:
        raise ValidationError(f"Unsupported file type: {mime}")



def validate_image_file(file):
    try:
        img = Image.open(file)
        img.verify()  # raises exception if file is not a valid image
    except Exception:
        raise ValidationError("Invalid image file")