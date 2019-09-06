#!/usr/bin/env python

import os
import shutil
import re
import tempfile
import copy

import xmlrpclib as x

from jinja2 import Environment
from jinja2.loaders import FileSystemLoader



class FreeRadiusManager:
	
	
	def __init__(self):
		
		self.radius_path="/etc/freeradius/3.0/"
		self.templates_path="/usr/share/n4d/templates/n4d-freeradius/"
		self.groups_file=self.radius_path + "/mods-config/files/authorize.lliurex_groups"
		
		self.groups={}
		self.diversions={}
		
		self.variable_list=["LDAP_BASE_DN","INTERNAL_NETWORK","INTERNAL_MASK"]
		
		self.diversions["/etc/freeradius/3.0/clients.conf"]="/etc/freeradius/3.0/clients.conf.diverted"
		#self.diversions["/etc/freeradius/3.0/eap.conf"]="/etc/freeradius/3.0/eap.conf.diverted"
		self.diversions["/etc/freeradius/3.0/mods-config/files/authorize"]="/etc/freeradius/3.0/mods-config/files/authorize.diverted"
		self.diversions["/etc/freeradius/3.0/radiusd.conf"]="/etc/freeradius/3.0/radiusd.conf.diverted"
		
		self.diversions["/etc/freeradius/3.0/mods-available/ldap"]="/etc/freeradius/3.0/mods-available/ldap.diverted"
		self.diversions["/etc/freeradius/3.0/mods-available/mschap"]="/etc/freeradius/3.0/mods-available/mschap.diverted"
		
		self.diversions["/etc/freeradius/3.0/sites-available/default"]="/etc/freeradius/3.0/sites-available/default.diverted"
		self.diversions["/etc/freeradius/3.0/sites-available/inner-tunnel"]="/etc/freeradius/3.0/sites-available/inner-tunnel.diverted"
		
		
	#def init
	
	def startup(self,options):
	
		self.variable=copy.deepcopy(objects["VariablesManager"].get_variable("FREERADIUS"))
		
		if self.variable==None:
			
			self.variable={}
			self.variable["configured"]=False
			self.variable["groups_filter"]={}
			self.variable["groups_filter"]["enabled"]=False
			self.variable["groups_filter"]["groups"]={}
			self.variable["groups_filter"]["default_auth"]=None
			
			try:
				objects["VariablesManager"].add_variable("FREERADIUS",copy.deepcopy(self.variable),"","Freeradius service variable","n4d-freeradius")
			except:
				# If this fails, something is horribly wrong and we have bigger problems than this variable not being saved
				# Hopefully we'll be able to do it later, anyway
				pass

		if self.variable["groups_filter"]["enabled"]:
			groups=self.parse_groups_file()
			if groups != self.variable["groups_filter"]["groups"]:
				self.variable["groups_filter"]["groups"]=groups
				self.save_variable()
		
	#def startup

	def is_configured(self):

		return self.variable["configured"]

	#def is_configured


	def parse_groups_file(self):
		
		group_pattern='^DEFAULT\s+Ldap-Group\s*==\s*"(\w+)"\s*(,\s*Auth-Type\s*:=\s*\w+\s*)?$'
		groups={}
		
		if os.path.exists(self.groups_file):
			
			f=open(self.groups_file)
			for line in f.readlines():
				ret=re.match(group_pattern,line)
				if ret!=None:
					group,auth_type=ret.groups()
					groups[group]=auth_type
					
			f.close()
		
		return groups
		
	#def parse_groups_file


	def get_allowed_groups(self):

		groups=self.parse_groups_file()
		if len(groups) < 1:
			groups=self.variable["groups_filter"]["groups"]
		return {"status":True,"msg":groups.keys()}

	#def get_allowed_groups
	
	
	def generate_groups_file(self,groups=None):
		
		header = "# FILE GENERATED BY n4d-freeradius PLUGIN\n\n"
		final_rule="DEFAULT Auth-Type := Reject\n\n"
		
		group_skel='DEFAULT Ldap-Group == "%s"'
		extra_auth=", Auth-Type := EAP"
				
		if not groups:
			groups=self.variable["groups_filter"]["groups"]
			
		fd,tmpfile=tempfile.mkstemp()
		f=open(tmpfile,"w")
		f.write(header)
		for group in groups:
			f.write(group_skel%group)
			if groups[group]!=None:
				f.write(extra_auth)
			f.write("\n")
	
		f.write("\n")		
		f.write(final_rule)
		f.close()
		os.close(fd)
		
		shutil.copy(tmpfile,self.groups_file)
		self.fix_perms(self.groups_file)
		
		return True
		
	#def generate_groups_file
	
	
	def clean_groups_file(self):
		
		f=open(self.groups_file,"w")
		f.write("# FILE GENERATED BY n4d-freeradius PLUGIN\n\n")
		f.close()
		
	#def clean_groups_file
	
	
	def set_filter_default_auth(self,auth_type=None):
		
		if not self.variable["groups_filter"]["enabled"]:
			return {"msg":False,"status":"Filter not enabled"}
		
		self.variable["groups_filter"]["default_auth"]=auth_type
		
		for group in self.variable["groups_filter"]["groups"]:
			self.variable["groups_filter"]["groups"][group]=auth_type
				
		self.generate_groups_file()
		self.restart_service()
		
		self.save_variable()
		
		return {"status":True,"msg":"auth configured"}
		
	#def set_filter_default_auth
	
	
	def add_group_to_filter(self,group,extra_auth=None):
		
		if not self.variable["groups_filter"]["enabled"]:
			return {"status":False,"msg":"Filter not enabled"}
			
		if extra_auth==None:
			extra_auth=self.variable["groups_filter"]["default_auth"]
		
		groups=self.parse_groups_file()
		
		if group not in groups or groups[group]!=extra_auth:
			self.variable["groups_filter"]["groups"][group]=extra_auth
			
		self.generate_groups_file()
		self.save_variable()
		self.restart_service()
		
		return {"status":True,"msg":"Group added"}
		
		
	#def add_group_to_filter
	
	
	def remove_group_from_filter(self,group):
		
		if not self.variable["groups_filter"]["enabled"]:
			return {"status":False,"msg":"Filter not enabled"}
		
		groups=self.parse_groups_file()
		
		if group in groups:
			groups.pop(group)
			self.variable["groups_filter"]["groups"]=groups
			
		self.generate_groups_file()
		self.restart_service()
		self.save_variable()
		
		return {"status":True, "msg": "Group removed"}
		
	#def remove_group_from_filter
	
	
	def enable_group_filtering(self):
		
		self.variable["groups_filter"]["enabled"]=True
		self.generate_groups_file()
		
		self.save_variable()
		self.restart_service()
		
		return {"status":True,"msg":""}
		
	#def enable_filtering
	
	
	def disable_group_filtering(self):
		
		# get groups currently written in case user did it manually
		groups=self.parse_groups_file()
		# save groups in local variable only if it has content
		# rely on variable groups value if it doesn't
		if len(groups)>0:
			self.variable["groups_filter"]["groups"]=groups
		
		self.clean_groups_file()
		self.variable["groups_filter"]["enabled"]=False
		
		self.save_variable()
		self.restart_service()
		
		return {"status":True,"msg":""}
		
	#def empty_groups_file
	
	
	def save_variable(self):
		
		objects["VariablesManager"].set_variable("FREERADIUS",copy.deepcopy(self.variable))
		
	#def save_variable
	
	def restart_service(self):
		
		os.system("systemctl restart freeradius")
		
	#def restart_service
		
	
	def render_templates(self,server,radius_secret,ldap_user,ldap_pwd,router_ip):
		
	
		vars=objects["VariablesManager"].get_variable_list(self.variable_list)
		
		vars["RADIUS_SECRET"]=radius_secret
		vars["LDAP_USER"]=ldap_user
		vars["LDAP_PASSWORD"]=ldap_pwd
		vars["SERVER"]=server
		vars["ROUTER_IP"]=router_ip
		
		env = Environment(loader=FileSystemLoader(self.templates_path))

		template=env.get_template("clients.conf")
		str_template=template.render(vars).encode("utf-8")
		clients_str=str_template
		
		f=open(self.templates_path+"mods-available/ldap")
		lines=f.readlines()
		f.close()
		 
		str_template=""
		
		for line in lines:
			
			if "%%LDAP_USER%%" in line:
				line=line.replace("%%LDAP_USER%%",vars["LDAP_USER"])

			if "%%LDAP_PASSWORD%%" in line:
				line=line.replace("%%LDAP_PASSWORD%%",vars["LDAP_PASSWORD"])

			if "%%LDAP_BASE_DN%%" in line:
				line=line.replace("%%LDAP_BASE_DN%%",vars["LDAP_BASE_DN"])

			if "%%SERVER%%" in line:
				line=line.replace("%%SERVER%%",vars["SERVER"])
				
			str_template+=line

		
		ldap_str=str_template
		
		return (clients_str,ldap_str)
	
	#def render_template

	
	def install_conf_files(self,server,radius_secret,ldap_user,ldap_pwd,router_ip):
		
		try:
		
			clients_str,ldap_str=self.render_templates(server,radius_secret,ldap_user,ldap_pwd,router_ip)
			
			if not os.path.exists(self.radius_path):
				os.makedirs(self.radius_path)
			
			# clients.conf
			
			f=open(self.radius_path+"clients.conf.lliurex","w")
			f.write(clients_str)
			f.close()
			
			self.fix_perms(self.radius_path+"clients.conf.lliurex")
			
			
			# modules/ldap
			
			if not os.path.exists(self.radius_path+"mods-available"):
				os.makedirs(self.radius_path+"mods-available/")
			
			
			f=open(self.radius_path+"mods-available/ldap.lliurex","w")
			f.write(ldap_str)
			f.close()
			self.fix_perms(self.radius_path+"/mods-available/ldap.lliurex")
			
						
			if not os.path.exists(self.radius_path+"mods-enabled/ldap"):
				os.symlink(self.radius_path+"mods-available/ldap",self.radius_path+"mods-enabled/ldap")
			
			# default
			if not os.path.exists(self.radius_path+"sites-available"):
				os.makedirs(self.radius_path+"sites-available")
			
			shutil.copy(self.templates_path+"sites-available/default",self.radius_path+"sites-available/default.lliurex")
			self.fix_perms(self.radius_path+"sites-available/default.lliurex")
			
			# inner-tunnel
			shutil.copy(self.templates_path+"sites-available/inner-tunnel",self.radius_path+"sites-available/inner-tunnel.lliurex")
			self.fix_perms(self.radius_path+"sites-available/inner-tunnel.lliurex")
			
			# radiusd.conf
			shutil.copy(self.templates_path+"radiusd.conf",self.radius_path+"radiusd.conf.lliurex")
			self.fix_perms(self.radius_path+"radiusd.conf.lliurex")
			
			# eap.conf
			#shutil.copy(self.templates_path+"eap.conf",self.radius_path+"eap.conf.lliurex")
			#self.fix_perms(self.radius_path+"eap.conf.lliurex")
			
			# authorize
			shutil.copy(self.templates_path+"/mods-config/files/authorize",self.radius_path+"/mods-config/files/authorize.lliurex")
			self.fix_perms(self.radius_path+"/mods-config/files/authorize.lliurex")
			
			# user.lliurex_groups
			shutil.copy(self.templates_path+"/mods-config/files/authorize.lliurex_groups",self.radius_path+"/mods-config/files")
			self.fix_perms(self.radius_path+"/mods-config/files/authorize.lliurex_groups")
			
			# modules/mschap
			shutil.copy(self.templates_path+"/mods-available/mschap",self.radius_path+"mods-available/mschap.lliurex")
			self.fix_perms(self.radius_path+"/mods-available/mschap.lliurex")
			if not os.path.exists(self.radius_path+"mods-enabled/mschap"):
				os.symlink(self.radius_path+"mods-available/mschap",self.radius_path+"mods-enabled/mschap")
			
			self.enable_diversions()		
	
			os.system("systemctl restart freeradius")
			
			self.variable["groups_filter"]["enabled"]=False
			self.variable["configured"]=True
			
			self.save_variable()
			
			return {"status":True,"msg":str(True)}
			
		except Exception as e:
			
			return {"status":False,"msg":str(e)}
			
		
	#def install_conf_files
	
	
	def fix_perms(self,f):
		
		os.system("chown freerad:freerad %s"%f)
		os.system("chmod 640 %s"%f)		
		
	#def fix_perms
	

	def enable_diversions(self):

		for original_file in self.diversions:

			lliurex_file=original_file+".lliurex"
			
			if not os.path.exists(self.diversions[original_file]):
				command="dpkg-divert --add --package n4d-freeradius --rename --divert '%s' '%s'"%(self.diversions[original_file],original_file)
				os.system(command)
				
			if not os.path.islink(original_file):
				os.symlink(lliurex_file, original_file)

	#def enable_diversions


	def disable_diversions(self):

		pass

	#def disable_diversions
	
	


	
#class RadiusManager

if __name__=="__main__":
	
	r=RadiusManager()
	r.install_conf_files("server","myradius1","cn=roadmin...","2","")
