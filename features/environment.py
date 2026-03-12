import shutil
import tempfile

from django.conf import settings
from django.core.files.storage import default_storage
from django.utils.functional import empty


def before_all(context):
    context.temp_media_root = tempfile.mkdtemp(prefix="questlog-behave-media-")
    context.original_media_root = settings.MEDIA_ROOT
    settings.MEDIA_ROOT = context.temp_media_root
    default_storage._wrapped = empty


def after_all(context):
    settings.MEDIA_ROOT = context.original_media_root
    default_storage._wrapped = empty
    shutil.rmtree(context.temp_media_root, ignore_errors=True)
