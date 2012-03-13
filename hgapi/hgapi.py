# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, with_statement
from subprocess import Popen, STDOUT, PIPE
from collections import deque
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
        if not self.parents:
            self.parents = [int(self.rev)-1]
        else:
            self.parents = [int(p.split(':')[0]) for p in self.parents.split()]

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

    def __getitem__(self, rev):
        """Get a Revision object for the revision identifed by rev"""
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
        self.hg_command("commit", "-m", message, close, 
                        userspec, *files)

    def hg_log(self, identifier=None, limit=None, template=None, **kwargs):
        """Get repositiory log. 
        Output from this method can be processed with the Changeset class.
        
        example:
        changesets = Changeset(repo.hg_log(<node_range>))
        for entry in changeset:
            print(entry.changeset, entry.branch, entry.tag, entry.parent, entry.user, entry.date, entry.summary)
        """
        cmds = ["log"]
        if identifier: cmds += ['-r', str(identifier)]
        if limit: cmds += ['-l', str(limit)]
        if template: cmds += ['--template', str(template)]
        if kwargs:
            for key in kwargs:
                cmds += [key, kwargs[key]]
        return self.hg_command(*cmds)
        
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
        
    rev_log_tpl = '\{"node":"{node|short}","rev":"{rev}","author":"{author|urlescape}","branch":"{branch}", "parents":"{parents}","date":"{date|isodate}","tags":"{tags}","desc":"{desc|urlescape}"}'        

    def revision(self, identifier):
        """Get the identified revision as a Revision object"""
        out = self.hg_log(identifier=str(identifier), 
                          template=self.rev_log_tpl)
        
        return Revision(out)

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


class Changeset(object):
    """Parses the hg log output and breaks it up into a list of entries and access to their data"""
    all_changeset_instances = [] # permanent class var list of changeset instances 
    queue = [] # temp list for iteration
    processing_log = False

    def __init__(self, log=None):
        """Takes hg_log() output as parameter and processes the logs into a list of instances for each entry
        to be iterated through.

        example:
        changesets = Changeset(repo.hg_log(<node_range>))
        for entry in changeset:
            print(entry.changeset, entry.branch, entry.tag, entry.parent, entry.user, entry.date, entry.summary)
        """

        if not log and not self.__class__.processing_log:
            raise TypeError(' __init__() requires log output as parameter')

        self.changeset = 'Undefined'
        self.branch = None
        self.tag = None
        self.parent = None
        self.user = None
        self.date = None
        self.summary = None

        if log:
            self = Changeset.process_log(log)

    def __len__(self):
        return len(self.__class__.all_changeset_instances)

    def __nonzero__(self):
        return len(self.__class__.all_changeset_instances)

    def __iter__(self):
        if not self.__class__.queue:
            # if queue is empty, reset it to start the iteration fresh
            self.__class__.queue = deque(self.__class__.all_changeset_instances)
        return self

    def next(self):
        """returns the next changeset instance on the stack"""
        if self.__class__.queue:
           return self.__class__.queue.popleft()
        else:
           raise StopIteration

    @classmethod
    def process_log(cls, log):
        """Processes the log output from Repo.hg_log, and creates an internal stack of instances of type Changeset. 
           To be iterated through by the user. Returns first on stack to be used as the return instance for the caller.
        """
        first_instance = None
        cls.processing_log = True

        for block in log.split("\n\n"):
            block = block + "\n"
            regexp = re.compile(r"changeset:\s+(?P<changeset>[\d]+:[\da-zA-Z]+)\n"
                                r"(branch:\s+(?P<branch>[a-zA-z\d]+)\n)?"
                                r"(tag:\s+(?P<tag>[a-zA-z\d]+)\n)?"
                                r"(parent:\s+(?P<parent>[\d]+:[\da-zA-Z]+)\n)?"
                                r"user:\s+(?P<user>[\da-zA-Z]+)\n"
                                r"date:\s+(?P<date>[\s\S]+)\n"
                                r"summary:\s+(?P<summary>[\s\S]+)\n"
                               )
            result = regexp.search(block)
            if result:
                instance = Changeset()
                instance.changeset = result.group('changeset')
                instance.branch = result.group('branch')
                instance.tag = result.group('tag')
                instance.parent = result.group('parent')
                instance.user = result.group('user')
                instance.date = result.group('date')
                instance.summary = result.group('summary')
                if not first_instance:
                    first_instance = instance
                cls.all_changeset_instances.append(instance)

        cls.processing_log = False
        return first_instance

