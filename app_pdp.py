#!/usr/bin/env python
#

__author__  = 'Cameron Rodda'
__date__    = 'May 2014'

import os
import cherrypy
import jinja2
import MySQLdb
import ldap

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR,'templates/')
STYLES_DIR = os.path.join(BASE_DIR,'styles/')

jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(TEMPLATE_DIR), autoescape=True)

class PeedyPee(object):
    
    def loggedin(self):
        cookie = cherrypy.request.cookie
        try:
            if cookie['peedy-pee'].value:
                return cookie['peedy-pee'].value
            else:
                return False
        except:
            return False

    @cherrypy.expose
    def index(self):
        u = self.loggedin()
        if u:
            t = jinja_env.get_template('index.html')
            return t.render(user=u)
        else:
            #raise cherrypy.HTTPRedirect("/login")
            t = jinja_env.get_template('login.html')
            return t.render()
    
    @cherrypy.expose
    def logout(self):
        cookie = cherrypy.response.cookie
        cookie['peedy-pee'] = False
        cookie['peedy-pee']['expires'] = 0
        
        raise cherrypy.HTTPRedirect("/")
    
    @cherrypy.expose
    def login(self):
        t = jinja_env.get_template('login.html')
        return t.render()
    
    @cherrypy.expose
    def dologin(self, **kws):


        if "username" in kws:
            user = kws['username']
        if "password" in kws:
            passw = kws['password']
            
        ldap_server = "10.7.0.243"    # ldap://
        acct_sx = "@synchrotron.org.au"
        
        connect = ldap.open(ldap_server)
        
        try:
            connect.simple_bind_s(user+acct_sx,passw)
            
            cookie =  cherrypy.response.cookie
            cookie['peedy-pee'] = user
            cookie['peedy-pee']['path'] = '/'
            cookie['peedy-pee']['max-age'] = 7200
            cookie['peedy-pee']['version'] = 1
            
            #t = jinja_env.get_template('index.html')
            raise cherrypy.HTTPRedirect('/')
            #return t.render(user=user)

        except ldap.LDAPError:
            connect.unbdin_s()
            #t = jinja_env.get_template('login.html')
            error = 'Incorrect Login Details. Please try again...'
            #return t.render(err_msg = error)
            raise cherrypy.HTTPRedirect('/login')

    @cherrypy.expose
    def personal_pdp(self):
        u = self.loggedin()
        if u:
            t = jinja_env.get_template('personal.html')
            return t.render(user=u)
        
        

cherrypy.config.update({
    'server.socket_host': 'localhost',
    'server.socket_port': 8080
})

config = {
    '/':
        {'tools.staticdir.debug': True,
         'log.screen': True
        },
    '/templates':
        {'tools.staticdir.on': True,
         'tools.staticdir.dir': TEMPLATE_DIR
        },
    '/styles':
        {'tools.staticdir.on': True,
         'tools.staticdir.dir': STYLES_DIR
        }
        
}

cherrypy.tree.mount(PeedyPee(),'/', config=config)
cherrypy.engine.autoreload.on = True
cherrypy.engine.autoreload.files.add('app_pdp.py') #remove for production
cherrypy.engine.start()
