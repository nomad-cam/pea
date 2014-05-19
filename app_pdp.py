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
import string
from datetime import date

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR,'templates/')
STYLES_DIR = os.path.join(BASE_DIR,'styles/')
JS_DIR = os.path.join(BASE_DIR,'js/')
IMG_DIR = os.path.join(BASE_DIR,'images/')

jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(TEMPLATE_DIR), autoescape=True)

config_data = open('config.json')
values = json.load(config_data)
config_data.close()

db = MySQLdb.connect(host=values['DB']['host'],user=values['DB']['dbuser'],
                    passwd=values['DB']['password'],db=values['DB']['database'],
                    cursorclass=MySQLdb.cursors.DictCursor)

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
    def index(self,**kws):
        if self.loggedin():
            cookies = self.returnCookies()
            userName = cookies['user']
            
            err = ''
            if 'e' in kws:
                err = kws['e']
            
            query = "SELECT * FROM `person` WHERE userName='%s'" % userName
            side_dict = self.runQuery(query)[0]
            
            query = "SELECT * FROM `group` WHERE manager='%s'" % userName
            g_dict = self.runQuery(query)
            #uManager = result[0]['manager']
            #return side_dict
            
            
            t = jinja_env.get_template('index.html')
            return t.render(sideDB=side_dict,groupDB=g_dict,err=err,
                            userName=userName,title=cookies['title'],firstName=cookies['fname'])
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
            
        #ldap_server = "10.7.0.243"    # ldap://
        #acct_sx = "@synchrotron.org.au"
        #base_dn = 'dc=synchrotron,dc=org,dc=au'
        ldap_server = values['LDAP']['ldap_server']
        acct_sx = values['LDAP']['acct_sx']
        base_dn = values['LDAP']['base_dn']
                
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
            connect.unbind_s()
            
            raise cherrypy.HTTPRedirect('/')
            #return t.render(user=user)

        except ldap.LDAPError:
            connect.unbind_s()
            #t = jinja_env.get_template('login.html')
            error = 'Incorrect Login Details. Please try again...'
            #return t.render(err_msg = error)
            raise cherrypy.HTTPRedirect('/login')

    @cherrypy.expose
    def changelog(self):
        t = jinja_env.get_template('change.html')
        return t.render()


    @cherrypy.expose
    def personalpdp(self,user=None):
        if self.loggedin():
            cookies = self.returnCookies()
            
            # enable managers and admin to view other pdps
            if user:
                selectName = user
            else:
                selectName = userName
            
            query = ("SELECT * FROM `person` WHERE userName='%s'" % selectName)
            select_dict = self.runQuery(query, all=0)
            
            userName = cookies['user']
                
            query = "SELECT * FROM `person` WHERE userName='%s'" % userName
            side_dict = self.runQuery(query)[0]
            
            query = "SELECT * FROM `group` WHERE manager='%s'" % userName
            g_dict = self.runQuery(query)
            
            t = jinja_env.get_template('personal_pdp.html')
            return t.render(sideDB=side_dict,groupDB=g_dict,selectDB=select_dict,
                            user=userName,title=cookies['title'],name=cookies['fname'])
            
        else:
            raise cherrypy.HTTPRedirect('/login')

    def default_year(self):
        #pdp year starts at start of pdp year (financial year)
        #so to get in the right year cycle - need to set last year if in the new year
        
        if date.today().month < 6:
            return date.today().year - 1
        else:
            return date.today().year

    @cherrypy.expose
    def grouppdp(self,group=None,year=None,**kws):
        if self.loggedin():
            cookies = self.returnCookies()
            
            err = ''
            if 'e' in kws:
                err = kws['e']
            
            if year == None:
                year = self.default_year()
            
            userName = cookies['user']
            query = "SELECT * FROM `person` WHERE userName='%s'" % userName
            side_dict = self.runQuery(query)[0]
            
            query = "SELECT * FROM `group` WHERE manager='%s'" % userName
            g_dict = self.runQuery(query)
            
                       
            query = ("SELECT gid, groupName, manager FROM `group` WHERE urlName='%s'") % group
            groupID = self.runQuery(query, all=0)
            
            query = ("SELECT MAX(cycle) AS cycle FROM `group-pdp-data` WHERE (gid='%s' AND year='%s')"
                    % (groupID['gid'],year))
            current_cycle = self.runQuery(query, all=0)
            
            g_training = self.getTraining()
            
            if 'add_group_row' in kws:
                # First save data then add a new line
                for j in range(len(kws['zid[]'])):
                    query = ("UPDATE `group-pdp-data` "
                         "SET goalTitle='%s', owners='%s', description='%s', deadline='%s', budget='%s', training='%s' "
                         "WHERE zid='%s'" 
                         % (kws['group_goal[]'][j],kws['group_owners[]'][j],kws['group_description[]'][j],
                         kws['group_deadline[]'][j],kws['group_budget[]'][j],kws['group_training[]'][j],kws['zid[]'][j]))
                         
                    self.runQuery(query,read=0)
                    
                
                # Second add a blank line to the DB before redirecting to same page
                query = ("INSERT INTO `group-pdp-data` (gid, year, cycle)"
                         "VALUES (%s,%s,%s)" % (groupID['gid'], year, current_cycle['cycle']))
                self.runQuery(query,read=0)
                
                raise cherrypy.HTTPRedirect('/grouppdp/%s/%s?e=%s'% (group,year,err))
            
            elif 'save_group_data' in kws:
                # Save the current data
                for j in range(len(kws['zid[]'])):
                     query = ("UPDATE `group-pdp-data` "
                         "SET goalTitle='%s', owners='%s', description='%s', deadline='%s', budget='%s', training='%s' "
                         "WHERE zid='%s'" 
                         % (kws['group_goal[]'][j],kws['group_owners[]'][j],kws['group_description[]'][j],
                         kws['group_deadline[]'][j],kws['group_budget[]'][j],kws['group_training[]'][j],kws['zid[]'][j]))
                         
                     self.runQuery(query,read=0)
                
                raise cherrypy.HTTPRedirect('/grouppdp/%s/%s?e=%s'% (group,year,err))                   
            
            query = ("SELECT * FROM `group-pdp-data` WHERE (gid='%s' AND year='%s' AND cycle='%s')"
                    % (groupID['gid'], year, current_cycle['cycle']))
            gpdps = self.runQuery(query, all=1)
            
           
            t = jinja_env.get_template('group_pdp.html')
            return t.render(sideDB=side_dict,groupDB=g_dict,err=err,training=g_training,
                            user=cookies['user'],title=cookies['title'],name=cookies['fname'],year=year,cycle=current_cycle['cycle'],
                            group_url=group,groupPDPs=gpdps,groupName=groupID['groupName'],manager=groupID['manager'])
            
        else:
            raise cherrypy.HTTPRedirect('/login')

    @cherrypy.expose
    def grouppdp_signoff(self,**kws):
        if self.loggedin():
            group_url = kws['group_url']
            year = kws['s_year']
            cycle = kws['s_cycle']
            if 'manager-sign' in kws:
                signoff = 1
            else:
                err = "The signoff box was not checked"
                raise cherrypy.HTTPRedirect('/grouppdp/%s/%s?e=%s'%(group_url,year,err))
            comments = kws['comments']
            next_cycle = int(cycle) + 1
            thisday = date.today().strftime("%Y/%m/%d")
            query = ( "SELECT gid FROM `group` WHERE urlName='%s'" % group_url )
            groupID = self.runQuery(query,all=0)
            
            # "Store" the current cycle group goals and copy to new cycle
            query = ("INSERT INTO `group-pdp-data` "
                    "(gid,cycle,year,goalTitle,description,owners,deadline,budget,training) "                                          
                     "SELECT gid,'%s',year,goalTitle,description,owners,deadline,budget,training "
                     "FROM `group-pdp-data` "
                     "WHERE (gid='%s' AND cycle='%s')" % (next_cycle,groupID['gid'],cycle))
            self.runQuery(query,read=0)
            
            #Save the sign off data...
            query = ("INSERT INTO `group-pdp-signoff` "
                     "(gid,year,cycle,date,manager_checked,comments) "
                     "VALUES ('%s','%s','%s','%s','%s','%s') "
                     % (groupID['gid'],year,cycle,thisday,signoff,comments))
            self.runQuery(query,read=0)
            
            err="Signoff Complete. Progressed to Cycle: %s... %s" % (next_cycle,query)
            raise cherrypy.HTTPRedirect('/grouppdp/%s/%s?e=%s'%(group_url,year,err))
            

    @cherrypy.expose
    def grouppdp_initialise(self,**kws):
        if self.loggedin():
                        
            groupName = kws['group_name'] #should be reference to groupUrl name
            yearSelect = kws['init_goals']
            
            if yearSelect == "":
                urlStr = "/grouppdp/%s?e=No Year Selected" % groupName
                raise cherrypy.HTTPRedirect(urlStr)
            
            query = "SELECT gid FROM `group` WHERE urlName='%s'" % groupName
            g_ref = self.runQuery(query,all=0)
            
            query = "SELECT gid FROM `group-pdp-data` WHERE (year='%s' AND gid='%s')" % (yearSelect, g_ref['gid'])
            result = self.runQuery(query,all=0)
            
            #test if year in database already
            if result:
                urlStr = ('/grouppdp/%s/%s?e=Goals already initialised for year %s' %
                           (groupName,yearSelect,yearSelect))
            else:    
                query = ("INSERT INTO `group-pdp-data` (gid,year,cycle) "
                        "VALUES ('%s','%s','0')" % (g_ref['gid'],yearSelect))
                for i in range(4):
                    self.runQuery(query,read=0)
            
                urlStr = ("/grouppdp/%s/%s?e=Group PDP Initialised %s" % 
                         (groupName,yearSelect,yearSelect))
            
            raise cherrypy.HTTPRedirect(urlStr)
    
    @cherrypy.expose
    def grouppdp_changeyear(self,**kws):
        if self.loggedin():
            
            name = kws['group_name']
            year = kws['year_goals']
            
            if year == "":
                urlStr = ("/grouppdp/%s?e=No Year Selected" % name)
            else:
                urlStr = ("/grouppdp/%s/%s" % (name,year))
                
            raise cherrypy.HTTPRedirect(urlStr)

    
    def getTraining(self):
        query = "SELECT tid,courseName FROM `training` WHERE available='1'"
        return self.runQuery(query,all=1)
    
    
    @cherrypy.expose
    def admin(self, **kws):
        
        t = jinja_env.get_template('admin.html')
        
        if self.loggedin():
            cookies = self.returnCookies()
            
            userName = cookies['user']
            title = cookies['title']
            query = "SELECT * FROM `person` WHERE userName='%s'" % userName
            user_dict = self.runQuery(query)[0]
            
            query = "SELECT * FROM `group` WHERE manager='%s'" % userName
            g_dict = self.runQuery(query)
            
            #check for the error flag and send to template            
            if 'e' in kws:
                err = kws['e']
            else:
                err = ""

            #Always display the group list and the user list
            query = ( "SELECT userName,firstName,lastName,isManager,uid "
                    "FROM `person` ORDER BY firstName" )
            result_people = self.runQuery(query,all=1)

            query = "SELECT groupName,gid FROM `group`"
            result_group = self.runQuery(query,all=1)

            query = "SELECT firstName,lastName,uid FROM `person` WHERE isManager = '1'"
            result_manager = self.runQuery(query,all=1)
            
            #Group edit has been initiated
            if 'group_click' in kws:
                try:
                    group_select = kws['group_list']
                    query = "SELECT groupName,gid,enabled,manager FROM `group` WHERE gid='%s'" % group_select
                    result_g_select = self.runQuery(query, all=0)
                    grp = result_g_select['groupName']
                    ebl = result_g_select['enabled']
                    man = result_g_select['manager']
                                        
                    return t.render(sideDB=user_dict,groupDB=g_dict,error=err,
                            title=title,name=cookies['fname'],people_dict=result_people,
                            manager_dict=result_manager,group_dict=result_group,
                            groupName=grp,groupEnabled=ebl,groupManager=man)
                    
                except:            
                    return t.render(sideDB=user_dict,groupDB=g_dict,error=err,
                            title=title,name=cookies['fname'],people_dict=result_people,
                            manager_dict=result_manager,group_dict=result_group,
                            groupName="",groupEnabled=0,groupManager="")
            
            #Person edit or pdp view has been initiated
            elif 'person_click' in kws:
                
                
                
                #check for person edit
                if 'edit_person' in kws:
                    try:
                        #collect their details
                        person_select = kws['people_list']
                        query = "SELECT * FROM `person` WHERE uid='%s'" % person_select
                        pselect = self.runQuery(query, all=0)
                        #err=pselect
                        uname = pselect['userName']
                        fname = pselect['firstName']
                        lname = pselect['lastName']
                        gname = pselect['groupName']
                        manag = pselect['manager']
                        ptitle = pselect['position']
                        admin = pselect['isAdmin']
                        gmana = pselect['managedGroups']
                        year  = pselect['year']
                        cycle = pselect['cycle']
                        isman = pselect['isManager']
                                                                        
                        return t.render(sideDB=user_dict,groupDB=g_dict,error=err,
                                    title=title,name=cookies['fname'],people_dict=result_people,
                                    group_dict=result_group,manager_dict=result_manager,
                                    uname=uname,fname=fname,lname=lname,gname=gname,manag=manag,
                                    admin=admin,gmana=gmana,year=year,ptitle=ptitle,
                                    cycle=cycle,isman=isman)
                    except:
                        #user not in DB
                        return t.render(sideDB=user_dict,groupDB=g_dict,error=err,
                                    title=title,name=cookies['fname'],people_dict=result_people,
                                    group_dict=result_group,manager_dict=result_manager,
                                    uname="",fname="",lname="",gname="",manag="",
                                    admin="",gmana="",year="",cycle="",isman="",ptitle="")
                        
                
                #Check for person pdp view
                if 'view_person' in kws:
                    try:
                        #collect their details
                        person_select = kws['people_list']
                        query = "SELECT userName FROM `person` WHERE uid='%s'" % person_select
                        pselect = self.runQuery(query, all=0)
                        uname = pselect['userName']
                    except:
                        uname = ""
                        
                    urlstr = '/personalpdp/%s' % uname
                    raise cherrypy.HTTPRedirect(urlstr)
                        
                return t.render(sideDB=user_dict,groupDB=g_dict,error="Reached the End...",title=title,name=cookies['fname'],
                                people_dict=result_people,group_dict=result_group,manager_dict=result_manager)
                                
                #Just display the basic page if no other data is requested    
            else:
                return t.render(sideDB=user_dict,groupDB=g_dict,error=err,
                                title=title,name=cookies['fname'],manager_dict=result_manager,
                                people_dict=result_people,group_dict=result_group)
        else:
            #If not logged in the redirect to login page
            raise cherrypy.HTTPRedirect('/login')

    @cherrypy.expose
    # An admin script to update the users database from the ldap source...
    def updateDBldap(self,**kws):
        if self.loggedin():
            
            if (("username" in kws) and ("password" in kws)):
                user = kws['username']
                passwd = kws['password']
            
            
            ldap_server = values['LDAP']['ldap_server']
            acct_sx = values['LDAP']['acct_sx']
            base_dn = "OU=Staff,%s" % values['LDAP']['base_dn']
                       
            
            connect = ldap.open(ldap_server)
        
            try:
                connect.simple_bind_s(user+acct_sx,passwd)
            
                result = connect.search_s(base_dn,ldap.SCOPE_SUBTREE, 
                        '(&(objectclass=User) (sAMAccountName=*))',
                        ['title','givenName','sn','sAMAccountName'])
            
                connect.unbind_s()
            
            except ldap.LDAPError:
                connect.unbind_s()
                error = 'Unable to process LDAP Request. Please try again...'
            
                raise cherrypy.HTTPRedirect('/admin?e=%s' % error)
        
            update = 0
        
            for j in range(len(result)):
                if 'title' in result[j][1]:
                    title = result[j][1]['title'][0]
                else:
                    title = ''
                
                if 'givenName' in result[j][1]:    
                    fname = result[j][1]['givenName'][0]
                else:
                    fname = ''
                
                if 'sn' in result[j][1]:
                    lname = result[j][1]['sn'][0]
                else:
                    lname = ''
                    
                if 'sAMAccountName' in result[j][1]:
                    uname = result[j][1]['sAMAccountName'][0]
                else:
                    uname = ''
                
                if '_' in uname:
                    continue
                
                query = ("INSERT INTO `person` "
                         "SET userName='%s',firstName='%s',lastName='%s',position='%s'"
                         % (uname,fname,lname,title) )

                try:            
                    self.runQuery(query,read=0)
                except:
                    continue

                update += 1
                
            error = '''Staff database updated from the Active Directory. %s new Staff added. 
                       Manual editing may be required''' % update
            raise cherrypy.HTTPRedirect('/admin?e=%s' % error)

    def prettynames(self, uname_list):
        # Return a list of pretty names from a submitted username list
        pass

    @cherrypy.expose
    def groups(self):
        if self.loggedin():
            #cur = db.cursor()
            #cur.execute("SELECT * FROM `group`")
            result={}
            g_query = "SELECT * FROM `group`"
            result = self.runQuery(g_query)
            return json.dumps(result)
    
    @cherrypy.expose
    def people(self):
        if self.loggedin():
            #cur = db.cursor()
            #cur.execute("SELECT * FROM `person`")
            result={}
            p_query = "SELECT * FROM `person`"
            result = self.runQuery(p_query)   
            return json.dumps(result)
    
    @cherrypy.expose
    #Check if the user 'uname' is already in the database
    def isUserDB(self,uname):
        #cur_check = db.cursor()
        query = "SELECT userName FROM `person` WHERE userName = '%s'" % uname

        result = self.runQuery(query,all=0)
        if result:
        #if len(result):
            return result
        else:
            return False
            
        #try:
        #    cur_check.execute(query)
        #    if cur_check.rowcount:
        #        #cherrypy.log(cur_check.rowcount)
        #        return cur_check.fetchone()
        #    else:
        #        return False
        #except:
        #    #return "Error! %d: %s" % (e.args[0],e.args[1])
        #    return False
    
    @cherrypy.expose
    #Check if gname is in the database already        
    def isGroupDB(self,gname):
        #cur_check = db.cursor()
        query = "SELECT groupName FROM `group` WHERE groupName = '%s'" % gname
        
        result = self.runQuery(query,all=0)
        #if len(result):
        if result:
            return result
        else:
            return False
        #try:
        #    cur_check.execute(query)
        #    if cur_check.rowcount:
        #        return cur_check.fetchone()
        #    else:
        #        return False
        #except:
        #    return False
        
    
    @cherrypy.expose
    #general db query helper
    def runQuery(self,query,all=1,read=1):
        cur_run = db.cursor()
        try:
            cur_run.execute(query)
            db.commit()
            #return cur_run.fetchall()
            if read:
                if all:
                    return cur_run.fetchall()
                else:
                    return cur_run.fetchone()
            else:
                return True
        except:
            db.rollback()
            return {}
    
    @cherrypy.expose
    #Update the DB with group information
    def admin_update_group(self, **kws):
        if self.loggedin():
            g_name = kws['group_name']
            g_man = kws['group_manager']
            
            if 'group_enabled' in kws:
                g_enable = kws['group_enabled']
            else:
                g_enable = 'off'
            
            #create a url name, all lower case, space replaced by underscore
            g_url = g_name.lower().replace(" ","_")
            
            #read the the radio button and convert to int
            if g_enable == 'on':
                g_enable = 1
            else:
                g_enable = 0
            
            #group name not specified
            if g_name == "":
                raise cherrypy.HTTPRedirect('/admin?e=noGroup')
            
            #Check if already in the DB
            if self.isGroupDB(g_name):
                query = ("UPDATE `group` SET groupName='%s',enabled='%s',urlName='%s',manager='%s' WHERE groupName='%s'" 
                        % (g_name,g_enable,g_url,g_man,g_name))
            #Else update the group already in the DB
            else:
                query = ("INSERT INTO `group` (groupName,enabled,urlName,manager) VALUES ('%s','%s','%s','%s')" 
                        % (g_name,g_enable,g_url,g_man))
                
            self.runQuery(query,read=0)
            
            urlStr = '/admin?e=Group Data Updated'
            raise cherrypy.HTTPRedirect(urlStr)
            
        else:
            #Not logged in redirect...
            raise cherrypy.HTTPRedirect('/login')
    
    @cherrypy.expose
    #Update the DB with the user information
    def admin_update_person(self, **kws):
        if self.loggedin():
                    
            #Collect the information entered from the form
            p_manager = kws['select_manager']
            p_lname = kws['person_lastname']
            p_fname = kws['person_firstname']
            p_uname = kws['person_username']
            p_group = kws['select_group']
            p_title = kws['person_title']
            
            
            #query = 
            
            p_year = self.default_year()
            
            if 'person_ismanager' in kws:
                #p_ismanager = kws['person_ismanager']
                p_ismanager = 1
            else:
                #p_ismanager = 'off'
                p_ismanager = 0

            if 'person_isadmin' in kws:
                p_isadmin = 1
            else:
                p_isadmin = 0
            
            if p_uname == "":
                raise cherrypy.HTTPRedirect('/admin?e=noUser')
            

            #If user already in Database the update, else add a new user
            if self.isUserDB(p_uname):

                    query = ("UPDATE `person` SET "
                             "groupName='%s',userName='%s',firstName='%s',isAdmin='%s',"
                             "lastName='%s',manager='%s',isManager='%s',position='%s' "
                             "WHERE userName='%s'" 
                             % (p_group,p_uname,p_fname,p_isadmin,p_lname,
                                p_manager,p_ismanager,p_title,p_uname))
            else:
                    query = ("INSERT INTO `person` "
                            "(groupName,userName,firstName,lastName,isAdmin,"
                            "position,manager,isManager,year) VALUES "
                            "('%s','%s','%s','%s','%s','%s','%s','%s')" % 
                            (p_group,p_uname,p_fname,p_lname,p_isadmin,
                            p_title,p_manager,p_ismanager,p_year))

            
            self.runQuery(query,read=0)

            urlStr = '/admin?e=User Data Updated'
            raise cherrypy.HTTPRedirect(urlStr)

#class Admin(object):
#    @cherrypy.expose
#    def index(self):
#        return "Hello Admin!"

cherrypy.config.update({
    'server.socket_host': '127.0.0.1',
    'server.socket_port': 7000
})

config = {
    '/':
        {'tools.staticdir.debug': True,
         'log.screen': True,
         'tools.sessions.on': True,
         'tools.sessions.type': "ram",
         'tools.sessions.timeout': 360
        },
    '/templates':
        {'tools.staticdir.on': True,
         'tools.staticdir.dir': TEMPLATE_DIR
        },
    '/styles':
        {'tools.staticdir.on': True,
         'tools.staticdir.dir': STYLES_DIR
        },
    '/js':
        {'tools.staticdir.on': True,
         'tools.staticdir.dir': JS_DIR
        },
    '/images':
        {'tools.staticdir.on': True,
         'tools.staticdir.dir': IMG_DIR
        }
}

cherrypy.tree.mount(PeedyPee(),'/', config=config)
#cherrypy.tree.mount(Admin(),'/admin', config=config)
cherrypy.engine.autoreload.on = True
cherrypy.engine.autoreload.frequency = 5
cherrypy.engine.autoreload.files.add('app_pdp.py') #remove for production
cherrypy.engine.start()

