from flask import Blueprint, render_template, abort, request, redirect, session, url_for, send_file
from flask.ext.login import current_user, login_user, logout_user
from sqlalchemy import desc, or_, and_
from datetime import datetime, timedelta
from truecraft.objects import *
from truecraft.common import *
from truecraft.config import _cfg
from truecraft.email import send_confirmation, send_reset

import binascii
import os
import zipfile
import urllib
import re
import json
import locale
import shlex
import math

encoding = locale.getdefaultlocale()[1]
html = Blueprint('html', __name__, template_folder='../../templates')

@html.route("/")
def index():
    posts = BlogPost.query.order_by(desc(BlogPost.created)).limit(5)[:5]
    total = BlogPost.query.count()
    return render_template("index.html", posts=posts, total_pages=total // 5)

@html.route("/rss.xml")
def rss():
    posts = BlogPost.query.order_by(desc(BlogPost.created)).limit(10)[:10]
    return render_template("rss.xml", posts=posts)

@html.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template("register.html")
    else:
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        errors = dict()
        if not email:
            errors['email'] = 'Email is required.'
        else:
            if not re.match(r"^[^@]+@[^@]+\.[^@]+$", email):
                errors['email'] = 'Please use a valid email address.'
            if User.query.filter(User.username.ilike(username)).first():
                errors['username'] = 'This username is already in use.'
        if not username:
            errors['username'] = 'Username is required.'
        else:
            if not re.match(r"^[A-Za-z0-9_]+$", username):
                errors['username'] = 'Letters, numbers, underscores only.'
            if len(username) < 3 or len(username) > 24:
                errors['username'] = 'Must be between 3 and 24 characters.'
            if User.query.filter(User.username.ilike(username)).first():
                errors['username'] = 'This username is already in use.'
        if not password:
            errors['password'] = 'Password is required.'
        else:
            if len(password) < 5 or len(password) > 256:
                errors['password'] = 'Must be between 5 and 256 characters.'
        if errors != dict():
            return render_template("register.html", username=username, email=email, errors=errors)
        # All good, create an account for them
        user = User(username, email, password)
        user.confirmation = binascii.b2a_hex(os.urandom(20)).decode("utf-8")
        db.add(user)
        db.commit()
        send_confirmation(user)
        return redirect("/pending")

@html.route("/confirm/<confirmation>")
def confirm(confirmation):
    user = User.query.filter(User.confirmation == confirmation).first()
    if not user:
        return render_template("confirm.html", **{ 'success': False, 'user': user })
    else:
        user.confirmation = None
        login_user(user)
        db.commit()
        return render_template("confirm.html", **{ 'success': True, 'user': user })

@html.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if current_user:
            return redirect("/")
        reset = request.args.get('reset') == '1'
        return render_template("login.html", **{ 'return_to': request.args.get('return_to'), 'reset': reset })
    else:
        username = request.form['username']
        password = request.form['password']
        remember = request.form.get('remember-me')
        if remember == "on":
            remember = True
        else:
            remember = False
        user = User.query.filter(User.username.ilike(username)).first()
        if not user:
            return render_template("login.html", **{ "username": username, "errors": 'Your username or password is incorrect.' })
        if user.confirmation != '' and user.confirmation != None:
            return redirect("/pending")
        if not bcrypt.checkpw(password, user.password):
            return render_template("login.html", **{ "username": username, "errors": 'Your username or password is incorrect.' })
        login_user(user, remember=remember)
        if 'return_to' in request.form and request.form['return_to']:
            return redirect(urllib.parse.unquote(request.form.get('return_to')))
        return redirect("/")

@html.route("/logout")
@loginrequired
def logout():
    logout_user()
    return redirect("/")

@html.route("/forgot-password", methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'GET':
        return render_template("forgot.html")
    else:
        email = request.form.get('email')
        if not email:
            return render_template("forgot.html", bad_email=True)
        user = User.query.filter(User.email == email).first()
        if not user:
            return render_template("forgot.html", bad_email=True, email=email)
        user.passwordReset = binascii.b2a_hex(os.urandom(20)).decode("utf-8")
        user.passwordResetExpiry = datetime.now() + timedelta(days=1)
        db.commit()
        send_reset(user)
        return render_template("forgot.html", success=True)

@html.route("/reset", methods=['GET', 'POST'])
@html.route("/reset/<username>/<confirmation>", methods=['GET', 'POST'])
def reset_password(username, confirmation):
    user = User.query.filter(User.username == username).first()
    if not user:
        redirect("/")
    if request.method == 'GET':
        if user.passwordResetExpiry == None or user.passwordResetExpiry < datetime.now():
            return render_template("reset.html", expired=True)
        if user.passwordReset != confirmation:
            redirect("/")
        return render_template("reset.html", username=username, confirmation=confirmation)
    else:
        if user.passwordResetExpiry == None or user.passwordResetExpiry < datetime.now():
            abort(401)
        if user.passwordReset != confirmation:
            abort(401)
        password = request.form.get('password')
        password2 = request.form.get('password2')
        if not password or not password2:
            return render_template("reset.html", username=username, confirmation=confirmation, errors="Please fill out both fields.")
        if password != password2:
            return render_template("reset.html", username=username, confirmation=confirmation, errors="You seem to have mistyped one of these, please try again.")
        user.set_password(password)
        user.passwordReset = None
        user.passwordResetExpiry = None
        db.commit()
        return redirect("/login?reset=1")

@html.route("/pending")
def pending():
    return render_template("pending.html")

@html.route("/download")
def download():
    return render_template("download.html")

@html.route("/roadmap")
def roadmap():
    return render_template("roadmap.html")

@html.route("/blog/compose", methods=["GET", "POST"])
@adminrequired
def compose_blog():
    if request.method == 'GET':
        return render_template("compose.html")
    else:
        title = request.form.get('post-title')
        image_url = request.form.get('post-image')
        content = request.form.get('post-content')
        if not title or not image_url or not content:
            return render_template("compose.html", errors=True)
        post = BlogPost()
        post.author = current_user
        post.title = title
        post.image = image_url
        post.text = content
        db.add(post)
        db.commit()
        return redirect(url_for("html.view_blog", id=post.id, title=post.title))

@html.route("/blog/<int:id>/edit", methods=["GET", "POST"])
@adminrequired
def edit_blog(id):
    post = BlogPost.query.filter(BlogPost.id == id).first()
    if not post:
        abort(404)
    if request.method == "GET":
        return render_template("compose.html", post=post)
    else:
        title = request.form.get('post-title')
        image_url = request.form.get('post-image')
        content = request.form.get('post-content')
        if not title or not image_url or not content:
            return render_template("compose.html", errors=True)
        post.title = title
        post.image = image_url
        post.text = content
        db.commit()
        return redirect(url_for("html.view_blog", id=post.id, title=post.title))

@html.route("/blog/<int:id>/<path:title>")
def view_blog(id, title):
    post = BlogPost.query.filter(BlogPost.id == id).first()
    if not post:
        abort(404)
    return render_template("blog-post.html", post=post)

@html.route("/updates")
def updates():
    page = 1
    provided = request.args.get('page')
    if provided:
        try:
            page = int(provided)
        except:
            pass
    posts = BlogPost.query.order_by(desc(BlogPost.created)).offset((page - 1) * 5).limit(5)[:5]
    total = BlogPost.query.count()
    return render_template("updates.html", posts=posts, page=page, total_pages=total // 5)

@html.route("/u/<username>")
@html.route("/user/<username>")
def view_user(username):
    user = User.query.filter(User.username.ilike(username)).first()
    if not user:
        abort(404)
    return render_template("profile.html", profile=user)
