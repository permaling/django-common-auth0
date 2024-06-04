from __future__ import unicode_literals

__author__ = 'David Baum'

import io, logging, os, requests, uuid

from contextlib import closing
from typing import Any

from django.core.exceptions import ValidationError
from django.core.files.temp import NamedTemporaryFile
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.core.validators import URLValidator

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)


class LJImageUtils:
    CHUNK_SIZE = 1024

    @staticmethod
    def get_valid_image_bytes(photo: Any, rotate_angle: int = 0) -> bytes:
        if rotate_angle < -360 or rotate_angle > 360:
            rotate_angle = 0
        if rotate_angle < 0:
            rotate_angle = 360 + rotate_angle

        if isinstance(photo, bytes):
            try:
                image = Image.open(io.BytesIO(photo))
                if rotate_angle > 0:
                    image_format = image.format or 'JPEG'
                    image = image.rotate(rotate_angle, resample=0, expand=0)
                    return LJImageUtils.image_to_byte_array(image, image_format=image_format)
                return photo
            except OSError:
                return None
        elif not photo or \
                not hasattr(photo, 'read') or \
                not callable(getattr(photo, 'read')):
            return None

        image_bytes = photo.read()
        try:
            image = Image.open(io.BytesIO(image_bytes))
            if rotate_angle > 0:
                image_format = image.format or 'JPEG'
                image = image.rotate(rotate_angle, resample=0, expand=0)
                return LJImageUtils.image_to_byte_array(image, image_format=image_format)
        except OSError:
            return None
        return image_bytes

    @staticmethod
    def validate_bytes(image_bytes):
        try:
            Image.open(image_bytes)
        except OSError:
            return None
        return image_bytes

    @staticmethod
    def get_image_size(image_bytes) -> (int, int):
        try:
            bytes_io = io.BytesIO(image_bytes)
            image = Image.open(bytes_io)
            return image.size
        except OSError:
            pass
        return 0, 0

    @staticmethod
    def is_valid_url(uri) -> bool:
        try:
            url_validate = URLValidator()
            url_validate(uri)
        except ValidationError:
            return False

        return True

    @staticmethod
    def copy_image_from_url(url) -> InMemoryUploadedFile:
        if LJImageUtils.is_valid_url(url):
            data_file = NamedTemporaryFile()

            with closing(requests.get(url, stream=True)) as r:
                for chunk in r.iter_content(chunk_size=LJImageUtils.CHUNK_SIZE):
                    if chunk:
                        data_file.write(chunk)
            data_file.seek(os.SEEK_SET, os.SEEK_END)
            size = os.path.getsize(data_file.name)
            data_file.seek(os.SEEK_SET)

            filename = '{}.jpg'.format(uuid.uuid4())

            data_file = InMemoryUploadedFile(
                data_file, 'data_file', filename, 'image/jpeg',
                size, charset=None)

            return data_file

        return None

    @staticmethod
    def image_bytes_to_file(image_bytes):
        if image_bytes:
            bytes_io = io.BytesIO(image_bytes)
            filename = '{}.jpg'.format(uuid.uuid4())
            return InMemoryUploadedFile(
                bytes_io, None, filename, 'image/jpeg',
                bytes_io.getbuffer().nbytes, None
            )
        return None

    @staticmethod
    def image_bytes_to_box_file(image_bytes):
        if image_bytes:
            bytes_io = io.BytesIO(image_bytes)
            image = Image.open(bytes_io)
            image_format = image.format
            image_width, image_height = image.size
            if image_width < image_height:
                image_height = image_width
            elif image_height < image_width:
                image_width = image_height
            image = ImageOps.fit(image, (image_width, image_height), centering=(0.5, 0.5))
            buffer = io.BytesIO()

            image.save(fp=buffer, format=image_format)
            buffer.seek(0, os.SEEK_END)

            filename = f'{uuid.uuid4()}.{image_format.lower()}'
            return InMemoryUploadedFile(
                buffer, None, filename, f'image/{image_format.lower()}',
                buffer.tell(), None
            )
        return None

    @staticmethod
    def image_to_byte_array(image: Image, image_format=None) -> bytes:
        image_bytes_array = io.BytesIO()
        image.save(image_bytes_array, format=image_format or image.format or 'JPEG')
        image_bytes = image_bytes_array.getvalue()
        return image_bytes
