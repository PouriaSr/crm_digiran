import uuid
from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class HiringDocumentStorage(FileSystemStorage):
    def __init__(self):
        super().__init__(location=getattr(settings, 'HIRING_PRIVATE_ROOT', Path(settings.BASE_DIR) / 'private_uploads' / 'hiring'), file_permissions_mode=0o600, directory_permissions_mode=0o700)

    def url(self, name):
        raise ValueError('Hiring documents are served through their authorized download view.')


def resume_path(instance, filename):
    return f'resumes/{uuid.uuid4().hex}{Path(filename).suffix.lower()}'
