import socket

from flask import Flask
from flask.ext.admin import Admin, base
from flask.ext.cache import Cache
from flask_wtf.csrf import CsrfProtect

import airflow
from airflow import models
from airflow.settings import Session

from airflow.www.blueprints import ck, routes
from airflow import jobs
from airflow import settings
from airflow import configuration

csrf = CsrfProtect()


def create_app(config=None):
    app = Flask(__name__)
    app.secret_key = configuration.get('webserver', 'SECRET_KEY')
    app.config['LOGIN_DISABLED'] = not configuration.getboolean('webserver', 'AUTHENTICATE')

    csrf.init_app(app)

    #app.config = config
    airflow.load_login()
    airflow.login.login_manager.init_app(app)

    cache = Cache(
        app=app, config={'CACHE_TYPE': 'filesystem', 'CACHE_DIR': '/tmp'})

    app.register_blueprint(ck, url_prefix='/ck')
    app.register_blueprint(routes)
    app.jinja_env.add_extension("chartkick.ext.charts")

    with app.app_context():
        from airflow.www import views

        admin = Admin(
            app, name='Airflow',
            static_url_path='/admin',
            index_view=views.HomeView(endpoint='', url='/admin', name="DAGs"),
            template_mode='bootstrap3',
        )
        av = admin.add_view
        vs = views
        av(vs.Airflow(name='DAGs', category='DAGs'))

        av(vs.QueryView(name='Ad Hoc Query', category="Data Profiling"))
        av(vs.ChartModelView(
            models.Chart, Session, name="Charts", category="Data Profiling"))
        av(vs.KnowEventView(
            models.KnownEvent,
            Session, name="Known Events", category="Data Profiling"))
        av(vs.SlaMissModelView(
            models.SlaMiss,
            Session, name="SLA Misses", category="Browse"))
        av(vs.TaskInstanceModelView(models.TaskInstance,
            Session, name="Task Instances", category="Browse"))
        av(vs.LogModelView(
            models.Log, Session, name="Logs", category="Browse"))
        av(vs.JobModelView(
            jobs.BaseJob, Session, name="Jobs", category="Browse"))
        av(vs.PoolModelView(
            models.Pool, Session, name="Pools", category="Admin"))
        av(vs.ConfigurationView(
            name='Configuration', category="Admin"))
        av(vs.UserModelView(
            models.User, Session, name="Users", category="Admin"))
        av(vs.ConnectionModelView(
            models.Connection, Session, name="Connections", category="Admin"))
        av(vs.VariableView(
            models.Variable, Session, name="Variables", category="Admin"))

        admin.add_link(base.MenuLink(
            category='Docs', name='Documentation',
            url='http://pythonhosted.org/airflow/'))
        admin.add_link(
            base.MenuLink(category='Docs',
                name='Github',url='https://github.com/airbnb/airflow'))

        av(vs.DagRunModelView(
            models.DagRun, Session, name="DAG Runs", category="Browse"))
        av(vs.DagModelView(models.DagModel, Session, name=None))
        # Hack to not add this view to the menu
        admin._menu = admin._menu[:-1]

        def integrate_plugins():
            """Integrate plugins to the context"""
            from airflow.plugins_manager import (
                admin_views, flask_blueprints, menu_links)
            for v in admin_views:
                admin.add_view(v)
            for bp in flask_blueprints:
                app.register_blueprint(bp)
            for ml in menu_links:
                admin.add_link(ml)

        integrate_plugins()

        @app.context_processor
        def jinja_globals():
            return {
                'hostname': socket.gethostname(),
            }

        @app.teardown_appcontext
        def shutdown_session(exception=None):
            settings.Session.remove()

        return app

app = None
def cached_app(config=None):
    global app
    if not app:
        app = create_app(config)
    return app
