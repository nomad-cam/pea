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

from help import Help

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_DIR = os.path.join(BASE_DIR,'templates/')
STYLES_DIR = os.path.join(BASE_DIR,'styles/')
JS_DIR = os.path.join(BASE_DIR,'js/')
IMG_DIR = os.path.join(BASE_DIR,'images/')

jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(TEMPLATE_DIR), autoescape=True)

config_data = open('config.json')
values = json.load(config_data)
config_data.close()

#db = MySQLdb.connect(host=values['DB']['host'],user=values['DB']['dbuser'],
#                    passwd=values['DB']['password'],db=values['DB']['database'],
#                    cursorclass=MySQLdb.cursors.DictCursor)


class PeedyPee(object):
    
    def loggedin(self):
        user = cherrypy.session.get('user')
        if user:
            return user
        else:
            return False

    def returnCookies(self):
        
        try:
            user = cherrypy.session.get('user')
            fname = cherrypy.session.get('name')
            position = cherrypy.session.get('position')
            
            return {'user': user, 'fname': fname,'title': position}
        except:
            return False

    @cherrypy.expose
    def index(self,**kws):
        if self.loggedin():
            cookies = self.returnCookies()
                        
            query = "SELECT uid FROM `person` WHERE userName='%s'" % cookies['user']
            uid = self.runQuery(query, all=0)['uid']
                        
            err = []
            if 'e' in kws:
                err.append(kws['e'])
                err.append(kws['ref'])
                if 'id' in kws:
                    err.append(kws['id'])
                else:
                    err.append('')
            
            query = "SELECT * FROM `person` WHERE uid='%s'" % uid
            side_dict = self.runQuery(query)[0]
            userName = side_dict['userName']
            title = side_dict['position']
            name = "%s %s" % ( side_dict['firstName'], side_dict['lastName'])
            
            query = "SELECT * FROM `group` WHERE manager='%s'" % uid
            g_dict = self.runQuery(query)
            
            #used for side bar details
            g_manager_name = self.convertUser(side_dict['manager'])
            g_name = self.convertGroup(side_dict['groupName'])
            
            query = "SELECT userName,firstName,lastName FROM `person` WHERE manager='%s'" % uid
            group_list = self.runQuery(query,all=1)
                        
            t = jinja_env.get_template('index.html')
            return t.render(sideDB=side_dict,groupDB=g_dict,error=err,
                            userName=userName,title=title,firstName=name,
                            groupList=group_list,gName=g_name,gManagerName=g_manager_name)
        else:
            raise cherrypy.HTTPRedirect("/login")
            
                
    @cherrypy.expose
    def logout(self):
        
        cherrypy.lib.sessions.expire()
        
        raise cherrypy.HTTPRedirect("/")
    
    @cherrypy.expose
    def login(self, **kws):
        t = jinja_env.get_template('login.html')
        
        err = []
        if 'e' in kws:
            err.append(kws['e'])
            err.append(kws['ref'])
            if 'id' in kws:
                err.append(kws['id'])
            else:
                err.append('')
        
        return t.render(error=err)
    
    @cherrypy.expose
    def dologin(self, **kws):


        if ((kws["username"]) and (kws["password"])):
            user = kws['username']
            passw = kws['password']
        else:
            error = "No Username or Password provided..."
            urlStr = "/login?e=%s&ref=/login" % (error)
            raise cherrypy.HTTPRedirect(urlStr)
            
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
            
            cherrypy.session['user'] = user
            cherrypy.session['position'] = position
            cherrypy.session['name'] = name
            
            connect.unbind_s()
            
            raise cherrypy.HTTPRedirect('/')
            
        except ldap.LDAPError:
            connect.unbind_s()
            
            error = 'Incorrect Login Details. Please try again...'
            urlStr = '/login?e=%s&ref=/login' % (error)
            raise cherrypy.HTTPRedirect(urlStr)

    @cherrypy.expose
    def changelog(self):
        t = jinja_env.get_template('change.html')
        return t.render()


    @cherrypy.expose
    def personalpdp(self,user=None,year=None,**kws):
        if self.loggedin():
            cookies = self.returnCookies()
            
            query = "SELECT uid,userName FROM `person` WHERE userName='%s'" % cookies['user']
            result = self.runQuery(query,all=0)
            uid = result['uid']
            userName = result['userName']
            
            if year == None:
                year = self.default_year()
            
            #refer = ''
            error = []
            #id = ''
            if 'e' in kws:
                error.append( kws['e'] )
                error.append( kws['ref'] )
                if 'id' in kws:
                    error.append( kws['id'] )
                else:
                    error.append('')
            #else:
            #    error = ['','','']
            
            # enable managers and admin to view other pdps
            if user:
                #must be admin or manager to view others pdp
                if (self.isAdmin(uid) or self.isManager(uid)):
                    selectName = user #remote user
                else:
                    selectName = userName
            else:
                selectName = userName #currently logged in user
            
            query = ("SELECT * FROM `person` WHERE userName='%s'" % selectName)
            select_dict = self.runQuery(query, all=0)
                                        
            query = "SELECT * FROM `person` WHERE uid='%s'" % uid
            side_dict = self.runQuery(query)[0]
            
            query = "SELECT * FROM `group` WHERE manager='%s'" % uid
            g_dict = self.runQuery(query)
            
            query = ("SELECT MAX(cycle) AS cycle FROM `person-pdp-data` "
                     "WHERE (uid='%s' AND year='%s')" % (select_dict['uid'],year))
            current_cycle = self.runQuery(query, all=0)
            
            
        
            if 'add_pdp_row' in kws:
                #add another row to the database, first save the current edits...
                #pass
                other = None
                if "course_other[]" in kws:
                    other = kws['course_other[]']
        
                aligns = []
                for t in range(len(kws['pid[]'])):
                    tmpStr = "person_aligns[%s]" % kws['pid[]'][t]
                    #set value to false/0 if not set
                    if tmpStr in kws:
                        #convert true and false into 1 / 0
                        if 'true' in kws[tmpStr]:
                            aligns.append( 1 )
                        else:
                            aligns.append( 0 )
                    else:
                        aligns.append( 0 )
                                                 
                # First save data then add a new line                                
                for j in range(len(kws['pid[]'])):
                    query = ("UPDATE `person-pdp-data` "
                         "SET goal='%s', align='%s', reason='%s', deadline='%s', "
                         "budget='%s', course='%s', courseOther='%s' "
                         "WHERE pid='%s'" 
                         % (kws['person_goals[]'][j],aligns[j],
                         kws['person_reason[]'][j],kws['person_deadline[]'][j],
                         kws['person_budget[]'][j],kws['person_training[]'][j],other[j],kws['pid[]'][j]))
                         
                    self.runQuery(query,read=0)
                                
                # Second add a blank line to the DB before redirecting to same page
                query = ("INSERT INTO `person-pdp-data` (uid, year, cycle)"
                         "VALUES (%s,%s,%s)" % (select_dict['uid'], year, current_cycle['cycle']))
                self.runQuery(query,read=0)
                
                err = "New line added to table... " #+ json.dumps(aligns)
                refStr = cherrypy.request.path_info
                
                raise cherrypy.HTTPRedirect('/personalpdp/%s/%s/?e=%s&ref=%s&id=person_goals'% (selectName,year,err,refStr))
                
            if 'save_pdp_data' in kws:
                other = None
                if "course_other[]" in kws:
                    other = kws['course_other[]']
                
                man_comms = None
                if "manager_comments[]" in kws:
                    man_comms = kws["manager_comments[]"]
                
                aligns = []
                for t in range(len(kws['pid[]'])):
                    tmpStr = "person_aligns[%s]" % kws['pid[]'][t]
                    #set value to false/0 if not set
                    if tmpStr in kws:
                        #convert true and false into 1 / 0
                        if 'true' in kws[tmpStr]:
                            aligns.append( 1 )
                        else:
                            aligns.append( 0 )
                    else:
                        aligns.append( 0 )
                
                #Save data
                for j in range(len(kws['pid[]'])):
                    query = ("UPDATE `person-pdp-data` "
                         "SET goal='%s', align='%s', reason='%s', deadline='%s', "
                         "budget='%s', course='%s', courseOther='%s', comments='%s' "
                         "WHERE pid='%s'" 
                         % (kws['person_goals[]'][j],aligns[j],
                         kws['person_reason[]'][j],kws['person_deadline[]'][j],
                         kws['person_budget[]'][j],kws['person_training[]'][j],other[j],
                         man_comms[j],kws['pid[]'][j]))
                         
                    self.runQuery(query,read=0)
                
                err = "User PDP data updated successfully..."
                refStr = cherrypy.request.path_info
                
                raise cherrypy.HTTPRedirect('/personalpdp/%s/%s/?e=%s&ref=%s&id=person_goals#person_goals'%(selectName,year,err,refStr))

            if 'save_values' in kws:
                #pass
                #Test if values already written to DB for current user this year
                query = "SELECT vid FROM `values-data` WHERE (uid='%s' AND year='%s')" % (select_dict['uid'],year)
                result = self.runQuery(query,all=0)
                
                if not result:
                    for k in range(len(kws['value_id[]'])):
                        query = ("INSERT INTO `values-data` (uid,value,cycle,year,grade,comment) VALUES (%s,%s,%s,%s,%s,'%s') "
                                % (select_dict['uid'],kws['value_id[]'][k],current_cycle['cycle'],
                                year,kws['value_grade[]'][k],kws['value_comments[]'][k]) )
                        self.runQuery(query,read=0)
                    err = "Value data saved to DB..."
                else:
                    err = "Unable to update Values table, data already saved..."
                
                #err += query
                refStr = cherrypy.request.path_info
                
                raise cherrypy.HTTPRedirect('/personalpdp/%s/%s/?e=%s&ref=%s&id=values#values'%(selectName,year,err,refStr))
                
            if 'save_compliance' in kws:
                #pass
                #Test if values already written to DB for current user this year
                query = "SELECT cid FROM `compliance-data` WHERE (uid='%s' AND year='%s')" % (select_dict['uid'],year)
                result = self.runQuery(query,all=0)
                
                if not result:
                    for k in range(len(kws['comply_id[]'])):
                        query = ("INSERT INTO `compliance-data` (uid,area,cycle,year,grade,comment) VALUES (%s,%s,%s,%s,%s,'%s') "
                                % (select_dict['uid'],kws['comply_id[]'][k],current_cycle['cycle'],
                                year,kws['comply_grade[]'][k],kws['comply_comments[]'][k]) )
                        self.runQuery(query,read=0)
                    err = "Compliance data saved to DB..."
                else:
                    err = "Unable to update Compliance table, data already saved..."
                
                #err += cherrypy.request.browser_url
                refStr = cherrypy.request.path_info
                
                raise cherrypy.HTTPRedirect('/personalpdp/%s/%s/?e=%s&ref=%s&id=compliance#compliance'%(selectName,year,err,refStr))
                
            # Need to make sure getting current year and latest cycle
            query = ("SELECT * FROM `group-pdp-data` WHERE (gid='%s' AND cycle='%s' AND year='%s' AND visible=1)" 
                    % (select_dict['groupName'],select_dict['cycle'],year))
            gpdps = self.runQuery(query,all=1)
            #cherrypy.log.error(query)
            
            owner_list = []
            for l in range(len(gpdps)):
                owner_list.append(self.convertUid(gpdps[l]['owners']))
                #error[0] += gpdps[l]['owners']
            #cherrypy.log.error(json.dumps(owner_list))
            
            query = ("SELECT * FROM `person-pdp-data` WHERE (uid='%s' AND year='%s' AND cycle='%s')" 
                    %(select_dict['uid'],year,select_dict['cycle']))
            pdp = self.runQuery(query,all=1)
            #error=query
            
            query = ("SELECT * FROM `values-data` WHERE (uid='%s' AND year='%s' AND cycle='%s')"
                    %(select_dict['uid'],year,select_dict['cycle']))
            values_data = self.runQuery(query, all=1)
            #cherrypy.log.error(query)
            
            query = ("SELECT * FROM `compliance-data` WHERE (uid='%s' AND year='%s' AND cycle='%s')"
                    %(select_dict['uid'],year,select_dict['cycle']))
            compliance_data = self.runQuery(query, all=1)
            #cherrypy.log.error(query)
            
            query = "SELECT DISTINCT year FROM `person-pdp-data` WHERE uid='%s'" % select_dict['uid']
            avail_view_year = self.runQuery(query,all=1)
            
            query = "SELECT DISTINCT year FROM `group-pdp-data` WHERE gid='%s'" % select_dict['groupName']
            avail_init_year = self.runQuery(query,all=1)
            
            query = ("SELECT course,courseOther FROM `group-pdp-data` WHERE (gid='%s' AND year='%s' AND cycle='%s')"
                    % (select_dict['groupName'],year,select_dict['cycle']))
            result = self.runQuery(query,all=1)
            #cherrypy.log.error(json.dumps(result))
            g_train_name = []
            for k in range(len(result)):
                if result[k]['course'] == 2:
                    #if training couse is other get the course name
                    g_train_name.append(result[k]['courseOther'])
                else:
                    #else convert the id to a course name
                    g_train_name.append(self.convertTraining(result[k]['course']))

            #used for side bar details
            g_manager_name = self.convertUser(select_dict['manager'])
            g_name = self.convertGroup(select_dict['groupName'])

            p_training = self.getTraining()
            p_values = self.getValues()
            p_compliance = self.getCompliance()
            p_opt_val = self.getOptions(2) #rarely/sometime/always
            p_opt_comp = self.getOptions(1) #yes/no/maybe

            #error = p_opt_val
            
            t = jinja_env.get_template('personal_pdp.html')
            return t.render(sideDB=side_dict,groupDB=g_dict,selectDB=select_dict,error=error,
                            gpdps=gpdps,person_pdp=pdp,training=p_training,values=p_values,
                            compliance=p_compliance,val_opts=p_opt_val,comp_opts=p_opt_comp,
                            valuesDB=values_data,complianceDB=compliance_data,ownersList=owner_list,
                            aViewYear=avail_view_year,aInitYear=avail_init_year,gTrainName=g_train_name,
                            gName=g_name,gManagerName=g_manager_name,
                            user=userName,title=cookies['title'],name=cookies['fname'])
            
        else:
            raise cherrypy.HTTPRedirect('/login')

    def default_year(self):
        #pdp year starts at start of pdp year (financial year)
        #so to get in the right year cycle - need to set last year if in the new year
        
        if date.today().month <= 6:
            return date.today().year - 1
        else:
            return date.today().year

    @cherrypy.expose
    def grouppdp(self,group=None,year=None,**kws):
        if self.loggedin():
            cookies = self.returnCookies()
            
            err = []
            if 'e' in kws:
                err.append( kws['e'] )
                err.append( kws['ref'] )
                if 'id' in kws:
                    err.append( kws['id'] )
                else:
                    err.append('')
                
            
            if year == None:
                year = self.default_year()
            
            #userName = cookies['user']
            query = "SELECT uid FROM `person` WHERE userName='%s'" % cookies['user']
            uid = self.runQuery(query,all=0)['uid']
            
            query = "SELECT * FROM `person` WHERE uid='%s'" % uid
            side_dict = self.runQuery(query)[0]
            
            query = "SELECT * FROM `group` WHERE manager='%s'" % uid
            g_dict = self.runQuery(query)
            
                       
            query = ("SELECT gid, groupName, manager FROM `group` WHERE urlName='%s'") % group
            groupID = self.runQuery(query, all=0)
            
            query = ("SELECT MAX(cycle) AS cycle FROM `group-pdp-data` "
                     "WHERE (gid='%s' AND year='%s')"
                      % (groupID['gid'],year))
            current_cycle = self.runQuery(query, all=0)
            
            g_training = self.getTraining()
            g_members = self.getGroupMembers(groupID['gid']) 
            
            if 'add_group_row' in kws:
                other = None
                if "course_other[]" in kws:
                    other = kws['course_other[]']
            
                #first make sure that at least one item is selected
                    names = []
                    # Reference the group_member list
                for j in range(len(kws['zid[]'])):                    
                    tmpStr = "group_owners[%s]" % kws['zid[]'][j]
                    if tmpStr in kws:
                        names.append( kws[tmpStr] )
                    else:
                        names.append("0")
                 
                
                # First save data then add a new line                                
                for j in range(len(kws['zid[]'])):
                    query = ("UPDATE `group-pdp-data` "
                         "SET goalTitle='%s', owners='%s', description='%s', deadline='%s', "
                         "budget='%s', course='%s', courseOther='%s' "
                         "WHERE zid='%s'" 
                         % (kws['group_goal[]'][j],json.dumps(names[j]),
                         kws['group_description[]'][j],kws['group_deadline[]'][j],
                         kws['group_budget[]'][j],kws['group_training[]'][j],other[j],kws['zid[]'][j]))
                         
                    self.runQuery(query,read=0)
                    
                
                # Second add a blank line to the DB before redirecting to same page
                query = ("INSERT INTO `group-pdp-data` (gid, year, cycle)"
                         "VALUES (%s,%s,%s)" % (groupID['gid'], year, current_cycle['cycle']))
                self.runQuery(query,read=0)
                
                #error = ""
                
                raise cherrypy.HTTPRedirect('/grouppdp/%s/%s?e=%s&ref=%s'% (group,year,err,cherrypy.request.path_info))
            
            elif 'save_group_data' in kws:
                other = None
                if "course_other[]" in kws:
                    other = kws['course_other[]']
            
                # Reference the group_member list
                names = []
                for j in range(len(kws['zid[]'])):
                    tmpStr = "group_owners[%s]" % kws['zid[]'][j] #contains owners list uid
                    if tmpStr in kws:   # test if any value has been selected
                        names.append(kws[tmpStr]) #append as string list
                    else:
                        names.append("0") #if no value selected set to 0
                   
                            
                # Save the current data
                for j in range(len(kws['zid[]'])):
                     query = ("UPDATE `group-pdp-data` "
                         "SET goalTitle='%s', owners='%s', description='%s', deadline='%s', "
                         "budget='%s', course='%s', courseOther='%s' "
                         "WHERE zid='%s'" 
                         % (kws['group_goal[]'][j],json.dumps(names[j]),
                         kws['group_description[]'][j],kws['group_deadline[]'][j],
                         kws['group_budget[]'][j],kws['group_training[]'][j],other[j],kws['zid[]'][j]))
                         
                     self.runQuery(query,read=0)
                err = "Group row data saved to DB"
                
                raise cherrypy.HTTPRedirect('/grouppdp/%s/%s?e=%s&ref=%s'% (group,year,err,cherrypy.request.path_info))
            
            query = ("SELECT * FROM `group-pdp-data` WHERE (gid='%s' AND year='%s' AND cycle='%s')"
                    % (groupID['gid'], year, current_cycle['cycle']))
            gpdps = self.runQuery(query, all=1)
            
            g_temp = []
            for k in range(len(gpdps)):
                if gpdps[k]['owners']:
                    g_temp.append(json.loads(gpdps[k]['owners']))
                else:
                    g_temp.append('0') #default to all as ALL is always present in the template
                
            g_owners = [map(int, x) for x in g_temp]
            
            #get the available years for the dropdown box
            query = "SELECT DISTINCT year FROM `group-pdp-data` WHERE gid='%s'" % groupID['gid']
            avail_view_year = self.runQuery(query,all=1)
            
            #query = "SELECT DISTINCT year FROM `group-pdp-data` WHERE gid='%s'" % groupID['gid']
            #avail_init_year = self.runQuery(query,all=1)
            #cherrypy.log.error(json.dumps(avail_init_year))
            avail_init_year = [{"year": year}, {"year": year + 1}]
            
            
            
            #used for side bar details
            g_manager_name = self.convertUser(side_dict['manager'])
            g_name = self.convertGroup(side_dict['groupName'])
            
            t = jinja_env.get_template('group_pdp.html')
            return t.render(sideDB=side_dict,groupDB=g_dict,err=err,training=g_training,
                            user=cookies['user'],title=cookies['title'],name=cookies['fname'],
                            year=year,cycle=current_cycle['cycle'],group_url=group,
                            groupPDPs=gpdps,groupName=groupID['groupName'],
                            gOwners=g_owners,gName=g_name,gManagerName=g_manager_name,
                            aInitYear=avail_init_year,aViewYear=avail_view_year,
                            manager=groupID['manager'],gMembers=g_members)
            
        else:
            raise cherrypy.HTTPRedirect('/login')


    @cherrypy.expose
    def personalpdp_signoff(self,userName,**kws):
        if self.loggedin():
            cycle = int(kws['p_cycle'])
            year = int(kws['p_year'])
            
            err = json.dumps(kws)
            
            if 'employee-sign' in kws:
                emp_sign = 1
            else:
                emp_sign = ""
                
            if 'employee-comment' in kws:
                emp_comment = kws['employee-comment']
            else:
                emp_comment = "No Comment"
                
            if 'manager-sign' in kws:
                man_sign = 1
            else:
                #The manager should sign off first (or at same time)
                err = "A manager has not signed off on this PDP"
                ref = ('/personalpdp/%s' % userName)
                raise cherrypy.HTTPRedirect('/personalpdp/%s?e=%s&ref=%s&id=bottom#bottom' % (userName,err,ref))
            
            thisday = date.today().strftime("%Y/%m/%d")
            next_cycle = cycle + 1
            
            if next_cycle > 3:
                next_cycle = 1
                year = year + 1
            
            #Get the uid
            query = "SELECT uid FROM `person` WHERE userName='%s'" % userName
            userID = self.runQuery(query,all=0)
            
            
            #Before donig too much check if all the other required tables are filled out for cycle 3...
            #Redirect if not all saved...
            if cycle == 3:
                err = ""
                #check if values-data has been written
                #get the number of values...
                query = ("SELECT COUNT(vid) FROM `values` WHERE disabled IS NULL ")
                numVals = self.runQuery(query,all=0)
                query = ("SELECT COUNT(uid) FROM `values-data` WHERE (uid='%s' AND cycle='%s' AND year='%s')" 
                         % (userID['uid'],cycle,year))
                result = self.runQuery(query,all=1) 
                
                if numVals != result:
                    err += "Not all values data has been entered. "
                    
                #check if compliance-data has been written
                query = ("SELECT COUNT(cid) FROM compliance WHERE disabled IS NULL")
                numComp = self.runQuery(query,all=0)
                query = ("SELECT COUNT(uid) FROM `compliance-data` WHERE (uid='%s' AND cycle='%s' AND year='%s')"
                         % (userID['uid'],cycle,year))
                
                if numComp != result:
                    err += "Not all compliance data has been entered. "
                    
                #check if comments have been written for the person-pdp-data                
                query = ("SELECT COUNT(uid) FROM `person-pdp-data` "
                         "WHERE (uid='%s' AND cycle='%s' AND year='%s')"
                         % (userID['uid'],cycle,year))
                numComm = self.runQuery(query,all=0)
                query = ("SELECT COUNT(uid) FROM `person-pdp-data` "
                         "WHERE (uid='%s' AND cycle='%s' AND year='%s' AND (comments IS NOT "" OR comments IS NOT NULL))"
                         % (userID['uid'],cycle,year))
                result = self.runQuery(query,all=0)
                
                if numComm != result:
                    err += "Not all performance comment data has been entered. "
                
                
                if err:
                    err += "Please fix this before submitting again..."
                    ref = ('/personalpdp/%s' % userName)
                    raise cherrypy.HTTPRedirect('/personalpdp/%s?e=%s&ref=%s&id=bottom#bottom' % (userName,err,ref))
            
            
            #Check if there is already an entry in the DB (ie if man has signed but not emp)
            query = ("SELECT `manager-sign`,`person-sign` FROM `person-pdp-signoff` WHERE (uid='%s' AND cycle='%s' AND year='%s')"
                    % (userID['uid'], cycle, year))
            result = self.runQuery(query,all=0)
            
            
            if result:
                # manager must have signed if employee has signed...
                if result['person-sign']:
                    err = "The PDP for this cycle has already been signed off"
                    ref = ('/personalpdp/%s#botom' % userName)
                    raise cherrypy.HTTPRedirect('/personalpdp/%s?e=%s&ref=%s' % (userName,err,ref))
                
                # update the record with the employee sign off
                else:
                    query = ("UPDATE `person-pdp-signoff` SET `person-sign`='%s',`person-date`='%s',`person-comment`='%s' "
                             "WHERE (uid='%s' AND cycle='%s' AND year='%s')"
                             % (emp_sign,thisday,emp_comment,userID['uid'],cycle,year))
                    self.runQuery(query,read=0)
                    #cherrypy.log.error(query)
                    self.updateUserCycle(userID['uid'],next_cycle,year)
                
            else:
                # insert a new field in table
                query = ("INSERT INTO `person-pdp-signoff` (uid,year,cycle,`manager-sign`,`manager-date`,"
                         "`person-sign`,`person-date`,`person-comment`) "
                         "VALUES ('%s','%s','%s','%s','%s','%s','%s','%s')"
                         % (userID['uid'],year,cycle,man_sign,thisday,emp_sign,thisday,emp_comment) )
                self.runQuery(query,read=0)
                #cherrypy.log.error(query)
                
                if emp_sign and man_sign:
                    #update the employee cycle +1
                    self.updateUserCycle(userID['uid'],next_cycle,year)
                    
                    
                    
                    
            err = "The PDP for this cycle has now been signed off"
            ref = ('/personalpdp/%s' % userName)
            raise cherrypy.HTTPRedirect('/personalpdp/%s?e=%s&ref=%s&id=bottom' % (userName,err,ref))
                
        
            #raise cherrypy.HTTPRedirect('/personalpdp/%s?e=%s&ref=/personalpdp/%s#bottom' % (userName,err,userName))


    def updateUserCycle(self,uid,cycle,year):
        # Update the cycle count in the `person` table
        query = ("UPDATE `person` SET cycle='%s',year='%s' WHERE uid='%s'" 
                 % (cycle,year,uid))
        self.runQuery(query,read=0)
        
        last_cycle = cycle - 1
        
        
        query = ("INSERT INTO `person-pdp-data` (uid,cycle,year,goal,align,reason,"
                "deadline,budget,course,courseOther,comments) " 
                "SELECT uid,%s,%s,goal,align,reason,deadline,budget,course,courseOther,comments "
                "FROM `person-pdp-data` "
                "WHERE (uid='%s' AND year='%s' AND cycle='%s')"
                % (cycle,year,uid,year,last_cycle))
        self.runQuery(query,read=0)
        
        
        return True
        


    @cherrypy.expose
    def grouppdp_signoff(self,**kws):
        if self.loggedin():
            group_url = kws['group_url']
            year = kws['s_year'] #current year
            cycle = kws['s_cycle'] #current cycle
            if 'manager-sign' in kws:
                signoff = 1
            else:
                err = "The signoff box was not checked"
                raise cherrypy.HTTPRedirect('/grouppdp/%s/%s?e=%s&ref=/grouppdp/%s/%s'%(group_url,year,err,group_url,year))
            
            # dont care if theres no comments...
            if 'comments' in kws:
                comments = kws['comments']
            else:
                comments = ''
                
            last_cycle = int(cycle) - 1
            next_cycle = int(cycle) + 1
            # cycle range is 1 to 3
            #//TODO: determine actions when complete cycle 3...
            if next_cycle > 3:
                next_cycle = 1
                #//TODO: update year also
            
            thisday = date.today().strftime("%Y/%m/%d")
            query = ( "SELECT gid FROM `group` WHERE urlName='%s'" % group_url )
            groupID = self.runQuery(query,all=0)
            
            # //TODO: verify operation of the hand-over procedure
            
            # //TODO: implement the visible variable in DB
            #set current cycle to visible
            query = ("UPDATE `group-pdp-data` SET visible=1 WHERE (gid='%s' AND cycle='%s' AND year='%s')"
                    % (groupID['gid'],cycle,year) )
            self.runQuery(query,read=0)
            
            #set last cycle to not visible
            #if current cycle is 1, then there is no last_cycle to set... so keep calm and carry on
            if last_cycle:
                query = ("UPDATE `group-pdp-data` SET visible=0 WHERE (gid='%s' AND cycle='%s' AND year='%s')"
                    % (groupID['gid'],last_cycle,year) )
                self.runQuery(query,read=0)
            
            # "Store" the current cycle group goals and copy to new cycle            
            query = ("INSERT INTO `group-pdp-data` "
                    "(gid,cycle,year,goalTitle,description,owners,deadline,budget,course,courseOther) "
                     "SELECT gid,'%s',year,goalTitle,description,owners,deadline,budget,course,courseOther "
                     "FROM `group-pdp-data` "
                     "WHERE (gid='%s' AND cycle='%s' AND year='%s')" % (next_cycle,groupID['gid'],cycle,year))
            self.runQuery(query,read=0)
            
            #Save the sign off data...
            query = ("INSERT INTO `group-pdp-signoff` "
                     "(gid,year,cycle,date,manager_checked,comments) "
                     "VALUES ('%s','%s','%s','%s','%s','%s') "
                     % (groupID['gid'],year,cycle,thisday,signoff,comments))
            self.runQuery(query,read=0)
            
            #Only update person.cycle if it is currently set to 0
            
            # if person.cycle = 0
            #    update to new cycle person.cycle
            
            err="Signoff Complete. Progressed to Cycle: %s..." % (next_cycle)
            raise cherrypy.HTTPRedirect('/grouppdp/%s/%s?e=%s&ref=/grouppdp/%s/%s'%(group_url,year,err,group_url,year))
            

    @cherrypy.expose
    def grouppdp_initialise(self,**kws):
        if self.loggedin():
                        
            groupName = kws['group_name'] #should be reference to groupUrl name
            yearSelect = kws['init_goals']
            
            if yearSelect == "":
                urlStr = "/grouppdp/%s?e=No Year Selected&ref=/grouppdp/%s" % (groupName,groupName)
                raise cherrypy.HTTPRedirect(urlStr)
            
            query = "SELECT gid FROM `group` WHERE urlName='%s'" % groupName
            g_ref = self.runQuery(query,all=0)
            
            query = "SELECT gid FROM `group-pdp-data` WHERE (year='%s' AND gid='%s')" % (yearSelect, g_ref['gid'])
            result = self.runQuery(query,all=0)
            
            #test if year in database already
            if result:
                urlStr = ('/grouppdp/%s/%s?e=Goals already initialised for year %s&ref=/grouppdp/%s/%s' %
                           (groupName,yearSelect,yearSelect,groupName,yearSelect))
            else:    
                query = ("INSERT INTO `group-pdp-data` (gid,year,cycle) "
                        "VALUES ('%s','%s','1')" % (g_ref['gid'],yearSelect))
                for i in range(4):
                    self.runQuery(query,read=0)
            
                urlStr = ("/grouppdp/%s/%s?e=Group PDP Initialised %s&ref=/grouppdp/%s/%s" % 
                         (groupName,yearSelect,yearSelect,groupName,yearSelect))
            
            raise cherrypy.HTTPRedirect(urlStr)
    
    @cherrypy.expose
    def personalpdp_initialise(self, **kws):
        if self.loggedin():
            userName = kws['user_name']
            yearSelect = kws['init_goals']
            
            if yearSelect == "":
                urlStr = "/personalpdp/%s?e=No Year Selected&ref=/personalpdp/%s" % (userName,userName)
                raise cherrypy.HTTPRedirect(urlStr)
            
            query = "SELECT uid FROM `person` where userName='%s'" % userName
            u_ref = self.runQuery(query,all=0)
            
            query = "SELECT uid FROM `person-pdp-data` WHERE (year='%s' AND uid='%s')" % (yearSelect,u_ref['uid'])
            result = self.runQuery(query,all=0)
            
            # Test if results are already in the database for current year
            if result:
                urlStr = ("/personalpdp/%s/%s?e=Goals already initialised for year %s&ref=/personalpdp/%s/%s" %
                            (userName,yearSelect,yearSelect,userName,yearSelect))
            else:
                # //TODO: pre load the relevent group goals
                query = ("SELECT * FROM `group-pdp-data` WHERE owners LIKE '%%\"%s\"%%' " % u_ref['uid'])
                resDict = self.runQuery(query,all=1)
                
                #err = json.dumps(len(resDict))
                if resDict:
                    for k in range(len(resDict)):
                        query = ("INSERT INTO `person-pdp-data` (uid,cycle,year,goal,align,reason,deadline,"
                             "course,courseOther) "
                             "VALUES ('%s','%s','%s','%s','%s','%s','%s','%s','%s')"
                             % (u_ref['uid'],resDict[k]['cycle'],resDict[k]['year'],resDict[k]['goalTitle'],
                                1,resDict[k]['description'],resDict[k]['deadline'],resDict[k]['course'],
                                resDict[k]['courseOther']))
                        self.runQuery(query,read=0)
                        #err = query
                
                
                
                # start out in cycle 1 of current year
                query = ("INSERT INTO `person-pdp-data` (uid,year,cycle) "
                         "VALUES ('%s','%s',1)" % (u_ref['uid'],yearSelect))
                if len(resDict) <= 4:
                # if more than 4 in resDict, don't need to populate blanks, only need min 4...
                    for i in range(4-len(resDict)):
                        #Insert 4 blank lines
                        self.runQuery(query,read=0)
                
                err = ''
                urlStr = ("/personalpdp/%s/%s?e=Person PDP Initialised %s... %s&ref=/personalpdp/%s/%s" %
                         (userName,yearSelect,yearSelect,err,userName,yearSelect))
                         
            
            raise cherrypy.HTTPRedirect(urlStr)
            
    @cherrypy.expose
    def personalpdp_changeyear(self,**kws):
        if self.loggedin():
            name = kws['user_name']
            
            if 'select_year' in kws:
                year = kws['select_year']
                urlStr = ("/personalpdp/%s/%s" % (name,year))
            else:
                urlStr = ("/personalpdp/%s?e=No Year Selected&ref=/personalpdp/%s" % (name,name))
            
            #if year == "":
            #    urlStr = ("/personalpdp/%s?e=No Year Selected&ref=/personalpdp/%s" % (name,name))
            #else:
            #    urlStr = ("/personalpdp/%s/%s" % (name,year))
                
            raise cherrypy.HTTPRedirect(urlStr)
    
    @cherrypy.expose
    def grouppdp_changeyear(self,**kws):
        if self.loggedin():
            
            name = kws['group_name']
            year = kws['year_goals']
            
            if year == "":
                urlStr = ("/grouppdp/%s?e=No Year Selected&ref=/grouppdp/%s" % (name,name))
            else:
                urlStr = ("/grouppdp/%s/%s" % (name,year))
                
            raise cherrypy.HTTPRedirect(urlStr)

    
    def getTraining(self):
        query = "SELECT tid,courseName FROM `training` WHERE available='1'"
        return self.runQuery(query,all=1)
    
    def getValues(self):
        query = "SELECT vid,value FROM `values` WHERE disabled IS NULL"
        return self.runQuery(query,all=1)
        
    def getCompliance(self):
        query = "SELECT cid,area FROM `compliance` WHERE disabled IS NULL"
        return self.runQuery(query,all=1)

    def getOptions(self,opt):
        query = "SELECT `oid`,`option` FROM `options` WHERE inUse='%s'" % opt
        return self.runQuery(query,all=1)
    
    def getGroupMembers(self,gid):
        query = ("SELECT uid,firstName,lastName,userName FROM `person` "
                 "WHERE groupName='%s'" % gid)
        return self.runQuery(query,all=1)
        
    def convertUid(self,plist):
        userlist = []
        #cherrypy.log.error(plist)
        
        if plist:
            uidStr = json.loads(plist)
            #for j in range(len(uidStr)):
            #cherrypy.log.error(uidStr)
            if type(uidStr) is list:
                uidStr = uidStr
            else:
                uidStr = [uidStr]
                
            for uid in uidStr:
                query = ("SELECT userName FROM `person` WHERE uid='%s'" % uid)
                result = self.runQuery(query,all=0)
                if result:
                    userlist.append(result['userName'])
                else:
                    userlist.append('ALL')
        return userlist

    def convertTraining(self, trainId):
        query = "SELECT courseName FROM `training` WHERE tid='%s'" % trainId
        result = self.runQuery(query,all=0)
        if result:
            if trainId == 1: #want to return None string not None type
                return 'None'
            else:
                return result['courseName']
        else:
            return 'None'
        
    def convertGroup(self,groupID):
        #pass
        query = "SELECT groupName FROM `group` WHERE gid='%s'" % groupID
        return self.runQuery(query,all=0)['groupName']
        
    def convertUser(self,userID):
        #pass
        query = "SELECT firstName,lastName FROM `person` WHERE uid='%s'" % userID
        result = self.runQuery(query,all=0)
        if result:
            return "%s %s" % (result['firstName'],result['lastName'])
        else:
            return "None"
    
    @cherrypy.expose
    def admin(self, **kws):
        
        t = jinja_env.get_template('admin.html')
        
        if self.loggedin():
            
            cookies = self.returnCookies()
            
            #userName = cookies['user']
            
            query = "SELECT uid FROM `person` WHERE userName='%s'" % cookies['user']
            uid = self.runQuery(query,all=0)['uid']
            
            if not self.isAdmin(uid):
                raise cherrypy.HTTPRedirect('/')
            
            #return json.dumps(uid)
            #title = cookies['title']
            query = "SELECT * FROM `person` WHERE uid='%s'" % uid
            user_dict = self.runQuery(query)[0]
            title = user_dict['position']
            userName = user_dict['userName']
            
            query = "SELECT * FROM `group` WHERE manager='%s'" % uid
            g_dict = self.runQuery(query)
            
            #check for the error flag and send to template            
            err = []
            if 'e' in kws:
                err.append(kws['e'])
                err.append(kws['ref'])
                if 'id' in kws:
                    err.append(kws['id'])
                else:
                    err.append('')
                
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

                    query = "SELECT userName,firstName,lastName FROM `person` WHERE groupName='%s'" % group_select
                    group_list = self.runQuery(query,all=1)
                                                
                    return t.render(sideDB=user_dict,groupDB=g_dict,error=err,
                            title=title,name=cookies['fname'],people_dict=result_people,
                            manager_dict=result_manager,group_dict=result_group,
                            groupName=grp,groupEnabled=ebl,groupManager=man,
                            groupList=group_list)
                    
                except:            
                    return t.render(sideDB=user_dict,groupDB=g_dict,error=err,
                            title=title,name=cookies['fname'],people_dict=result_people,
                            manager_dict=result_manager,group_dict=result_group,
                            groupName="",groupEnabled=0,groupManager="",
                            groupList="")
            
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
                #used for side bar details
                g_manager_name = self.convertUser(user_dict['manager'])
                g_name = self.convertGroup(user_dict['groupName'])
            
                return t.render(sideDB=user_dict,groupDB=g_dict,error=err,
                                title=title,name=cookies['fname'],manager_dict=result_manager,
                                gName=g_name,gManagerName=g_manager_name,
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
            
                raise cherrypy.HTTPRedirect('/admin?e=%s&ref=/admin' % error)
        
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
            raise cherrypy.HTTPRedirect('/admin?e=%s&ref=/admin' % error)

    def prettynames(self, uname_list):
        # Return a list of pretty names from a submitted username list
        pass

    @cherrypy.expose
    def groups(self):
        if self.loggedin():
            
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

    #Check if the user is a manager
    def isManager(self,userID):
        query = "SELECT isManager FROM `person` WHERE uid='%s'" % userID
        result = self.runQuery(query,all=0)
        
        if result['isManager']:
            return True
        else:
            return False
            
    #Check if the user is an Admin
    def isAdmin(self,userID):
        query = "SELECT isAdmin FROM `person` WHERE uid='%s'" % userID
        result = self.runQuery(query,all=0)
        
        if result['isAdmin']:
            return True
        else:
            return False
        
    
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
                
    
    @cherrypy.expose
    #general db query helper
    def runQuery(self,query,all=1,read=1):
        #Not very efficient, but avoids "db gone away' errors
        db = MySQLdb.connect(host=values['DB']['host'],user=values['DB']['dbuser'],
                passwd=values['DB']['password'],db=values['DB']['database'],
                cursorclass=MySQLdb.cursors.DictCursor)
        #open new cursor
        cur_run = db.cursor()
                    
        try:
            cur_run.execute(query)
            db.commit()
            #return cur_run.fetchall()
            if read:
                if all:
                    result = cur_run.fetchall()
                    db.close()
                    return result
                else:
                    result = cur_run.fetchone()
                    db.close()
                    return result
            else:
                return True
        except:
            db.rollback()
            db.close()
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
                raise cherrypy.HTTPRedirect('/admin?e=No group name selected')
            
            #Check if already in the DB
            if self.isGroupDB(g_name):
                query = ("UPDATE `group` SET groupName='%s',enabled='%s',urlName='%s',manager='%s' WHERE groupName='%s'" 
                        % (g_name,g_enable,g_url,g_man,g_name))
            #Else update the group already in the DB
            else:
                query = ("INSERT INTO `group` (groupName,enabled,urlName,manager) VALUES ('%s','%s','%s','%s')" 
                        % (g_name,g_enable,g_url,g_man))
                
            self.runQuery(query,read=0)
            
            urlStr = '/admin?e=Group Data Updated for %s&ref=/admin' % g_name
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
                raise cherrypy.HTTPRedirect('/admin?e=noUser&ref=/admin')
            

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

            urlStr = '/admin?e=User Data Updated for %s&ref=/admin'%p_uname
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
         'tools.sessions.on': True, # RAM is default storage type
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
cherrypy.tree.mount(Help(), '/help', config=config)
cherrypy.engine.autoreload.on = True
cherrypy.engine.autoreload.frequency = 5
cherrypy.engine.autoreload.files.add('app_pdp.py') #remove for production
cherrypy.engine.start()

