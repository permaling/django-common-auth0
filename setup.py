#!/usr/bin/env python
import setuptools
import os

if __name__ == "__main__":
    setuptools.setup(
        version=os.environ.get("PACKAGE_VERSION", "1.0.0"),
        install_requires=[
            'pilkit @ git+https://github.com/jokerinteractive/pilkit.git@e2eb73e1798865a201e570fced0bac195b2a590c',
            'admin_multiupload @ git+https://github.com/python-force/django-admin-multiupload.git@master#egg=admin_multiupload-1.10',
            'djangorestframework_jwt @ git+https://github.com/serjant/django-rest-framework-jwt.git@f8751bca0d8992b8a27a4f08a821afae6baa0a55'
        ]
    )
