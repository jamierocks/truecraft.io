from sqlalchemy import Column, Integer, String, Unicode, Boolean, DateTime
from sqlalchemy import ForeignKey, Table, UnicodeText, Text, text
from sqlalchemy.orm import relationship, backref
from .database import Base

from datetime import datetime
import bcrypt

class User(Base):
    __tablename__ = 'user'
    id = Column(Integer, primary_key = True)
    username = Column(String(128), nullable = False, index = True)
    email = Column(String(256), nullable = False, index = True)
    admin = Column(Boolean())
    password = Column(String)
    created = Column(DateTime)
    confirmation = Column(String(128))
    passwordReset = Column(String(128))
    passwordResetExpiry = Column(DateTime)
    sessionId = Column(String(128))
    sessionExpiry = Column(DateTime)

    def set_password(self, password):
        self.password = bcrypt.hashpw(password, bcrypt.gensalt())

    def __init__(self, username, email, password):
        self.email = email
        self.username = username
        self.password = bcrypt.hashpw(password, bcrypt.gensalt())
        self.admin = False
        self.created = datetime.now()

    def __repr__(self):
        return '<User %r>' % self.username

    # Flask.Login stuff
    # We don't use most of these features
    def is_authenticated(self):
        return True
    def is_active(self):
        return True
    def is_anonymous(self):
        return False
    def get_id(self):
        return self.username

class BlogPost(Base):
    __tablename__ = 'blog'
    id = Column(Integer, primary_key = True)
    title = Column(Unicode(1024))
    image = Column(Unicode(1024))
    text = Column(Unicode(65535))
    created = Column(DateTime)
    author_id = Column(Integer, ForeignKey('user.id'))
    author = relationship('User', backref=backref('blog', order_by=id))

    def __init__(self):
        self.created = datetime.now()

    def __repr__(self):
        return '<Blog Post %r>' % self.id
