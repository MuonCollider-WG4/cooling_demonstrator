import tempfile
import shutil
import subprocess
import os
import pathlib
import unittest
import sys

class TestCooling(unittest.TestCase):
    """
    Test the cooling lattice is okay

    For now just check it runs; eventually we can check performance etc
    """
    def setUp(self):
        """Make a tempdir to run the test in."""
        self.tempdir = tempfile.TemporaryDirectory()
        self.test_path = os.path.abspath(__file__)
        self.g4bl_cooling_dir = pathlib.Path(self.test_path).parents[1]
        self.g4bl_cooling_dir = f"{self.g4bl_cooling_dir}/cooling/g4bl"
        self.target_dir = f"{self.tempdir.name}/g4bl"
        self.log_file = open(f"{self.tempdir.name}/run.log", "w")
        shutil.copytree(self.g4bl_cooling_dir, self.target_dir)

    def tearDown(self):
        """Clean up tempdir and log file resources"""
        print("Ran in", self.target_dir)
        self.log_file.close()
        self.tempdir.cleanup()

    def test_g4bl_cooling_runs(self):
        """Check that the G4BL cooling simulation runs and returns 0"""
        os.chdir(self.target_dir)
        command = [os.path.expandvars("${G4BL_EXE_PATH}/g4bl"), "cooling.g4bl", "last_event=10"]
        output = subprocess.run(command, stdout=self.log_file, stderr=subprocess.STDOUT)
        self.assertEqual(output.returncode, 0)

if __name__ == "__main__":
    unittest.main()

