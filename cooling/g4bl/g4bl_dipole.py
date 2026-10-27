#!/usr/bin/python
import time
import os
import sys
import math
import subprocess
import tempfile

"""
Script to generate a dipole field map with a soft-edged fringe field

This is a workaround because G4BL internal dipole routines are bugged.

Algorithm comes from Wolski paper and Ruihu's rectilinear g4bl lattices;
mistakes belong to Rogers.
"""

class DipoleField:
    def __init__(self):
        self.by0 = 1.0 # T
        self.fall_off = 310.0 # mm, full aperture of dipole
        self.length = 100.0 # mm
        self.a_1 = 5.0

    def fringe(self, x, y, z):
        """
        Calculate the field from one fringe (start or end)

        :param x: horizontal position (not used for dipole)
        :param y: vertical position
        :param z: longitudinal position
        :return: list of [Bx, By, Bz]
        """
        xf = self.a_1 * x/self.fall_off
        yf = self.a_1 * y/self.fall_off
        zf = self.a_1 * z/self.fall_off
        bx = 0.0
        by = self.by0 * (
                (1 + math.exp(zf) * math.cos(yf)) /
                (1 + 2 * math.exp(zf) * math.cos(yf) + math.exp(2 * zf))
        )
        bz = -self.by0 * math.exp(zf) * math.sin(yf) / (
                1 + 2 * math.exp(zf) * math.cos(yf) + math.exp(2 * zf)
        )
        return [bx, by, bz]

    def get_field(self, x, y, z):
        [bxl, byl, bzl] = self.fringe(x, y, -z-self.length/2)
        [bxr, byr, bzr] = self.fringe(x, y, z-self.length/2)
        return [bxl+bxr, byl+byr-1, -bzl+bzr]

class FieldMapWriter:
    def __init__(self):
        """Initialisation"""
        self.output_filename = "dipole_field_map.txt"
        self.file_out = None
        self.dipole = None

        self.norm_b = None # WARNING: if None always scale the dipole so By(0,0,0) = 1.0 [T]
        self.current = 1.0

        self.x0 = 0.0
        self.nx = 31
        self.dx = 5.0

        self.y0 = 0.0
        self.ny = 31
        self.dy = 5.0

        self.z0 = 0.0
        self.nz = 101
        self.dz = 5.0

    def write_field_map(self):
        """Write the field map"""
        self.file_out = open(self.output_filename, "w")
        self.write_header()
        self.write_data()
        self.file_out.close()

    def write_header(self):
        """Write the header information"""
        if self.norm_b is None:
            self.norm_b = 1/self.dipole.get_field(0, 0, 0)[1]
        header = f"""* Dipole field map generated from cooling demonstrator toolset
param normB={self.norm_b} current={self.current}
grid X0={self.x0} Y0={self.y0} Z0={self.z0} nX={self.nx} nY={self.ny} nZ={self.nz} dX={self.dx} dY={self.dy} dZ={self.dz}
extendY flip=Bz
extendZ flip=Bz
"""
        self.file_out.write(header)

    def write_data(self):
        """Write the body information, sorted by z_axis then r_axis

        G4Beamline has two formats, this implements the 'block' format
        """
        x_list = [self.x0+xi*self.dx for xi in range(self.nx)]
        y_list = [self.y0+yi*self.dy for yi in range(self.ny)]
        z_list = [self.z0+zi*self.dz for zi in range(self.nz)]
        # for g4bl afficionados, pointwise does not work for 3D field map
        self.file_out.write("data\n")
        for x in x_list:
            for y in y_list:
                for z in z_list:
                    [bx, by, bz] = self.dipole.get_field(x, y, z)
                    self.file_out.write(f"{x} {y} {z} {bx:10.6g} {by:10.6g} {bz:10.6g} 0 0 0\n")

