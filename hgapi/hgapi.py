# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, with_statement
from subprocess import Popen, STDOUT, PIPE
try:
    from urllib import unquote
except: #python 3
    from urllib.parse import unquote
import re
import os.path
try:
    import json #for reading logs
except:
    import simplejson as json


class Revision(object):
    """A representation of a revision.
    Available fields are::

      node, rev, author, branch, parents, date, tags, desc

    A Revision object is equal to any other object with the same value for node
    """
    def __init__(self, json_log):
        """Create a Revision object from a JSON representation"""
        rev = json.loads(json_log)
        
        for key in rev.keys():
            self.__setattr__(key, unquote(rev[key]))
        self.rev = int(self.rev)
        if not self.branch: self.branch='default'
        if not self.parents:
            self.parents = [int(self.rev)-1]
        else:
            self.parents = [int(p.split(':')[0]) for p in self.parents.split()]

    def __iter__(self):
        return self

    def __eq__(self, other):
        """Returns true if self.node == other.node"""
        return self.node == other.node

class Repo(object):
    """A representation of a Mercurial repository"""
    def __init__(self, path, user=None):
        """Create a Repo object from the repository at path"""
        self.path = path
        self.cfg = False
        self.user = user
 
    def __getitem__(self, rev=slice(0, 'tip')):
        """Get a Revision object for the revision identifed by rev
           rev can be a range (6c31a9f7be7ac58686f0610dd3c4ba375db2472c:tip)
           a single changeset id
           or it can be left blank to indicate the entire history
        """
        if isinstance(rev, slice):
            return self.revisions(rev)
        return self.revision(rev)

    def hg_command(self, *args):
        """Run a hg command in path and return the result.
        Throws on error."""    
        proc = Popen(["hg", "--cwd", self.path, "--encoding", "UTF-8"] + list(args), stdout=PIPE, stderr=PIPE)

        out, err = [x.decode("utf-8") for x in  proc.communicate()]

        if proc.returncode:
            cmd = (" ".join(["hg", "--cwd", self.path] + list(args)))
            raise Exception("Error running %s:\n\tErr: %s\n\tOut: %s\n\tExit: %s" 
                            % (cmd,err,out,proc.returncode))
        return out

    def hg_init(self):
        """Initialize a new repo"""
        self.hg_command("init")

    def hg_id(self):
        """Get the output of the hg id command (truncated node)"""
        res = self.hg_command("id", "-i")
        return res.strip("\n +")
        
    def hg_rev(self):
        """Get the revision number of the current revision"""
        res = self.hg_command("id", "-n")
        str_rev = res.strip("\n +")
        return int(str_rev)

    def hg_add(self, filepath):
        """Add a file to the repo"""
        self.hg_command("add", filepath)

    def hg_remove(self, filepath):
        """Remove a file from the repo"""
        self.hg_command("remove", filepath)

    def hg_update(self, reference, clean=False):
        """Update to the revision indetified by reference"""
        cmd = ["update", str(reference)]
        if clean: cmd.append("--clean")
        self.hg_command(*cmd)

    def hg_heads(self):
        """Gets a list with the node id:s of all open heads"""
        res = self.hg_command("heads","--template", "{node}\n")
        return [head for head in res.split("\n") if head]

    def hg_merge(self, reference):
        """Merge reference to current"""
        self.hg_command("merge", reference)
        
    def hg_revert(self, all=False, *files):
        """Revert repository"""
        
        if all:
            cmd = ["revert", "--all"]
        else:
            cmd = ["revert"] + list(files)
        self.hg_command(*cmd)

    def hg_node(self):
        """Get the full node id of the current revision"""
        res = self.hg_command("log", "-r", self.hg_id(), "--template", "{node}")
        return res.strip()

    def hg_commit(self, message, user=None, files=[], close_branch=False):
        """Commit changes to the repository."""
        userspec = "-u" + user if user else "-u" + self.user if self.user else ""
        close = "--close-branch" if close_branch else ""
        args = [close, userspec] + files
        # don't send a "" arg for userspec or close, which HG will
        # consider the files arg, committing all files instead of what
        # was passed in files kwarg
        args = [arg for arg in args if arg]
        self.hg_command("commit", "-m", message, *args)

    def hg_log(self, identifier=None, limit=None, template=None, **kwargs):
        """Get repositiory log."""
        cmds = ["log"]
        if identifier: cmds += ['-r', str(identifier)]
        if limit: cmds += ['-l', str(limit)]
        if template: cmds += ['--template', str(template)]
        if kwargs:
            for key in kwargs:
                cmds += [key, kwargs[key]]
        return self.hg_command(*cmds)

    def hg_branch(self, branch_name=None):
        """ Creates a branch of branch_name isn't None
            If not, returns the current branch name.
        """
        args = []
        if branch_name:
            args.append(branch_name)
        branch = self.hg_command("branch", *args)
        return branch.strip()

    def get_branches(self):
        """ Returns a list of branches from the repo, including versions """
        branches = self.hg_command("branches")
        branch_list = branches.strip().split("\n")
        values = []
        for branch in branch_list:
            b = branch.partition(" ")
            if not b:
                continue
            name = b[0].strip()
            version = b[-1].strip()
            values.append({'name':name, 'version':version})
        return values

    def get_branch_names(self):
        """ Returns a list of branch names from the repo. """
        branches = self.hg_command("branches")
        branch_list = branches.strip().split("\n")
        values = []
        for branch in branch_list:
            b = branch.partition(" ")
            if not b:
                continue
            name = b[0]
            if name:
                name = name.strip()
                values.append(name)
        return values

    def hg_status(self, empty=False):
        """Get repository status.
        Returns a dict containing a *change char* -> *file list* mapping, where 
        change char is in::

         A, M, R, !, ?

        Example - added one.txt, modified a_folder/two.txt and three.txt::

         {'A': ['one.txt'], 'M': ['a_folder/two.txt', 'three.txt'],
         '!': [], '?': [], 'R': []}

        If empty is set to non-False value, don't add empty lists
        """
        cmds = ['status']
        out = self.hg_command(*cmds).strip()
        #default empty set
        if empty:
            changes = {}
        else:
            changes = {'A': [], 'M': [], '!': [], '?': [], 'R': []}
        if not out: return changes
        lines = out.split("\n")
        status_split = re.compile("^(.) (.*)$")

        for change, path in [status_split.match(x).groups() for x in lines]:
            changes.setdefault(change, []).append(path)
        return changes
        
    rev_log_tpl = '\{"node":"{node|short}","rev":"{rev}","author":"{author|urlescape}","branch":"{branches}","parents":"{parents}","date":"{date|isodate}","tags":"{tags}","desc":"{desc|urlescape}\"}\n'

    def revision(self, identifier):
        """Get the identified revision as a Revision object"""

        out = self.hg_log(identifier=str(identifier), 
                                     template=self.rev_log_tpl)
                
        return Revision(out)   

    def revisions(self, slice_):
        """Retruns a list of Revision objects for the given slice"""
        out = self.hg_log(identifier=":".join([str(x)for x in (slice_.start, slice_.stop)]), 
                                             template=self.rev_log_tpl)
                        
        revs = []
        for entry in out.split('\n')[:-1]:
            revs.append(Revision(entry))

        return revs      
    
    def read_config(self):
        """Read the configuration as seen with 'hg showconfig'
        Is called by __init__ - only needs to be called explicitly
        to reflect changes made since instantiation"""
        res = self.hg_command("showconfig")
        cfg = {}
        for row in res.split("\n"):
            section, ign, value = row.partition("=")
            main, ign, sub = section.partition(".")
            sect_cfg = cfg.setdefault(main, {})
            sect_cfg[sub] = value.strip()
        self.cfg = cfg
        return cfg

    def config(self, section, key):
        """Return the value of a configuration variable"""
        if not self.cfg: 
            self.cfg = self.read_config()
        return self.cfg.get(section, {}).get(key, None)
    
    def configbool(self, section, key):
        """Return a config value as a boolean value.
        Empty values, the string 'false' (any capitalization),
        and '0' are considered False, anything else True"""
        if not self.cfg: 
            self.cfg = self.read_config()
        value = self.cfg.get(section, {}).get(key, None)
        if not value: 
            return False
        if (value == "0" 
            or value.upper() == "FALSE"
            or value.upper() == "None"): 
            return False
        return True

    def configlist(self, section, key):
        """Return a config value as a list; will try to create a list
        delimited by commas, or whitespace if no commas are present"""
        if not self.cfg: 
            self.cfg = self.read_config()
        value = self.cfg.get(section, {}).get(key, None)
        if not value: 
            return []
        if value.count(","):
            return value.split(",")
        else:
            return value.split()

