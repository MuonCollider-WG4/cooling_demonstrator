#!/usr/bin/python

import sys

"""
Script to turn output from G4Beamline fieldntuple into a 2d field map suitable
for solenoid operation.

Assumptions:
* field map is generated using fieldntuple
* only solenoid fields are present during field map generation i.e. dipoles and
  RF are switched off
* field map is regular grid in x, z with no steps in y
"""

class FieldMapReader:
    def __init__(self):
        self.input_filename = "fieldmap_2d.txt"
        self.file_in = None
        self.columns = None
        self.title = None
        self.data = {}
        self.line_in = 0
        self.line = "no line"

        self.file_out = None

    def get_axis(self, axis):
        """Get the list of grid points along axis

        Assumes that the grid is approximately regular along axis i.e. it is one
        of x, y, z, t

        Returns the list of grid points with duplicates and near duplicates
        removed
        """
        u_list = set(self.data[axis]) # remove duplicates
        u_list = sorted(list(u_list)) # sorted list
        u0 = min(u_list)
        u1 = max(u_list)
        n_u = len(u_list)
        if n_u <= 1:
            raise ValueError(f"Field map only had one value on axis {axis}")
        du = (u1-u0)/(n_u-1)
        if du == 0:
            raise ValueError(f"Field map had 0 step size on axis {axis}")

        # fix in case floating point error gives us extra u_list entries
        # require u_list elements are all spaced by at least du/2
        # i.e. we can't have anything spaced by 1e-12 or whatever
        u_list = [u_list[0]]+[u for i, u in enumerate(u_list[1:]) if u > u_list[i]+du/2]
        return u_list

    def read_line(self):
        """
        Read a single line. Tracks the line number and the current line, for
        debugging purposes
        """
        self.line_in += 1
        self.line = self.file_in.readline()
        if self.line == "":
            raise StopIteration("File ended")
        return True

    def read_title(self):
        """Read the title line"""
        self.read_line()
        self.title = self.line.replace("#", "")
        self.title = self.line.replace("\n", "")

    def read_columns(self):
        """Read the list of columns"""
        self.read_line()
        self.columns = self.line.split()
        self.columns = [word.replace("#", "") for word in self.columns]
        self.columns = [word for word in self.columns if word != ""]
        self.data = dict([(name, []) for name in self.columns])

    def read_data(self):
        """Read the body data"""
        while self.read_line():
            values = [float(word) for word in self.line.split()]
            for i, col in enumerate(self.columns):
                self.data[col].append(values[i])

    def read_field_map(self):
        """
        Read a field map in G4BL format. Assumed format is
        # title
        # x y z t bx by bz ex ey ez
        [data]

        Note the particular columns are not hard-coded
        """
        print(f"Loading '{self.input_filename}'")
        self.file_in = open(self.input_filename)
        try:
            self.read_title()
            self.read_columns()
            self.read_data()
        except StopIteration:
            print(f"Finished reading on line {self.line_in}")
        except Exception:
            sys.excepthook(*sys.exc_info())
            print(f"Reading G4Beamline file failed while reading line {self.line_in} with line \n{self.line}\n")


class FieldMapWriter:
    def __init__(self):
        """Initialisation"""
        self.output_filename = "solenoid_file.txt"
        self.file_out = None
        self.field_map = None
        self.z_axis = "z"
        self.r_axis = "x"
        self.bz_axis = "Bz"
        self.br_axis = "Bx"

        self.norm_b = 1.0
        self.current = 1.0
        self.z_list = []
        self.r_list = []

    def write_header(self):
        """Write the header information"""
        z0 = self.z_list[0]
        nz = len(self.z_list)
        dz = (self.z_list[1]-self.z_list[0])/(nz-1)

        nr = len(self.r_list)
        dr = (self.r_list[1]-self.r_list[0])/(nr-1)

        header = f"""* Field map generated from {self.field_map.title}
param normB={self.norm_b} current={self.current}
cylinder Z0={z0} nR={nr} nZ={nz} dR={dr} dZ={dz}
extendZ flip=Br
"""
        self.file_out.write(header)

    def write_data(self):
        """Write the body information, sorted by z_axis then r_axis"""
        rows = []
        for i, z in enumerate(self.field_map.data[self.z_axis]):
            r = self.field_map.data[self.r_axis][i]
            bz = self.field_map.data[self.bz_axis][i]
            br = self.field_map.data[self.br_axis][i]
            rows.append([z, r, bz, br])
        rows = sorted(rows)
        for a_row in rows:
            [z, r, bz, br] = a_row
            self.file_out.write(f"{r:12.10g} {z:12.10g} {br:12.10g} {bz:12.10g}\n")
        print(f"Wrote {len(rows)} lines")

    def write_field_map(self):
        """Write the field map"""
        print(f"Writing to {self.output_filename}")
        self.file_out = open(self.output_filename, "w")
        self.z_list = self.field_map.get_axis(self.z_axis)
        self.r_list = self.field_map.get_axis(self.r_axis)
        self.write_header()
        self.write_data()

def main():
    if len(sys.argv) < 3:
        print("Usage: python g4bl_fieldmap.py [input_filename] [output_filename]")
        return

    reader = FieldMapReader()
    reader.input_filename = sys.argv[1]
    reader.read_field_map()

    writer = FieldMapWriter()
    writer.output_filename = sys.argv[2]
    writer.field_map = reader
    writer.write_field_map()

    print("Finished okay")

if __name__ == "__main__":
    main()
