import pymysql
pymysql.install_as_MySQLdb()

import os
import django

def setup_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "email_project.settings")
    django.setup()