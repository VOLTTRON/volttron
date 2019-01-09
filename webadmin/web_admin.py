from os import path as p
from flask import Flask, render_template
from volttron.platform.certs import Certs, Subject

from gevent.pywsgi import WSGIServer

# Web root is going to be relative to the volttron central agents
# current agent's installed path
DEFAULT_STATIC = p.abspath(p.join(p.dirname(__file__), 'static/'))

app = Flask(__name__) #, root_path='/', static_folder=DEFAULT_STATIC)  # pylint: disable=invalid-name
app.debug = True


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/certs')
def list_certs():
    certs = Certs()
    subjects = certs.get_all_cert_subjects()
    return render_template('list_certs.html', certs=subjects)


def main():
    "Start gevent WSGI server"
    app.run()
    # use gevent WSGI server instead of the Flask
    #http = WSGIServer(('', 5000), app.wsgi_app)
    # TODO gracefully handle shutdown
    #http.serve_forever()


if __name__ == '__main__':
    main()