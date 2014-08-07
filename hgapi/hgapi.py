# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals, with_statement
from subprocess import Popen, PIPE

try:
    from urllib import unquote
except ImportError:  # python 3
    from urllib.parse import unquote

import re
import os
import sys

try:
    import json  # for reading logs
except ImportError:
    import simplejson as json


class HgException(Exception):
    """
        Exception class allowing a exit_code parameter and member
        to be used when calling Mercurial to return exit code.
    """

    def __init__(self, msg, exit_code=None):
        super(HgException, self).__init__(msg)
        self.exit_code = exit_code


class Revision(object):
    """
        A representation of a revision.
        Available fields are::

            node, rev, author, branch, parents, date, tags, desc

        A Revision object is equal to any other object with the
        same value for node.
    """

    def __init__(self, json_log):
        """Create a Revision object from a JSON representation"""
        rev = json.loads(json_log)

        for key in rev.keys():
            if sys.version_info.major < 3:
                _value = unquote(rev[key].encode("ascii")).decode("utf-8")
            else:
                _value = unquote(rev[key])
            self.__setattr__(key, _value)
        self.rev = int(self.rev)
        if not self.branch:
            self.branch = 'default'
        if not self.parents:
            self.parents = [int(self.rev) - 1]
        else:
            self.parents = [int(p.split(':')[0]) for p in self.parents.split()]

    def __iter__(self):
        return self

    def __eq__(self, other):
        """Returns true if self.node == other.node."""
        return self.node == other.node


