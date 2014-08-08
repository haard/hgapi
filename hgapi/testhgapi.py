#  -*- encoding: utf-8 -*-
from __future__ import with_statement, unicode_literals

import unittest
import doctest
import os
import shutil
import hgapi


# TODO: add better logger test
class TestHgAPI(unittest.TestCase):
    """
        Test the hgapi.

        Uses and wipes folders named 'test' (a.k.a repo), 'test-clone'
        (a.k.a clone).  Tests are dependent on each other; named
        test_<number>_name for sorting.
    """
    repo = hgapi.Repo("./test", user="testuser")
    clone = hgapi.Repo("./test-clone", user="testuser")

    @classmethod
    def _delete_and_create(cls, path):
        if os.path.exists(path):
            shutil.rmtree(path)
        os.mkdir(path)
        assert os.path.exists(path)

    @classmethod
    def setUpClass(cls):
        # patch for Python 3
        if hasattr(cls, "assertEqual"):
            setattr(cls, "assertEquals", cls.assertEqual)
            setattr(cls, "assertNotEquals", cls.assertNotEqual)
        TestHgAPI._delete_and_create("./test")
        TestHgAPI._delete_and_create("./original")

    @classmethod
    def tearDownClass(self):
        shutil.rmtree("test", ignore_errors=True)
        shutil.rmtree("test-clone", ignore_errors=True)

    def test_000_Init(self):
        self.repo.hg_init()
        self.assertTrue(os.path.exists("test/.hg"))

    def test_010_Identity(self):
        rev = self.repo.hg_rev()
        hgid = self.repo.hg_id()
        self.assertEquals(-1, rev)
        self.assertEquals("000000000000", hgid)

    def test_020_Add(self):
        with open("test/file.txt", "w") as out:
            out.write("stuff")
        self.repo.hg_add("file.txt")
        self.assertListEqual(self.repo.hg_status()['A'], ['file.txt'])

    def test_021_Add(self):
        with open("test/foo.txt", "w") as out:
            out.write("A sample file")
        with open("test/bar.txt", "w") as out:
            out.write("Another sample file")
        self.repo.hg_add()
        self.assertListEqual(self.repo.hg_status()['A'],
                             ['bar.txt', 'file.txt', 'foo.txt'])

    def test_030_Commit(self):
        # commit and check that we're on a real revision
        self.repo.hg_commit("adding", user="test")
        rev = self.repo.hg_rev()
        hgid = self.repo.hg_id()
        self.assertEquals(rev, 0)
        self.assertNotEquals(hgid, "000000000000")

        # write some more to file
        with open("test/file.txt", "w+") as out:
            out.write("more stuff")

        # commit and check that changes have been made
        self.repo.hg_commit("modifying", user="test")
        rev2 = self.repo.hg_rev()
        hgid2 = self.repo.hg_id()
        self.assertNotEquals(rev, rev2)
        self.assertNotEquals(hgid, hgid2)

    def test_040_Log(self):
        rev = self.repo[0]
        self.assertEquals(rev.desc, "adding")
        self.assertEquals(rev.author, "test")
        self.assertEquals(rev.branch, "default")
        self.assertEquals(rev.parents, [-1])

    def test_050_Update(self):
        node = self.repo.hg_id()
        self.repo.hg_update(1)
        self.assertEquals(self.repo.hg_rev(), 1)
        self.repo.hg_update("tip")
        self.assertEquals(self.repo.hg_id(), node)

    def test_060_Heads(self):
        node = self.repo.hg_node()

        self.repo.hg_update(0)
        with open("test/file.txt", "w+") as out:
            out.write("even more stuff")

        # creates new head
        self.repo.hg_commit("modifying", user="test")

        heads = self.repo.hg_heads()
        self.assertEquals(len(heads), 2)
        self.assertTrue(node in heads)
        self.assertTrue(self.repo.hg_node() in heads)

        heads = self.repo.hg_heads(short=True)
        self.assertEquals(len(heads), 2)
        self.assertTrue(node[:12] in heads)
        self.assertTrue(self.repo.hg_node()[:12] in heads)

        # close head again
        self.repo.hg_commit("Closing branch", close_branch=True)
        self.repo.hg_update(node)

        # check that there's only one head remaining
        heads = self.repo.hg_heads()
        self.assertEquals(len(heads), 1)
        self.assertTrue(node in heads)

    def test_070_Config(self):
        with open("test/.hg/hgrc", "w") as hgrc:
            hgrc.write("[test]\n" +
                       "stuff.otherstuff = tsosvalue\n" +
                       "stuff.debug = True\n" +
                       "stuff.verbose = false\n" +
                       "stuff.list = one two three\n" +
                       "[ui]\n" +
                       "username = testsson")
        # re-read config
        self.repo.read_config()
        self.assertEquals(self.repo.config('test', 'stuff.otherstuff'),
                          "tsosvalue")
        self.assertEquals(self.repo.config('ui', 'username'),
                          "testsson")

    def test_071_ConfigBool(self):
        self.assertTrue(self.repo.configbool('test', 'stuff.debug'))
        self.assertFalse(self.repo.configbool('test', 'stuff.verbose'))

    def test_072_ConfigList(self):
        self.assertTrue(self.repo.configlist('test', 'stuff.list'),
                        ["one", "two", "three"])

    def test_080_LogBreakage(self):
        """
            Some log messages/users could possibly break
            the revision parsing.
        """
        # write some more to file
        with open("test/file.txt", "w+") as out:
            out.write("stuff and, more stuff")

        # commit and check that changes have been made
        self.repo.hg_commit("}", user="},desc=\"test")
        self.assertEquals(self.repo["tip"].desc, "}")
        self.assertEquals(self.repo["tip"].author, "},desc=\"test")

    def test_090_ModifiedStatus(self):
        # write some more to file
        with open("test/file.txt", "a") as out:
            out.write("stuff stuff stuff")
        status = self.repo.hg_status()
        self.assertEquals(status,
                          {'A': [], 'M': ['file.txt'], '!': [],
                           '?': [], 'R': []})

    def test_100_CleanStatus(self):
        # commit file created in 090
        self.repo.hg_commit("Comitting changes", user="test")
        # assert status is empty
        self.assertEquals(self.repo.hg_status(),
                          {'A': [], 'M': [], '!': [], '?': [], 'R': []})

    def test_110_UntrackedStatus(self):
        # create a new file
        with open("test/file2.txt", "w") as out:
            out.write("stuff stuff stuff")
        status = self.repo.hg_status()
        self.assertEquals(status,
                          {'A': [], 'M': [], '!': [],
                           '?': ['file2.txt'], 'R': []})

    def test_120_AddedStatus(self):
        # add file created in 110
        self.repo.hg_add("file2.txt")
        status = self.repo.hg_status()
        self.assertEquals(status,
                          {'A': ['file2.txt'], 'M': [], '!': [],
                           '?': [], 'R': []})

    def test_130_MissingStatus(self):
        # commit file created in 120
        self.repo.hg_commit("Added file")
        import os
        os.unlink("test/file2.txt")
        status = self.repo.hg_status()
        self.assertEquals(status,
                          {'A': [], 'M': [], '!': ['file2.txt'],
                           '?': [], 'R': []})

    def test_140_RemovedStatus(self):
        # remove file from repo
        self.repo.hg_remove("file2.txt")
        status = self.repo.hg_status()
        self.assertEquals(status,
                          {'A': [], 'M': [], '!': [],
                           '?': [], 'R': ['file2.txt']})

    def test_140_EmptyStatus(self):
        self.repo.hg_revert(all=True)
        status = self.repo.hg_status(empty=True)
        self.assertEquals(status, {})

    def test_150_ForkAndMerge(self):
        # store this version
        node = self.repo.hg_node()

        self.repo.hg_update(4, clean=True)
        with open("test/file3.txt", "w") as out:
            out.write("this is more stuff")

        # creates new head
        self.repo.hg_add("file3.txt")
        self.repo.hg_commit("adding head", user="test")

        heads = self.repo.hg_heads()
        self.assertEquals(len(heads), 2)
        self.assertTrue(node in heads)
        self.assertTrue(self.repo.hg_node() in heads)

        # merge the changes
        self.repo.hg_merge(node)
        self.repo.hg_commit("merge")

        # check that there's only one head remaining
        heads = self.repo.hg_heads()
        self.assertEquals(len(heads), 1)

    def test_160_CommitFiles(self):
        with open("test/file2.txt", "w") as out:
                    out.write("newstuff")
        with open("test/file3.txt", "w") as out:
            out.write("this is even more stuff")
        self.repo.hg_commit("only committing file2.txt",
                            user="test",
                            files=["file2.txt"])
        self.assertTrue("file3.txt" in self.repo.hg_status()["M"])

    def test_170_Indexing(self):
        with open("test/file2.txt", "a+") as out:
            out.write("newstuff")
        self.repo.hg_commit("indexing", user="test", files=["file2.txt"])
        # compare tip and current revision number
        self.assertEquals(self.repo['tip'], self.repo[self.repo.hg_rev()])
        self.assertEquals(self.repo['tip'].desc, "indexing")

    def test_180_Slicing(self):
        with open("test/file2.txt", "a+") as out:
            out.write("newstuff")
        self.repo.hg_commit("indexing", user="test", files=["file2.txt"])

        all_revs = self.repo[0:'tip']
        self.assertEquals(len(all_revs), 12)
        self.assertEquals(all_revs[-1].desc, all_revs[-2].desc)
        self.assertNotEquals(all_revs[-2].desc, all_revs[-3].desc)

    def test_190_Branches(self):
        # make sure there is only one branch and it is default
        self.assertEquals(self.repo.hg_branch(), "default")
        branches = self.repo.get_branches()
        self.assertEquals(len(branches), 1)
        branch_names = self.repo.get_branch_names()
        self.assertEquals(len(branch_names), 1)
        self.assertEquals(branch_names[0], "default")

        # create a new branch, should still be default in branches
        # until we commit - but branch should return the new branch
        self.assertTrue(self.repo.hg_branch('test_branch').startswith(
            "marked working directory as branch test_branch"))
        self.assertEquals(self.repo.hg_branch(), "test_branch")
        branches = self.repo.get_branches()
        self.assertEquals(len(branches), 1)
        branch_names = self.repo.get_branch_names()
        self.assertEquals(len(branch_names), 1)
        self.assertEquals(branch_names[0], "default")

        # now commit. branch and branches should change to test_branch
        self.repo.hg_commit("commit test_branch")
        self.assertEquals(self.repo.hg_branch(), "test_branch")
        branches = self.repo.get_branches()
        self.assertEquals(len(branches), 2)
        branch_names = self.repo.get_branch_names()
        self.assertEquals(len(branch_names), 2)

        # Test branch name with space
        branch = self.repo.hg_branch('test branch with space')
        message = "marked working directory as branch test branch with space"
        self.assertTrue(branch.startswith(message))
        self.assertEquals(self.repo.hg_branch(), "test branch with space")
        self.repo.hg_commit("commit test branch with space")
        self.assertEquals(self.repo.hg_branch(), "test branch with space")
        branches = self.repo.get_branches()
        self.assertEquals(len(branches), 3)
        branch_names = self.repo.get_branch_names()
        self.assertEquals(len(branch_names), 3)

        # Test closing of a branch
        self.repo.hg_commit("Closing test branch", close_branch=True)
        branches = self.repo.get_branches()
        self.assertEquals(len(branches), 2)
        branch_names = self.repo.get_branch_names()
        self.assertEquals(len(branch_names), 2)

    def test_200_CommitWithDates(self):
        self.repo.hg_update("test_branch")
        rev0 = self.repo.hg_rev()

        with open("test/file.txt", "w+") as out:
            out.write("even more stuff")

        self.repo.hg_commit("modifying and setting a date",
                            user="test",
                            date="10/10/11 UTC")

        rev = self.repo["tip"]
        self.assertEquals(rev.desc, "modifying and setting a date")
        self.assertEquals(rev.author, "test")
        self.assertEquals(rev.branch, "test_branch")
        self.assertEquals(rev.date, "2011-10-10 00:00 +0000")
        self.assertEquals(rev.parents, [rev0])

    def test_210_Tags(self):
        original_tip = self.repo['tip'].node
        self.repo.hg_tag('mytag', 'othertag')
        self.repo.hg_tag('mytag2', rev=1)
        self.repo.hg_tag('long mytag3', rev=2)
        tags = self.repo.hg_tags()
        self.assertEqual(tags, {'mytag': original_tip,
                                'othertag': original_tip,
                                'mytag2': self.repo[1].node,
                                'long mytag3': self.repo[2].node,
                                'tip': self.repo[-1].node})

    def test_220_LogWithBranch(self):
        default = self.repo.hg_log(branch='default')
        branch = self.repo.hg_log(branch='test_branch')
        self.assertTrue("commit test_branch" in branch)
        self.assertFalse("commit test_branch" in default)

    def test_230_BasicDiff(self):
        diffs = self.repo.hg_diff('default', 'test_branch')
        self.assertTrue('.hgtags' in [diff['filename'] for diff in diffs])
        self.assertTrue('+even more stuff' in diffs[1]['diff'])

    def test_240_DiffFile(self):
        diffs = self.repo.hg_diff('default',
                                  'test_branch',
                                  filenames=['file.txt'])
        self.assertEquals(len(diffs), 1)
        self.assertEquals(diffs[0]['filename'], 'file.txt')
        self.assertTrue('+even more stuff' in diffs[0]['diff'])

    def test_250_ExitCode(self):
        try:
            self.repo.hg_update('notexistingref')
        except hgapi.HgException as update_ex:
            self.assertNotEquals(update_ex.exit_code, None)
            self.assertNotEquals(update_ex.exit_code, 0)

    def test_260_EmptyDiff(self):
        self.repo.hg_update('default', clean=True)
        diffs = self.repo.hg_diff('default', filenames=['file.txt'])
        self.assertEquals(len(diffs), 0)

    def test_270_Move(self):
        # add source.txt, commit it
        with open("test/source.txt", "w") as out:
            out.write("stuff")
        self.repo.hg_add("source.txt")
        self.repo.hg_commit("Source is committed.")
        # move it to destination
        self.repo.hg_rename("source.txt", "destination.txt")
        # get diffs and check proper move
        diffs = self.repo.hg_diff()
        self.assertTrue(diffs[0]['filename'] == 'destination.txt')
        self.assertTrue(diffs[1]['filename'] == 'source.txt')
        self.repo.hg_commit("Checked move.")

    def test_280_AddRemove(self):
        # remove foo and add fizz first
        os.remove("test/foo.txt")
        with open("test/fizz.txt", "w") as out:
            out.write("fuzz")
        # then test addremove
        self.repo.hg_addremove()
        self.assertListEqual(self.repo.hg_status()['A'], ['fizz.txt'])
        self.assertListEqual(self.repo.hg_status()['R'], ['foo.txt'])

    def test_300_clone(self):
        # clone test to test clone
        self.clone = hgapi.Repo.hg_clone("./test", "./test-clone")
        self.assertTrue(isinstance(self.clone, hgapi.Repo))
        self.assertEquals(self.clone.path, self.repo.path + "-clone")

    def test_310_pull(self):
        # add a new directory with some files in test repo first
        os.mkdir("./test/cities")
        with open("./test/cities/brussels.txt", "w") as out:
            out.write("brussel")
        with open("./test/cities/antwerp.txt", "w") as out:
            out.write("antwerpen")
        self.repo.hg_add()
        message = "[TEST] Added two cities."
        self.repo.hg_commit(message)
        self.clone.hg_pull("../test")
        # update clone after pull and then check if the
        # identifiers are the same
        self.clone.hg_update("tip")
        self.assertEquals(self.clone.hg_id(), self.repo.hg_id())
        # check summary of pulled tip
        self.assertTrue(message in self.clone.hg_log(identifier="tip"))

    def test_320_push(self):
        # add another file in test-clone first
        with open("./test-clone/cities/ghent.txt", "w") as out:
            out.write("gent")
        self.clone.hg_add()
        message = "[CLONE] Added one file."
        self.clone.hg_commit(message)
        self.clone.hg_push("../test")
        # update test after push and assert
        self.repo.hg_update("tip")
        self.assertEquals(self.clone.hg_id(), self.repo.hg_id())
        # check summary of pushed tip
        self.assertTrue(message in self.repo.hg_log(identifier="tip"))

    def test_400_version(self):
        self.assertNotEquals(hgapi.Repo.hg_version(), "")

    def test_410_root(self):
        # regular test repo
        reply = hgapi.Repo.hg_root("./test")
        self.assertTrue(reply.endswith("/hgapi/test"))
        # non existing repo
        self.assertRaises(hgapi.HgException, hgapi.Repo.hg_root, "./whatever")

    def test_411_paths(self):
        paths = self.repo.hg_paths()
        self.assertEquals(paths, {})

        paths = self.clone.hg_paths()
        self.assertNotEquals(paths, {})

        self.assertTrue("default" in paths)
        self.assertTrue(paths['default'].endswith('test'))

    def test_412_outgoing(self):
        # modify file in the cloned repository and commit it
        with open("./test-clone/cities/ghent.txt", "a") as out:
            out.write("amsterdam")
        self.clone.hg_commit("[CLONE] Modified file")

        outgoing = self.clone.hg_outgoing()
        self.assertEquals(1, len(outgoing))
        self.assertEquals("[CLONE] Modified file", outgoing[0].desc)

        # push and check outgoing changes again
        self.clone.hg_push()
        outgoing = self.clone.hg_outgoing()
        self.assertEquals(0, len(outgoing))

        # a repository without remote should throw an exception
        self.assertRaises(hgapi.HgException, self.repo.hg_outgoing)

    def test_413_incoming(self):
        with open("./test/cities/ghent.txt", "a") as out:
            out.write("amstelveen")
        self.repo.hg_commit("[CLONE] Modified file again")

        incoming = self.clone.hg_incoming()
        self.assertEquals(1, len(incoming))
        self.assertEquals("[CLONE] Modified file again", incoming[0].desc)

        # pull changes, update and check incoming again
        self.clone.hg_pull()
        self.clone.hg_update("tip")

        incoming = self.clone.hg_incoming()
        self.assertEquals(0, len(incoming))

        # a repository without remote should throw an exception
        self.assertRaises(hgapi.HgException, self.repo.hg_incoming)

    def test_420_CommitWithNonAsciiCharacters(self):
        with open("test/file3.txt", "w") as out:
            out.write("enjoy a new file")
        self.repo.hg_add("file3.txt")

        self.repo.hg_commit("éàô",
                            user="F. Håård",
                            date="10/10/11 UTC")

        rev = self.repo["tip"]

        self.assertEquals(rev.desc, "éàô")
        self.assertEquals(rev.author, "F. Håård")

    def test_430_Bookmarks(self):
        # check no bookmarks
        self.assertListEqual(self.repo.hg_bookmarks(), [])
        empty_list = self.repo.hg_bookmarks(action=self.repo.BOOKMARK_LIST)
        self.assertListEqual(empty_list, [])
        # create bookmark at tip (revision 23:somevalue)
        self.repo.hg_bookmarks(action=self.repo.BOOKMARK_CREATE,
                               name="foo")
        # [True, 'foo', '23:somevalue']
        self.assertTrue(self.repo.hg_bookmarks()[0][0])
        self.assertEqual(self.repo.hg_bookmarks()[0][1], 'foo')
        self.assertTrue('25:' in self.repo.hg_bookmarks()[0][2])
        # create bookmark at '10:somevalue' named 'bar'
        self.repo.hg_bookmarks(action=self.repo.BOOKMARK_CREATE,
                               name="bar", revision=10)
        self.assertFalse(self.repo.hg_bookmarks()[0][0])
        self.assertEqual(self.repo.hg_bookmarks()[0][1], 'bar')
        self.assertTrue('10:' in self.repo.hg_bookmarks()[0][2])
        # rename foo to fizz
        self.repo.hg_bookmarks(action=self.repo.BOOKMARK_RENAME,
                               name='foo', newname='fizz')
        self.assertTrue(self.repo.hg_bookmarks()[1][0])
        self.assertEqual(self.repo.hg_bookmarks()[1][1], 'fizz')
        self.assertTrue('25:' in self.repo.hg_bookmarks()[1][2])
        # make fizz inactive
        self.repo.hg_bookmarks(action=self.repo.BOOKMARK_INACTIVE,
                               name='fizz')
        self.assertFalse(self.repo.hg_bookmarks()[1][0])
        self.assertEqual(self.repo.hg_bookmarks()[1][1], 'fizz')
        self.assertTrue('25:' in self.repo.hg_bookmarks()[1][2])
        # delete fizz
        self.repo.hg_bookmarks(action=self.repo.BOOKMARK_DELETE,
                               name='fizz')
        self.assertTrue(len(self.repo.hg_bookmarks()) == 1)


def test_doc():
    # prepare for doctest
    os.mkdir("./test_hgapi")
    with open("test_hgapi/file.txt", "w") as target:
        target.write("stuff")
    try:
        # run doctest
        doctest.testfile("../README.rst")
    finally:
        # cleanup
        shutil.rmtree("test_hgapi")


if __name__ == "__main__":
    # run full test suite
    try:
        test_doc()
    finally:
        unittest.main()
