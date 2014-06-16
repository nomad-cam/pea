#!/usr/bin/env python
#

__author__  = 'Cameron Rodda'
__date__    = 'June 2014'

import os
import cherrypy
import jinja2

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR,'templates/')

jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(TEMPLATE_DIR), autoescape=True)


class Help(object):
    @cherrypy.expose
    def index(self,**kws):
        #refUrl = cherrypy.request.path_info
        refUrl = cherrypy.request.headers.get('Referer','/') 
    
        t = jinja_env.get_template('help.html')
        return t.render(ref=refUrl)