class Repo(object):
    """A representation of a Mercurial repository."""

    def __init__(self, path, user=None):
        """Create a Repo object from the repository at path."""
        self.path = path
        self.cfg = False
        self.user = user

    _env = os.environ
    _env[str('LANG')] = str('en_US')

    @classmethod
    def command(cls, path, env, *args):
        """
            Run a hg command in path and return the result.

            Raise on error.
        """
        cmd = ["hg", "--cwd", path, "--encoding", "UTF-8"] + list(args)
        proc = Popen(cmd,
                     stdout=PIPE, stderr=PIPE, env=env)

        out, err = [x.decode("utf-8") for x in proc.communicate()]

        if proc.returncode:
            cmd = " ".join(cmd)
            raise HgException("Error running %s:\n"
                              "\tErr: %s\n"
                              "\tOut: %s\n"
                              "\tExit: %s"
                              % (cmd, err, out, proc.returncode),
                              exit_code=proc.returncode)

        return out

    def __getitem__(self, rev=slice(0, 'tip')):
        """
            Get a Revision object for the revision identified by rev.

            rev can be a range (6c31a9f7be7ac58686f0610dd3c4ba375db2472c:tip)
            a single changeset id or it can be left blank to indicate
            the entire history.
        """
        if isinstance(rev, slice):
            return self.revisions(rev)
        return self.revision(rev)

    def hg_command(self, *args):
        """Run a hg command."""
        return Repo.command(self.path, self._env, *args)

    def hg_init(self):
        """Initialize a new repo."""
        self.hg_command("init")

    def hg_id(self):
        """Get the output of the hg id command (truncated node)."""
        res = self.hg_command("id", "-i")
        return res.strip("\n +")

    def hg_rev(self):
        """Get the revision number of the current revision."""
        res = self.hg_command("id", "-n")
        str_rev = res.strip("\n +")
        return int(str_rev)

    def hg_add(self, filepath=None):
        """
            Add a file to the repo.

            when no filepath is given, all files are added to the repo.
        """
        if filepath is None:
            self.hg_command("add")
        else:
            self.hg_command("add", filepath)

    def hg_addremove(self, filepath=None):
        """
            Add a file to the repo.

            When no filepath is given, all files are added and removed
            to and respectively from the repo.
        """
        if filepath is None:
            self.hg_command("addremove")
        else:
            self.hg_command("addremove", filepath)

    def hg_remove(self, filepath):
        """Remove a file from the repo"""
        self.hg_command("remove", filepath)

    def hg_move(self, source, destination):
        """Move a file in the repo."""
        self.hg_command("move", source, destination)

    def hg_rename(self, source, destination):
        """
            Move a file in the repo.
            This is hg_more.
        """
        return self.hg_move(source, destination)

    def hg_update(self, reference, clean=False):
        """Update to the revision identified by reference."""
        cmd = ["update", str(reference)]
        if clean:
            cmd.append("--clean")
        self.hg_command(*cmd)

    def hg_tag(self, *tags, **kwargs):
        """
            Add one or more tags to the current revision.

            Add one or more tags to the current revision, or revision given by
            passing 'rev' as a keyword argument::

          >>> repo.hg_tag('mytag', rev=3)
        """
        rev = kwargs.get('rev')
        cmd = ['tag'] + list(tags)
        if rev:
            cmd += ['-r', str(rev)]
        self.hg_command(*cmd)

    def hg_tags(self):
        """
            Get all tags from the repo.

            Returns a dict containing tag: shortnode mapping
        """
        cmd = ['tags']
        output = self.hg_command(*cmd)
        res = {}
        reg_expr = "(?P<tag>.+\S)\s+(?P<rev>\d+):(?P<changeset>\w+)"
        pattern = re.compile(reg_expr)
        for row in output.strip().split('\n'):
            match = pattern.match(row)
            tag = match.group("tag")
            changeset = match.group("changeset")
            res[tag] = changeset
        return res

    def hg_heads(self, short=False):
        """
            Get a list with the node identifiers of all open heads.
            If short is given and is not False, return the short
            form of the node id.
        """
        template = "{node}\n" if not short else "{node|short}\n"
        res = self.hg_command("heads", "--template", template)
        return [head for head in res.split("\n") if head]

    def hg_merge(self, reference, preview=False):
        """
            Merge reference to current.

            With 'preview' set to True get a list of revision numbers
            containing all revisions that would have been merged.
        """
        if not preview:
            return self.hg_command("merge", reference)
        else:
            revno_re = re.compile('^changeset: (\d+):\w+$')
            out = self.hg_command("merge", "-P", reference)
            revs = []
            for row in out:
                match = revno_re.match(row)
                if match:
                    revs.append(match.group(1))
            return revs

    def hg_revert(self, all=False, *files):
        """Revert repository."""
        if all:
            cmd = ["revert", "--all"]
        else:
            cmd = ["revert"] + list(files)
        self.hg_command(*cmd)

    def hg_node(self):
        """Get the full node id of the current revision."""
        res = self.hg_command("log", "-r", self.hg_id(),
                              "--template", "{node}")
        return res.strip()

    def hg_commit(self, message, user=None, date=None, files=[],
                  close_branch=False):
        """Commit changes to the repository."""
        userspec = "-u" + user if user \
            else "-u" + self.user if self.user else ""
        datespec = "-d" + date if date else ""
        close = "--close-branch" if close_branch else ""
        args = [close, userspec, datespec] + files
        # don't send a "" arg for userspec or close, which HG will
        # consider the files arg, committing all files instead of what
        # was passed in files kwarg
        args = [arg for arg in args if arg]
        self.hg_command("commit", "-m", message, *args)

    def hg_push(self, destination=None):
        """Push changes from this repo."""
        if destination is None:
            self.hg_command("push")
        else:
            self.hg_command("push", destination)

    def hg_pull(self, source=None):
        """Pull changes to this repo."""
        if source is None:
            self.hg_command("pull")
        else:
            self.hg_command("pull", source)

    def hg_paths(self):
        """Get remote repositories."""
        remotes = self.hg_command("paths").split("\n")
        remotes_list = [line.split(" = ") for line in remotes if line != ""]

        return dict(remotes_list)

    def __get_remote_changes(self, command, remote):
        if remote not in self.hg_paths().keys():
            raise HgException("No such remote repository")

        try:
            result = self.hg_command(
                command,
                remote,
                "--template",
                self.rev_log_tpl
            ).split("\n")
        except HgException:
            return []

        changesets = [change for change in result if change.startswith("{")]
        return list(map(lambda revision: Revision(revision), changesets))

    def hg_outgoing(self, remote="default"):
        """Get outgoing changesets for a certain remote."""
        return self.__get_remote_changes("outgoing", remote)

    def hg_incoming(self, remote="default"):
        """Get incoming changesets for a certain remote."""
        return self.__get_remote_changes("incoming", remote)

    def hg_log(self, identifier=None, limit=None, template=None,
               branch=None, **kwargs):
        """Get repositiory log."""
        cmds = ["log"]
        if identifier:
            cmds += ['-r', str(identifier)]
        if branch:
            cmds += ['-b', str(branch)]
        if limit:
            cmds += ['-l', str(limit)]
        if template:
            cmds += ['--template', str(template)]
        if kwargs:
            for key in kwargs:
                cmds += [key, kwargs[key]]
        log = self.hg_command(*cmds)
        return log

    def hg_branch(self, branch_name=None):
        """
            Create a branch or get a branch name.

            If branch_name is not None, the branch is created.
            Otherwise the current branch name is returned.
        """
        args = []
        if branch_name:
            args.append(branch_name)
        branch = self.hg_command("branch", *args)
        return branch.strip()

    def get_branches(self):
        """
            Returns a list of branches from the repo, including versions.

            If get_active_only is True, then only return active branches.
        """
        branches = self.hg_command("branches")
        branch_list = branches.strip().split("\n")
        values = []
        for branch in branch_list:
            b = re.split('(\d+:[A-Za-z0-9]+)', branch)
            if not b:
                continue
            values.append({'name': b[0].strip(), 'version': b[1].strip()})
        return values

    def get_branch_names(self):
        """ Returns a list of branch names from the repo. """
        branches = self.hg_command("branches")
        branch_list = branches.strip().split("\n")
        values = []
        for branch in branch_list:
            b = re.split('(\d+:[A-Za-z0-9]+)', branch)
            if not b:
                continue
            name = b[0]
            if name:
                name = name.strip()
                values.append(name)
        return values

    BOOKMARK_LIST = 0
    BOOKMARK_CREATE = 1
    BOOKMARK_DELETE = 2
    BOOKMARK_RENAME = 3
    BOOKMARK_INACTIVE = 4

    def hg_bookmarks(self, action=BOOKMARK_LIST, name=None, newname=None,
                     revision=None, force=False):
        cmds = ['bookmarks']
        if force:
            cmds += ['--force']
        if revision:
            cmds += ['--rev', str(revision)]
        if action == Repo.BOOKMARK_LIST:
            out = self.hg_command(*cmds)
            bookmarks = []
            if out.startswith(" "):  # handles "no bookmarks set" reply
                for line in out.split('\n'):
                    if line:
                        # active/inactive
                        if line.strip()[0] == '*':
                            bookmark = [True]
                            line = line[3:]
                        else:
                            bookmark = [False]
                        # name and identifier
                        line.split()
                        bookmark += [line.split()[0].strip(), line.split()[1]]
                        bookmarks += [bookmark]
            return bookmarks
        elif action == Repo.BOOKMARK_INACTIVE:
            cmds += ['--inactive']
            if name:
                cmds += [name]
            return self.hg_command(*cmds)
        elif name is not None:
            if action == Repo.BOOKMARK_DELETE:
                cmds += ['--delete', name]
                return self.hg_command(*cmds)
            elif action == Repo.BOOKMARK_RENAME and newname is not None:
                cmds += ['--rename', name, newname]
                return self.hg_command(*cmds)
            elif action == Repo.BOOKMARK_CREATE:
                cmds += [name]
                return self.hg_command(*cmds)

    def hg_diff(self, rev_a=None, rev_b=None, filenames=None):
        """
            Get a unified diff as returned by 'hg diff'.

            rev_a and rev_b are passed as -r <rev> arguments to the call,
            filenames are expected to be an iterable of file names.

            Returns a list of dicts where every dict has a 'filename'
            and 'diff' field, where with diff being the complete diff
            for the file including header (diff -r xxxx -r xxx...).
        """
        cmds = ['diff']
        for rev in (rev_a, rev_b):
            if rev is not None:
                cmds += ['-r', rev]

        if filenames is not None:
            cmds += list(filenames)

        result = self.hg_command(*cmds)
        diffs = []
        if result:
            filere = re.compile("^diff .* (\S+)$")
            for line in result.split('\n'):
                match = filere.match(line)
                if match:
                    diffs.append({'filename': match.groups()[0], 'diff': ''})
                diffs[-1]['diff'] += line + '\n'
        return diffs

    def hg_status(self, empty=False, clean=False):
        """
            Get repository status.

            Returns a dict containing a *change char* -> *file list*
            mapping, where change char is in::

             A, M, R, !, ?

            Example after adding one.txt, modifying a_folder/two.txt
            and three.txt::

             {'A': ['one.txt'], 'M': ['a_folder/two.txt', 'three.txt'],
             '!': [], '?': [], 'R': []}

            If empty is set to non-False value, don't add empty lists.
            If clean is set to non-False value, add clean files as well (-A)
        """
        cmds = ['status']
        if clean:
            cmds.append('-A')
        out = self.hg_command(*cmds).strip()
        # default empty set
        if empty:
            changes = {}
        else:
            changes = {'A': [], 'M': [], '!': [], '?': [], 'R': []}
            if clean:
                changes['C'] = []

        if not out:
            return changes
        lines = out.split("\n")
        status_split = re.compile("^(.) (.*)$")

        for change, path in [status_split.match(x).groups() for x in lines]:
            changes.setdefault(change, []).append(path)
        return changes

    rev_log_tpl = (
        '\{"node":"{node|short}","rev":"{rev}","author":"{author|urlescape}",'
        '"branch":"{branches}","parents":"{parents}","date":"{date|isodate}",'
        '"tags":"{tags}","desc":"{desc|urlescape}\"}\n'
    )

    def revision(self, identifier):
        """Get the identified revision as a Revision object."""
        out = self.hg_log(identifier=str(identifier),
                          template=self.rev_log_tpl)
        return Revision(out)

    def revisions(self, slice_):
        """Returns a list of Revision objects for the given slice"""
        id = ":".join([str(x) for x in (slice_.start, slice_.stop)])
        out = self.hg_log(identifier=id,
                          template=self.rev_log_tpl)

        revs = []
        for entry in out.split('\n')[:-1]:
            revs.append(Revision(entry))

        return revs

    def read_config(self):
        """
            Read the configuration as seen with 'hg showconfig'.

            Is called by __init__ - only needs to be called explicitly
            to reflect changes made since instantiation.
        """
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
        """Return the value of a configuration variable."""
        if not self.cfg:
            self.cfg = self.read_config()
        return self.cfg.get(section, {}).get(key, None)

    def configbool(self, section, key):
        """
            Return a config value as a boolean value.

            Empty values, the string 'false' (any capitalization),
            and '0' are considered False, anything else is True
        """
        if not self.cfg:
            self.cfg = self.read_config()
        value = self.cfg.get(section, {}).get(key, None)
        if not value:
            return False
        if value == "0" or value.upper() == "FALSE" or value.upper() == "None":
            return False
        return True

    def configlist(self, section, key):
        """
            Return a config value as a list.

            Will try to create a list delimited by commas, or whitespace if
            no commas are present.
        """
        if not self.cfg:
            self.cfg = self.read_config()
        value = self.cfg.get(section, {}).get(key, None)
        if not value:
            return []
        if value.count(","):
            return value.split(",")
        else:
            return value.split()

    @classmethod
    def hg_version(cls):
        """Return the version number of Mercurial."""
        out = Repo.command(".", os.environ, "version")
        match = re.search('\s\(version (.*)\)$', out.split("\n")[0])
        return match.group(1)

    @classmethod
    def hg_clone(cls, url, path, *args):
        """
            Clone repository at given `url` to `path`, then return
            repo object to `path`.
        """
        Repo.command(".", os.environ, "clone", url, path, *args)
        return Repo(path)

    @classmethod
    def hg_root(self, path):
        """
            Return the root (top) of the path.

            When no path is given, current working directory is used.
            Raises HgException when no repo is available.
        """
        if path is None:
            path = os.getcwd()
        return Repo.command(path, os.environ, "root").strip("\n +")
