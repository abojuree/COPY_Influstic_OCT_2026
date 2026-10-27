# -*- encoding: utf-8 -*-
"""
Copyright (c) 2019 - present AppSeed.us
"""

import os
import random
import string
from icecream import ic
from dotenv import load_dotenv

# load_dotenv()

class Config(object):

    # Determine the environment and load the appropriate .env file
    basedir = os.path.abspath(os.path.dirname(__file__))
    if os.getenv("FLASK_ENV") == "production":
        dotenv_path = os.path.join(str.join(os.sep,basedir.split(os.sep)[:-1]) , ".env.prod")
    else:
        dotenv_path = os.path.join(str.join(os.sep,basedir.split(os.sep)[:-1]) , ".env.dev")
    load_dotenv(dotenv_path)

    # Assets Management
    ASSETS_ROOT = os.getenv('ASSETS_ROOT', '/static/assets')  
    BASE_URL = os.getenv('BASE_URL', 'http://127.0.0.1:4000/')

    # Set up the App SECRET_KEY
    SECRET_KEY  = os.getenv('SECRET_KEY', None)
    if not SECRET_KEY:
        SECRET_KEY = ''.join(random.choice( string.ascii_lowercase  ) for i in range( 32 ))

    # API Keys Configuration
    RAPIDAPI_KEY = os.getenv('RAPIDAPI_KEY', 'YOUR_RAPIDAPI_KEY_HERE')

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DB_ENGINE   = os.getenv('DB_ENGINE'   , None)
    DB_USERNAME = os.getenv('DB_USERNAME' , None)
    DB_PASS     = os.getenv('DB_PASS'     , None)
    DB_HOST     = os.getenv('DB_HOST'     , None)
    DB_PORT     = os.getenv('DB_PORT'     , '5433')
    DB_NAME     = os.getenv('DB_NAME'     , None)

    USE_SQLITE  = True 
    
    # try to set up a Relational DBMS
    if DB_ENGINE and DB_NAME and DB_USERNAME:

        try:
            
            # Relational DBMS: PSQL, MySql
            SQLALCHEMY_DATABASE_URI = '{}://{}:{}@{}:{}/{}'.format(
                DB_ENGINE,
                DB_USERNAME,
                DB_PASS,
                DB_HOST,
                DB_PORT,
                DB_NAME
            ) 

            USE_SQLITE  = False

        except Exception as e:

            ic('DBMS Exception: ', str(e) )
            ic('Fallback to SQLite ')    

    if USE_SQLITE:

        # This will create a file in <app> FOLDER
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'db.sqlite3')
        # SQLALCHEMY_DATABASE_URI ='postgresql://postgres:mazisvip@localhost/SocialScanner'

    
    ic(os.getenv("FLASK_ENV"), DB_ENGINE, DB_USERNAME, DB_PASS, DB_HOST, DB_PORT, DB_NAME, USE_SQLITE)


class ProductionConfig(Config):
    DEBUG = False
    # Security
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_DURATION = 3600


class DebugConfig(Config):
    DEBUG = True,
    TEMPLATES_AUTO_RELOAD=True


# Load all possible configurations
config_dict = {
    'Production': ProductionConfig,
    'Debug'     : DebugConfig
}