class TestDipole:
    def __init__(self):
        self.dipole = DipoleField()
        self.test_dipole()
        self.test_dipole_off_axis()

    def test_dipole(self):
        """Just print the field value along the axis"""
        for z in range(-20, 501, 20):
            [bx, by, bz] = self.dipole.get_field(0, 0, z)
            #print(z, bx, by, bz)

    def get_div_b(self, x, y, z, delta):
        """Calculate divb numerically"""
        #dbxdx is 0 by inspection
        [bx, by0, bz] = self.dipole.get_field(0, y-delta, z)
        [bx, by1, bz] = self.dipole.get_field(0, y+delta, z)
        dbydy = (by1-by0)/(2*delta)
        [bx, by, bz0] = self.dipole.get_field(0, y, z-delta)
        [bx, by, bz1] = self.dipole.get_field(0, y, z+delta)
        dbzdz = (bz1-bz0)/(2*delta)
        return dbydy+dbzdz

    def get_curl_b(self, x, y, z, delta):
        """Calculate curlb numerically"""
        [bx, by, bz0] = self.dipole.get_field(0, y-delta, z)
        [bx, by, bz1] = self.dipole.get_field(0, y+delta, z)
        dbzdy = (bz1-bz0)/(2*delta)
        [bx, by0, bz] = self.dipole.get_field(0, y, z-delta)
        [bx, by1, bz] = self.dipole.get_field(0, y, z+delta)
        dbydz = (by1-by0)/(2*delta)
        # all other terms 0 by inspection
        return dbzdy-dbydz

    def test_dipole_off_axis(self):
        """
        Print the field value along the axis, with divergence and curl; try fiddling with the dipole parameters, its
        quite interesting to see non-convergence poles appearing as "fall_off" gets smaller.
        """
        delta = 1.0e-3
        y = 10.0
        for y in range(-50, 151, 50):
            #print("y:", y)
            for z in range(-100, 101, 20):
                [bx, by, bz] = self.dipole.get_field(0, y, z)
                divb = self.get_div_b(0, y, z, delta)
                curlb = self.get_curl_b(0, y, z, delta)
                #print(f"    z {z:10.4g} b {bx:10.4g} {by:10.4g} {bz:10.4g} divb {divb:10.4g} curlb {curlb:10.4g}")
                assert abs(divb) < 1.0e-3, f"divb {divb} too large for y={y} z={z}"
                assert abs(curlb) < 1.0e-3, f"curlb {curlb} too large for y={y} z={z}"

class TestFieldMap:
    def __init__(self):
        self.field_map = FieldMapWriter()
        self.field_map.dipole = DipoleField()
        self.test_field_map()

    def check_field_map(self, fmap: str) -> bool:
        """
        Check field map output from g4bl against analytical field map

        :param fmap: file name of the fieldmap
        :return: bool corresponding to test pass
        """
        testpass = True
        try:
            fin = open(fmap, "r")
        except Exception:
            return False
        fin.readline()
        fin.readline()
        norm_b = 1 / self.field_map.dipole.get_field(0, 0, 0)[1]
        for line in fin.readlines():
            try:
                values = [float(word) for word in line.split()]
                ref_values = self.field_map.dipole.get_field(values[0], values[1], values[2]-100)
                ref_values = [norm_b*val for val in ref_values]
                #print(values[0:3], values[4:7], ref_values)
                for i, val in enumerate(ref_values):
                    if abs(val-values[4+i]) > 1.0e-3:
                        print(f"Mismatch at {values[0:3]}: {values[3:6]} vs {ref_values}")
                        testpass = False
            except Exception:
                sys.excepthook(*sys.exc_info())
                print(f"Failed to parse line {line}")
                testpass = False
        return testpass

    def test_field_map(self):
        minimal_g4bl_deck = f"""
            param epsMax=0.001
            fieldmap dipole filename={self.field_map.output_filename} current=1.0
            fieldntuple field_out_1d format=ascii filename=test.dat z=-100,300,10 y=-10,10,10
            place dipole z=100
        """
        # the with ... syntax means python deletes the temp directory when the code is finished running
        with tempfile.TemporaryDirectory(suffix="cooling_demo_test") as tmpdirname:
            here = os.getcwd()
            os.chdir(tmpdirname)
            with open("g4bl_deck.txt", "w") as f:
                f.write(minimal_g4bl_deck)
                self.field_map.write_field_map()
            with open("g4bl.log", "w") as logfile:
                subprocess.run(["g4bl", "g4bl_deck.txt"], stdout=logfile, stderr=subprocess.STDOUT)
            time.sleep(1)
            if not self.check_field_map(os.path.join(os.getcwd(), "test.dat.txt")):
                print("I am working in", os.getcwd())
                input("The self-test failed: Press <cr> to clean up or wait and check the data files manually.")
            os.chdir(here)

def main():
    if len(sys.argv) < 2:
        print("Usage: python g4bl_dipole.py [output_filename]")
        return
    TestDipole()
    TestFieldMap()
    field_map = FieldMapWriter()
    field_map.dipole = DipoleField() # use defaults?
    field_map.write_field_map()

if __name__ == "__main__":
    main()
