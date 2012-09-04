from __future__ import with_statement
import unittest, doctest
import os, shutil, os.path
import hgapi 

class TestHgAPI(unittest.TestCase):
    """Tests for hgapi.py
    Uses and wipes subfolder named 'test'
    Tests are dependant on each other; named test_<number>_name for sorting
    """
    repo = hgapi.Repo("./test", user="testuser")
    
    @classmethod
    def setUpClass(cls):
        #Patch Python 3
        if hasattr(cls, "assertEqual"):
            setattr(cls, "assertEquals", cls.assertEqual)
            setattr(cls, "assertNotEquals", cls.assertNotEqual)
        if os.path.exists("./test"):
            shutil.rmtree("./test")
        os.mkdir("./test")
        assert os.path.exists("./test")

    @classmethod
    def tearDownClass(self):
        shutil.rmtree("test")

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
        
    def test_030_Commit(self):
        #Commit and check that we're on a real revision
        self.repo.hg_commit("adding", user="test")
        rev  = self.repo.hg_rev()
        hgid = self.repo.hg_id()
        self.assertEquals(rev, 0)
        self.assertNotEquals(hgid, "000000000000")

        #write some more to file
        with open("test/file.txt", "w+") as out:
            out.write("more stuff")

        #Commit and check that changes have been made
        self.repo.hg_commit("modifying", user="test")
        rev2  = self.repo.hg_rev()
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

        #creates new head
        self.repo.hg_commit("modifying", user="test")

        heads = self.repo.hg_heads()
        self.assertEquals(len(heads), 2)
        self.assertTrue(node in heads)
        self.assertTrue(self.repo.hg_node() in heads)

        #Close head again
        self.repo.hg_commit("Closing branch", close_branch=True)
        self.repo.hg_update(node)

        #Check that there's only one head remaining
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
        #re-read config
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
        """Some log messages/users could possibly break 
        the revision parsing"""
        #write some more to file
        with open("test/file.txt", "w+") as out:
            out.write("stuff and, more stuff")

        #Commit and check that changes have been made
        self.repo.hg_commit("}", user="},desc=\"test")
        self.assertEquals(self.repo["tip"].desc, "}")
        self.assertEquals(self.repo["tip"].author, "},desc=\"test")
  

    def test_090_ModifiedStatus(self):
        #write some more to file
        with open("test/file.txt", "a") as out:
            out.write("stuff stuff stuff")
        status = self.repo.hg_status()
        self.assertEquals(status, 
                          {'A': [], 'M': ['file.txt'], '!': [], 
                           '?': [], 'R': []})
        
    def test_100_CleanStatus(self):
        #commit file created in 090
        self.repo.hg_commit("Comitting changes", user="test")
        #Assert status is empty
        self.assertEquals(self.repo.hg_status(), 
                          {'A': [], 'M': [], '!': [], '?': [], 'R': []})

    def test_110_UntrackedStatus(self):
        #Create a new file
        with open("test/file2.txt", "w") as out:
            out.write("stuff stuff stuff")
        status = self.repo.hg_status()
        self.assertEquals(status, 
                          {'A': [], 'M': [], '!': [], 
                           '?': ['file2.txt'], 'R': []})

    def test_120_AddedStatus(self):
        #Add file created in 110
        self.repo.hg_add("file2.txt")
        status = self.repo.hg_status()
        self.assertEquals(status, 
                          {'A': ['file2.txt'], 'M': [], '!': [], 
                           '?': [], 'R': []})

    def test_130_MissingStatus(self):
        #Commit file created in 120
        self.repo.hg_commit("Added file")
        import os
        os.unlink("test/file2.txt")
        status = self.repo.hg_status()
        self.assertEquals(status, 
                          {'A': [], 'M': [], '!': ['file2.txt'], 
                           '?': [], 'R': []})

    def test_140_RemovedStatus(self):
        #Remove file from repo
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
        #Store this version
        node = self.repo.hg_node()

        self.repo.hg_update(4, clean=True)
        with open("test/file3.txt", "w") as out:
            out.write("this is more stuff")

        #creates new head
        self.repo.hg_add("file3.txt")
        self.repo.hg_commit("adding head", user="test")

        heads = self.repo.hg_heads()
        self.assertEquals(len(heads), 2)
        self.assertTrue(node in heads)
        self.assertTrue(self.repo.hg_node() in heads)

        #merge the changes
        self.repo.hg_merge(node)
        self.repo.hg_commit("merge")
        
        #Check that there's only one head remaining
        heads = self.repo.hg_heads()
        self.assertEquals(len(heads), 1)

    def test_160_CommitFiles(self):
        with open("test/file2.txt", "w") as out:
                    out.write("newstuff")        	
        with open("test/file3.txt", "w") as out:
            out.write("this is even more stuff")
        self.repo.hg_commit("only committing file2.txt", user="test", files=["file2.txt"])
        self.assertTrue("file3.txt" in self.repo.hg_status()["M"])
        
    def test_170_Indexing(self):
        with open("test/file2.txt", "a+") as out:
            out.write("newstuff")
        self.repo.hg_commit("indexing", user="test", files=["file2.txt"])
        #Compare tip and current revision number
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

        # create a new branch, should still be default in branches until we commit
        # but branch should return the new branch
        self.assertEquals(self.repo.hg_branch('test_branch'),
            "marked working directory as branch test_branch")
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

    def test_200_CommitWithDates(self):
        rev0 = self.repo.hg_rev()

        with open("test/file.txt", "w+") as out:
            out.write("even more stuff")

        self.repo.hg_commit("modifying and setting a date", user="test", date="10/10/11 UTC")

        rev = self.repo["tip"]
        self.assertEquals(rev.desc, "modifying and setting a date")
        self.assertEquals(rev.author, "test")
        self.assertEquals(rev.branch, "test_branch")
        self.assertEquals(rev.date, "2011-10-10 00:00 +0000")
        self.assertEquals(rev.parents, [rev0])

    def test_210_Tags(self):
        original_tip = self.repo['tip'].node
        self.repo.hg_tag('mytag')
        self.repo.hg_tag('mytag2', rev=1)
        tags = self.repo.hg_tags()
        self.assertEqual(tags, {'mytag': original_tip,
            'mytag2': self.repo[1].node,
            'tip': self.repo[-1].node})


def test_doc():
    #Prepare for doctest
    os.mkdir("./test_hgapi")
    with open("test_hgapi/file.txt", "w") as target:
        w = target.write("stuff")
    try:
        #Run doctest
        res = doctest.testfile("../README.rst")
    finally:
        #Cleanup
        shutil.rmtree("test_hgapi")

if __name__ == "__main__":
    import sys
    try:
        test_doc()
    finally:
        unittest.main()
    
