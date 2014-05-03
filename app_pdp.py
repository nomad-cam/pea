#!/usr/bin/env python
#

__author__  = 'Cameron Rodda'
__date__    = 'May 2014'

import os
import cherrypy
import jinja2
import MySQLdb
import MySQLdb.cursors
import ldap
import json

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR,'templates/')
STYLES_DIR = os.path.join(BASE_DIR,'styles/')

jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(TEMPLATE_DIR), autoescape=True)

db = MySQLdb.connect(host='localhost',user='root',passwd='password',db='peedy-pee',cursorclass=MySQLdb.cursors.DictCursor)

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

    def returnCookies(self):
        cookie = cherrypy.request.cookie
        try:
            user = cookie['peedy-pee'].value
            fname = cookie['name'].value
            position = cookie['position'].value
            return {'user': user, 'fname': fname,'title': position}
        except:
            return False

    @cherrypy.expose
    def index(self):
        if self.loggedin():
            cookies = self.returnCookies()
            t = jinja_env.get_template('index.html')
            return t.render(user=cookies['fname'])
        else:
            raise cherrypy.HTTPRedirect("/login")
            #t = jinja_env.get_template('login.html')
            #return t.render()
    
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


        if (("username" in kws) and ("password" in kws)):
            user = kws['username']
        #if "password" in kws:
            passw = kws['password']
            
        ldap_server = "10.7.0.243"    # ldap://
        acct_sx = "@synchrotron.org.au"
        base_dn = 'dc=synchrotron,dc=org,dc=au'
                
        connect = ldap.open(ldap_server)
        
        try:
            connect.simple_bind_s(user+acct_sx,passw)
            
            result = connect.search_s(base_dn,ldap.SCOPE_SUBTREE, 
                        '(&(objectclass=User) (sAMAccountName='+user+'))', 
                        ['title','displayName','givenName'])
            
            position = result[0][1]['title'][0]
            name = result[0][1]['givenName'][0]
            
            cookie =  cherrypy.response.cookie
            cookie['peedy-pee'] = user
            cookie['peedy-pee']['path'] = '/'
            cookie['peedy-pee']['max-age'] = 7200
            
            cookie['position'] = position
            cookie['position']['path'] = '/'
            cookie['position']['max-age'] = 7200
            
            cookie['name'] = name
            cookie['name']['path'] = '/'
            cookie['name']['max-age'] = 7200
            
            #t = jinja_env.get_template('index.html')
            raise cherrypy.HTTPRedirect('/')
            #return t.render(user=user)

        except ldap.LDAPError:
            connect.unbind_s()
            #t = jinja_env.get_template('login.html')
            error = 'Incorrect Login Details. Please try again...'
            #return t.render(err_msg = error)
            raise cherrypy.HTTPRedirect('/login')

    @cherrypy.expose
    def personalpdp(self):
        if self.loggedin():
            cookies = self.returnCookies()
            t = jinja_env.get_template('personal.html')
            return t.render(user=cookies['user'],position=cookies['title'],name=cookies['fname'])
        
    @cherrypy.expose
    def admin(self):
        if self.loggedin():
            cookies = self.returnCookies()
            t = jinja_env.get_template('admin.html')
            return t.render(name=cookies['fname'])
        else:
            raise cherrypy.HTTPRedirect('/login')

    @cherrypy.expose
    def groups(self):
        if self.loggedin():
            cur = db.cursor()
            cur.execute("SELECT * FROM `group`")
            
            return json.dumps(cur.fetchall())
    
    @cherrypy.expose
    def people(self):
        if self.loggedin():
            cur = db.cursor()
            cur.execute("SELECT * FROM `person`")
            
            return json.dumps(cur.fetchall())
            
    @cherrypy.expose
    def admin_update_person(self, **kws):
        if self.loggedin():
            #db_update = MySQLdb.connect(host='localhost',user='root',passwd='password',db='peedy-pee')
        
            p_manager = kws['person_manager']
            p_lname = kws['person_lastname']
            p_fname = kws['person_firstname']
            p_uname = kws['person_username']
            p_group = kws['person_group']
            try:
                p_ismanager = kws['person_ismanager']
            except:
                p_ismanager = 0
            
            cur_person = db.cursor()
            try:
                #cur_person.execute("INSERT INTO `peedy-pee`.`person` (user,firstName,lastName,group,manager) VALUES ('%s','%s','%s','%s','%s')" % (p_uname,p_fname,p_lname,p_group,p_manager))
                query = "INSERT INTO person (groupName,userName,firstName,lastName,manager) VALUES ('%s','%s','%s','%s','%s')" % (p_group,p_uname,p_fname,p_lname,p_manager)
                cur_person.execute(query)
                db.commit()
            except MySQLdb.Error, e:
                db.rollback()
                return "Error! %d: %s"%(e.args[0],e.args[1])
                
            return kws

#class Admin(object):
#    @cherrypy.expose
#    def index(self):
#        return "Hello Admin!"

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
#cherrypy.tree.mount(Admin(),'/admin', config=config)
cherrypy.engine.autoreload.on = True
cherrypy.engine.autoreload.frequency = 5
cherrypy.engine.autoreload.files.add('app_pdp.py') #remove for production
cherrypy.engine.start()

