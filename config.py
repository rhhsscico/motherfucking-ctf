import os

class Config(object):
    DEBUG = False
    SECRET_KEY = '0000000000000000000000000'
    SECRET_PASSWORD_SALT = '0000000000000'

class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///db.sqlite'