from __future__ import unicode_literals

__author__ = 'David Baum'

import os

from django.core.files.base import ContentFile
from django.test import SimpleTestCase

from ..hashing.image import LJImageHashing


class LJImageHashingTest(SimpleTestCase):
    IMAGES_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data/images')
    EXPECTED_ENCODING_MAP = {
        'IMG_1231_1.JPG': 'ca4d8bca6bc36595',
        'IMG_1233.JPG': 'bf021f177a9760c6',
        'IMG_1232.JPG': 'bf785f137e0660c4',
        'IMG_1231.JPG': 'ca4d8bca6bc36595',
        'Image1.jpg': '897fa22ec4991e97',
        'Image2.jpg': '897fa22ec4991e97'
    }
    EXPECTED_DUPLICATES = {
        'IMG_1231_1.JPG': ['IMG_1231.JPG'],
        'IMG_1233.JPG': [],
        'IMG_1232.JPG': [],
        'IMG_1231.JPG': ['IMG_1231_1.JPG'],
        'Image1.jpg': ['Image2.jpg'],
        'Image2.jpg': ['Image1.jpg']
    }
    EXPECTED_UNIQUE_FILES = ['IMG_1231.JPG', 'Image2.jpg']

    def test_find_duplicate_images(self):
        images = []
        file_names = os.listdir(self.IMAGES_DATA_DIR)
        for file_name in file_names:
            file_path = os.path.join(self.IMAGES_DATA_DIR, file_name)

            with open(file_path, "rb") as fh:
                image_bytes = fh.read()
                with ContentFile(image_bytes, name=file_name) as file_content:
                    images.append(file_content)

        hasher = LJImageHashing()
        encodings_map = hasher.encode_images(images)
        for key, value in encodings_map.items():
            self.assertIn(key, file_names)
            self.assertIsNotNone(value)

        self.assertEquals(self.EXPECTED_ENCODING_MAP, encodings_map)

        hasher_duplicates = hasher.find_duplicates(encoding_map=encodings_map)
        self.assertEquals(hasher_duplicates, self.EXPECTED_DUPLICATES)

        hasher_unique_files = hasher.find_duplicates_to_remove(encoding_map=encodings_map)
        self.assertEquals(hasher_unique_files, self.EXPECTED_UNIQUE_FILES)
