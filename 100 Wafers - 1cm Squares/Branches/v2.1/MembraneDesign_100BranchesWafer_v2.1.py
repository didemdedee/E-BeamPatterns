# -*- coding: utf-8 -*-
"""
Created on Fri Dec 18 14:11:31 2015

@author: Martin Friedl

1.4.1 - Added cleaved cross section wires to quickly check the cross section of many wires by cleaving + SEM
v2.0 - Added buffers around the branches to get them to grow better, especially when the slits are very thin
v2.0 - Increased thicknesses of NMs to 20/40/80/140/220/320 to see how they grow, min pitch is now 500nm instead of 250
v2.0 - Converted all structures from "Rect" to "Path", reducing file size by about 20%
v2.0 - Made 2 out of the 4 regions with linear NMs instead of only branches, for possible contacting
v2.1 - Re-Added the arahonov bohm effect structures
"""

import itertools, json, os.path
from datetime import date
from random import choice as random_choice

import numpy as np

from Patterns.GrowthTheoryCell import make_theory_cell
from Patterns.GrowthTheoryCell_100_3BranchDevices import make_theory_cell_3br
from Patterns.GrowthTheoryCell_100_4BranchDevices import make_theory_cell_4br
from Patterns.QuantumPlayground_100_v1 import make_qp
from gdsCAD_py3.core import Cell, Boundary, CellArray, Layout, Path
from gdsCAD_py3.shapes import Box, Rectangle, Label
from gdsCAD_py3.templates100 import Wafer_GridStyle, dashed_line

WAFER_ID = '000045672829'  # CHANGE THIS FOR EACH DIFFERENT WAFER
PATTERN = 'SQBR2.1'
putOnWafer = True  # Output full wafer or just a single pattern?
HighDensity = False  # High density of triangles?
glbAlignmentMarks = False
tDicingMarks = 10.  # Dicing mark line thickness (um)
rotAngle = 0.  # Rotation angle of the membranes
wafer_r = 25e3
waferVer = '100 Membrane Branches v2.1'.format(int(wafer_r / 1000))

waferLabel = waferVer + '\n' + date.today().strftime("%d%m%Y")
# Layers
l_smBeam = 0
l_lgBeam = 1
l_drawing = 100


# %% Wafer template for MBE growth
class MBE100Wafer(Wafer_GridStyle):
    """
    A 2" wafer divided into square cells
    """

    def __init__(self, name, cells=None):
        Wafer_GridStyle.__init__(self, name=name, cells=cells, block_gap=1200.)

        # The placement of the wafer alignment markers
        am_x = 1.5e4
        am_y = 1.5e4
        self.align_pts = np.array([am_x, am_y])
        self.align_pts = np.vstack((self.align_pts, self.align_pts *
                                    (-1, 1)))  # Reflect about y-axis
        self.align_pts = np.vstack((self.align_pts, self.align_pts *
                                    (1, -1)))  # Reflect about x-axis

        self.wafer_r = 25e3
        self.block_size = np.array([10e3, 10e3])
        self._place_blocks(radius=self.wafer_r + 5e3)
        # if glbAlignmentMarks:
        #     self.add_aligment_marks(l_lgBeam)
        #     self.add_orientation_text(l_lgBeam)
        # self.add_dicing_marks()  # l_lgBeam, mkWidth=mkWidth Width of dicing marks

        self.add_blocks()
        self.add_wafer_outline(layers=l_drawing)
        self.add_dashed_dicing_marks(layers=[l_lgBeam])
        self.add_subdicing_marks(200, 5, layers=[l_lgBeam])
        self.add_block_labels(l_lgBeam, unique_ids=True, load_ids=True)

        self.add_prealignment_markers(layers=[l_lgBeam])
        # self.add_tem_membranes([20., 80., 220., 320., 140., 40.], 1000, 1, l_smBeam)
        self.add_theory_cells()
        self.add_chip_labels()
        self.add_cleave_xsection_nws([20., 40., 80., 140., 220., 320.], l_smBeam)

        # self.add_blockLabels(l_lgBeam)
        # self.add_cellLabels(l_lgBeam)

        bottom = np.array([0, -self.wafer_r * 0.9])
        # top = np.array([0, -1]) * bottom
        self.add_waferLabel(waferLabel, l_drawing, pos=bottom)

    def add_block_labels(self, layers, unique_ids=False, save_ids=True, load_ids=True):
        if type(layers) is not list:
            layers = [layers]

        txtSize = 1000
        blockids = []

        if not unique_ids:
            for (i, pt) in enumerate(self.block_pts):
                blockids.append(self.blockcols[pt[0]] + self.blockrows[pt[1]])
        else:
            existing_ids = {}
            existing_id_set = set()
            # Load the previously-used IDs from a JSON file
            if load_ids:
                master_db = '../../../ChipIDs_DB.json'
                if os.path.isfile(master_db):
                    with open(master_db, 'r') as f:
                        try:
                            existing_ids = json.load(f)
                            existing_id_set = set([item for sublist in list(existing_ids.values()) for item in sublist])

                            # Check if wafer is in the loaded database
                            if load_ids and WAFER_ID in existing_ids:
                                blockids = existing_ids[WAFER_ID]

                        # If there is a reading error then proceed with a warning
                        except json.decoder.JSONDecodeError:
                            print("Json Error: Couldn't load chip IDs from database!")
                            existing_id_set = set()

            # If the IDs haven't already been set by loading them from the database
            if not blockids:
                # Generate some new IDs, but only use the ones that haven't previously been used
                unique_label_string = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890'
                possible_label_set = set(["".join(x) for x in itertools.product(unique_label_string, repeat=2)])
                possible_label_set = possible_label_set - existing_id_set  # Remove chip lbls from the set of possible lbls

                blockids_set = set()
                while len(blockids_set) < len(self.blocks):
                    blockids_set.add(random_choice(list(possible_label_set)))

                blockids = list(blockids_set)

        # Save the labels to a file
        if save_ids:
            existing_ids.update({WAFER_ID: blockids})
            json_string = json.dumps(existing_ids)
            json_string = json_string.replace("], ", "],\n") # Make the file a bit easier to read in notepad
            with open(master_db, 'w') as f:
                f.write(json_string)

        # Write the labels to the cells
        for i, block in enumerate(self.blocks):
            blocklabel = Cell('LBL_B_' + blockids[i])
            for l in layers:
                txt = Label(blockids[i], txtSize, layer=l)
                bbox = txt.bounding_box
                offset = (0, 0)
                txt.translate(-np.mean(bbox, 0))  # Center text around origin
                txt.translate(offset)  # Translate it to bottom of wafer
                blocklabel.add(txt)
                block.add(blocklabel, origin=(self.block_size[0] / 2., self.block_size[1] / 2.))

    def add_dashed_dicing_marks(self, layers):
        if type(layers) is not list:
            layers = [layers]
        width = 10. / 2
        dashlength = 2000
        r = self.wafer_r
        rng = np.floor(self.wafer_r / self.block_size).astype(int)
        dmarks = Cell('DIC_MRKS')
        for l in layers:
            for x in np.arange(-rng[0], rng[0] + 1) * self.block_size[0]:
                y = np.sqrt(r ** 2 - x ** 2)
                vm = dashed_line([x, y], [x, -y], dashlength, width, layer=l)
                dmarks.add(vm)

            for y in np.arange(-rng[1], rng[1] + 1) * self.block_size[1]:
                x = np.sqrt(r ** 2 - y ** 2)
                hm = dashed_line([x, y], [-x, y], dashlength, width, layer=l)
                dmarks.add(hm)
        self.add(dmarks)

    def add_subdicing_marks(self, length, width, layers):
        if type(layers) is not list:
            layers = [layers]

        for l in layers:
            mark_cell = Cell("SubdicingMark")
            line = Path([[0, 0], [0, length]], width=width, layer=l)
            mark_cell.add(line)

            for block in self.blocks:
                block.add(mark_cell, origin=(self.block_size[0] / 2., 0), rotation=0)
                block.add(mark_cell, origin=(0, self.block_size[1] / 2.), rotation=-90)
                block.add(mark_cell, origin=(self.block_size[0], self.block_size[1] / 2.), rotation=90)
                block.add(mark_cell, origin=(self.block_size[0] / 2., self.block_size[1]), rotation=180)

    def add_prealignment_markers(self, layers, mrkr_size=7):
        if mrkr_size % 2 == 0:  # Number is even, but we need odd numbers
            mrkr_size += 1
        if type(layers) is not list:
            layers = [layers]

        for l in layers:
            rect_size = 10.  # 10 um large PAMM rectangles
            marker_rect = Rectangle([-rect_size / 2., -rect_size / 2.], [rect_size / 2., rect_size / 2.], layer=l)
            marker = Cell('10umMarker')
            marker.add(marker_rect)

            # Make one arm of the PAMM array
            marker_arm = Cell('PAMM_Arm')
            # Define the positions of the markers, they increase in spacing by 1 um each time:
            mrkr_positions = [75 * n + (n - 1) * n // 2 for n in range(1, (mrkr_size - 1) // 2 + 1)]
            for pos in mrkr_positions:
                marker_arm.add(marker, origin=[pos, 0])

            # Build the final PAMM Marker
            pamm_cell = Cell('PAMM_Marker')
            pamm_cell.add(marker)  # Center marker
            pamm_cell.add(marker_arm)  # Right arm
            pamm_cell.add(marker_arm, rotation=180)  # Left arm
            pamm_cell.add(marker_arm, rotation=90)  # Top arm
            pamm_cell.add(marker_arm, rotation=-90)  # Bottom arm
            for pos in mrkr_positions:
                pamm_cell.add(marker_arm, origin=[pos, 0], rotation=90)  # Top arms
                pamm_cell.add(marker_arm, origin=[-pos, 0], rotation=90)
                pamm_cell.add(marker_arm, origin=[pos, 0], rotation=-90)  # Bottom arms
                pamm_cell.add(marker_arm, origin=[-pos, 0], rotation=-90)

            # Make the 4 tick marks that mark the center of the array
            h = 30.
            w = 100.
            tick_mrk = Rectangle([-w / 2., -h / 2.], [w / 2, h / 2.], layer=l)
            tick_mrk_cell = Cell("TickMark")
            tick_mrk_cell.add(tick_mrk)
            pos = mrkr_positions[-1] + 75 + w / 2.
            pamm_cell.add(tick_mrk_cell, origin=[pos, 0])
            pamm_cell.add(tick_mrk_cell, origin=[-pos, 0])
            pamm_cell.add(tick_mrk_cell, origin=[0, pos], rotation=90)
            pamm_cell.add(tick_mrk_cell, origin=[0, -pos], rotation=90)

        center_x, center_y = (5000, 5000)
        for block in self.blocks:
            block.add(pamm_cell, origin=(center_x + 2000, center_y))
            block.add(pamm_cell, origin=(center_x - 2000, center_y))

    def add_tem_membranes(self, widths, length, pitch, layer):
        tem_membranes = Cell('TEM_Membranes')
        n = 4
        curr_y = 0
        for width in widths:
            membrane = Path([(-length / 2., 0), (length / 2., 0)], width=width / 1000., layer=layer)
            membrane_cell = Cell('Membrane_w{:.0f}'.format(width))
            membrane_cell.add(membrane)
            membrane_array = CellArray(membrane_cell, 1, n, (0, pitch))
            membrane_array_cell = Cell('MembraneArray_w{:.0f}'.format(width))
            membrane_array_cell.add(membrane_array)
            tem_membranes.add(membrane_array_cell, origin=(0, curr_y))
            curr_y += n * pitch

        n2 = 3
        tem_membranes2 = Cell('Many_TEM_Membranes')
        tem_membranes2.add(CellArray(tem_membranes, 1, n2, (0, n * len(widths) * pitch)))

        center_x, center_y = (5000, 5000)
        for block in self.blocks:
            block.add(tem_membranes2, origin=(center_x, center_y + 2000))
            block.add(tem_membranes2, origin=(center_x, center_y + 1500), rotation=45)

    def add_theory_cells(self):

        theory_cells = Cell('TheoryCells')
        theory_cells.add(make_theory_cell(wafer_orient='100'), origin=(-400, 0))
        theory_cells.add(make_theory_cell_3br(), origin=(0, 0))
        theory_cells.add(make_theory_cell_4br(), origin=(400, 0))

        theory_cells.add(make_theory_cell(wafer_orient='100'), origin=(-500, -400), rotation=45)
        theory_cells.add(make_theory_cell_3br(), origin=(-50, -400), rotation=45)
        theory_cells.add(make_theory_cell_4br(), origin=(370, -400), rotation=45)

        center_x, center_y = (5000, 5000)
        for block in self.blocks:
            block.add(theory_cells, origin=(center_x, center_y - 1700))

    def add_chip_labels(self):
        wafer_lbl = PATTERN + '\n' + WAFER_ID
        text = Label(wafer_lbl, 20., layer=l_lgBeam)
        text.translate(tuple(np.array(-text.bounding_box.mean(0))))  # Center justify label
        chip_lbl_cell = Cell('chip_label')
        chip_lbl_cell.add(text)

        center_x, center_y = (5000, 5000)
        for block in self.blocks:
            block.add(chip_lbl_cell, origin=(center_x, center_y - 2850))

    def add_cleave_xsection_nws(self, widths, layer):
        pitches = [0.5, 1., 2., 4.]
        n_membranes = 10
        length = 30
        spacing = 10

        cleave_xsection_cell = Cell("CleaveCrossSection")

        y_offset = 0
        for pitch in pitches:
            for width in widths:
                nm_cell = Cell("P{:.0f}W{:.0f}".format(pitch, width))
                slit = Path([(-length / 2., 0), (length / 2., 0)], width=width / 1000., layer=layer)
                nm_cell.add(slit)
                nm_cell_array = Cell("P{:.0f}W{:.0f}_Array".format(pitch, width))
                tmp = CellArray(nm_cell, 1.0, n_membranes, [0, pitch])
                nm_cell_array.add(tmp)
                cleave_xsection_cell.add(nm_cell_array, origin=(0, y_offset + pitch * n_membranes))
                y_offset += pitch * n_membranes + spacing
            y_offset += spacing * 3

        center_x, center_y = (5000, 5000)
        for block in self.blocks:
            block.add(cleave_xsection_cell, origin=(center_x + 1150, center_y - 340))
            block.add(cleave_xsection_cell, origin=(center_x - 450, center_y + 450), rotation=45.)
            block.add(cleave_xsection_cell, origin=(center_x + 340, center_y - 1150), rotation=90.)


class Frame(Cell):
    """
    Make a frame for writing to with ebeam lithography
    Params:
    -name of the frame, just like when naming a cell
    -size: the size of the frame as an array [xsize,ysize]
    """

    def __init__(self, name, size, border_layers):
        if not (type(border_layers) == list):
            border_layers = [border_layers]
        Cell.__init__(self, name)
        self.size_x, self.size_y = size
        # Create the border of the cell
        for l in border_layers:
            self.border = Box(
                (-self.size_x / 2., -self.size_y / 2.),
                (self.size_x / 2., self.size_y / 2.),
                1,
                layer=l)
            self.add(self.border)  # Add border to the frame

        self.align_markers = None

    def make_align_markers(self, t, w, position, layers, joy_markers=False, camps_markers=False):
        if not (type(layers) == list):
            layers = [layers]
        top_mk_cell = Cell('AlignmentMark')
        for l in layers:
            if not joy_markers:
                am0 = Rectangle((-w / 2., -w / 2.), (w / 2., w / 2.), layer=l)
                rect_mk_cell = Cell("RectMarker")
                rect_mk_cell.add(am0)
                top_mk_cell.add(rect_mk_cell)
            elif joy_markers:
                crosspts = [(0, 0), (w / 2., 0), (w / 2., t), (t, t), (t, w / 2), (0, w / 2), (0, 0)]
                crosspts.extend(tuple(map(tuple, (-np.array(crosspts)).tolist())))
                am0 = Boundary(crosspts, layer=l)  # Create gdsCAD shape
                joy_mk_cell = Cell("JOYMarker")
                joy_mk_cell.add(am0)
                top_mk_cell.add(joy_mk_cell)

            if camps_markers:
                emw = 20.  # 20 um e-beam marker width
                camps_mk = Rectangle((-emw / 2., -emw / 2.), (emw / 2., emw / 2.), layer=l)
                camps_mk_cell = Cell("CAMPSMarker")
                camps_mk_cell.add(camps_mk)
                top_mk_cell.add(camps_mk_cell, origin=[100., 100.])
                top_mk_cell.add(camps_mk_cell, origin=[100., -100.])
                top_mk_cell.add(camps_mk_cell, origin=[-100., 100.])
                top_mk_cell.add(camps_mk_cell, origin=[-100., -100.])

            self.align_markers = Cell("AlignMarkers")
            self.align_markers.add(top_mk_cell, origin=np.array(position) * np.array([1, -1]))
            self.align_markers.add(top_mk_cell, origin=np.array(position) * np.array([-1, -1]))
            self.align_markers.add(top_mk_cell, origin=np.array(position) * np.array([1, 1]))
            self.align_markers.add(top_mk_cell, origin=np.array(position) * np.array([-1, 1]))
            self.add(self.align_markers)

    def make_slit_array(self, _pitches, spacing, _widths, _lengths, rot_angle,
                        array_height, array_width, array_spacing, layers):
        if not (type(layers) == list):
            layers = [layers]
        if not (type(_pitches) == list):
            _pitches = [_pitches]
        if not (type(_lengths) == list):
            _lengths = [_lengths]
        if not (type(_widths) == list):
            _widths = [_widths]
        manyslits = i = j = None
        for l in layers:
            i = -1
            j = -1
            manyslits = Cell("SlitArray")
            pitch = _pitches[0]
            for length in _lengths:
                j += 1
                i = -1

                for width in _widths:
                    # for pitch in pitches:
                    i += 1
                    if i % 3 == 0:
                        j += 1  # Move to array to next line
                        i = 0  # Restart at left

                    nx = int(array_width / (length + spacing))
                    ny = int(array_height / pitch)
                    # Define the slits
                    nm_cell = Cell("P{:.0f}W{:.0f}".format(pitch, width))
                    slit = Path([(-length / 2., 0), (length / 2., 0)], width=width, layer=l_smBeam)
                    nm_cell.add(slit)
                    slits = CellArray(nm_cell, nx, ny, (length + spacing, pitch))
                    slits.translate((-(nx - 1) * (length + spacing) / 2., -(ny - 1) * pitch / 2.))
                    slit_array = Cell("SlitArray")
                    slit_array.add(slits)
                    text = Label('w/p/l\n%i/%i/%i' % (width * 1000, pitch, length), 5, layer=l)
                    lbl_vertical_offset = 1.35
                    if j % 2 == 0:
                        text.translate(
                            tuple(np.array(-text.bounding_box.mean(0)) + np.array((
                                0, -array_height / lbl_vertical_offset))))  # Center justify label
                    else:
                        text.translate(
                            tuple(np.array(-text.bounding_box.mean(0)) + np.array((
                                0, array_height / lbl_vertical_offset))))  # Center justify label
                    slit_array.add(text)
                    manyslits.add(slit_array,
                                  origin=((array_width + array_spacing) * i, (
                                          array_height + 2. * array_spacing) * j - array_spacing / 2.))

        # This is an ugly hack to center rotated slits, should fix this properly...
        if rot_angle == 45:  # TODO: fix this ugly thing
            hacky_offset_x = 200
            hacky_offset_y = -25
        elif rot_angle == 90:
            hacky_offset_x = 356
            hacky_offset_y = 96.5
        else:
            hacky_offset_x = 0
            hacky_offset_y = 0

        self.add(manyslits, origin=(-i * (array_width + array_spacing) / 2 + hacky_offset_x,
                                    -(j + 1.5) * (array_height + array_spacing) / 2 + hacky_offset_y),
                 rotation=rot_angle)

    def make_arm(self, width, length, layer, cell_name='branch'):
        cell = Cell(cell_name)
        line = Path([[0, 0], [length, 0]], width=width, layer=layer)
        cell.add(line)
        return cell

    def make_branch_device(self, width, pitch, len_inner, len_outer, n_membranes, layer, buffers_only=False):
        branch_device = Cell('branch_device')
        inner_arm = self.make_arm(width, len_inner, layer, cell_name='inner_arm')
        outer_arm = self.make_arm(width, len_outer, layer, cell_name='outer_arm')
        outer_branch = Cell('outer_branch')
        outer_branch.add(outer_arm)
        outer_branch.add(outer_arm, rotation=90)

        branch_quarter = Cell('branch_third')
        if not buffers_only:
            branch_quarter.add(inner_arm)
        for i in range(1, int(n_membranes) + 1):
            branch_quarter.add(outer_branch, origin=((width + pitch) * i, (width + pitch) * i))

        branch_device.add(branch_quarter, rotation=0)
        branch_device.add(branch_quarter, rotation=90)
        branch_device.add(branch_quarter, rotation=180)
        branch_device.add(branch_quarter, rotation=270)

        # self.add(branch_device)

        return branch_device

    def make_branch_array(self, _widths, _lengths, nx, ny, spacing_structs, spacing_arrays, rot_angle, layers):
        if not (type(layers) == list):
            layers = [layers]
        if not (type(_lengths) == list):
            _lengths = [_lengths]
        if not (type(_widths) == list):
            _widths = [_widths]
        l = layers[0]
        _length = _lengths[0]

        manyslits = i = j = None

        slits = []
        for width in _widths:
            slit = Cell("Slit_{:.0f}".format(width * 1000))
            line = Path([[-_length / 2., 0], [_length / 2., 0]], width=width, layer=l)
            slit.add(line)
            slits.append(slit)

        buffers = self.make_branch_device(0.08, 1.0, _lengths[0] / 2., _lengths[0] / 2., 4, layers[0],
                                          buffers_only=True)

        many_crosses = Cell("CrossArray")
        x_pos = 0
        y_pos = 0

        array_pitch = (ny - 1) * (length + spacing_structs) - spacing_structs + spacing_arrays

        for j, width_vert in enumerate(_widths[::-1]):
            for i, width_horiz in enumerate(_widths):
                # Define a single cross
                cross = Cell("Cross_{:.0f}_{:.0f}".format(width_horiz * 1000, width_vert * 1000))
                cross.add(slits[i])  # Horizontal slit
                cross.add(slits[j], rotation=90)  # Vertical slit
                cross.add(buffers)
                # Define the cross array
                cross_array = Cell("CrossArray_{:.0f}_{:.0f}".format(width_horiz * 1000, width_vert * 1000))
                slit_array = CellArray(cross, nx, ny, (_length + spacing_structs, _length + spacing_structs))
                slit_array.translate(
                    (-(nx - 1) * (_length + spacing_structs) / 2., (-(ny - 1) * (_length + spacing_structs) / 2.)))
                cross_array.add(slit_array)
                many_crosses.add(cross_array, origin=(x_pos, y_pos))
                x_pos += array_pitch
            y_pos += array_pitch
            x_pos = 0

        # Make the labels
        lbl_cell = Cell("Lbl_Cell")
        for i, width in enumerate(_widths):
            text_string = 'W{:.0f}'.format(width * 1000)
            text = Label(text_string, 5, layer=l)
            text.translate(tuple(np.array(-text.bounding_box.mean(0))))
            x_offset = - 1.5 * array_pitch + i * array_pitch
            text.translate(np.array((x_offset, 0)))  # Center justify label
            lbl_cell.add(text)

        centered_cell = Cell('Centered_Cell')
        bbox = np.mean(many_crosses.bounding_box, 0)  # Get center of cell

        centered_cell.add(many_crosses, origin=tuple(-bbox))
        lbl_vertical_offset = 1.5
        centered_cell.add(lbl_cell, origin=(0, -bbox[1] * lbl_vertical_offset))
        centered_cell.add(lbl_cell, origin=(-bbox[1] * lbl_vertical_offset, 0), rotation=90)

        self.add(centered_cell, rotation=rot_angle)


# Create the pattern that we want to write

lgField = Frame("LargeField", (2000., 2000.), [])  # Create the large write field
lgField.make_align_markers(20., 200., (850., 850.), l_lgBeam, joy_markers=True, camps_markers=True)

# Define parameters that we will use for the slits
widths = [0.020, 0.040, 0.080, 0.140, 0.220, 0.320]
length = 20.

smFrameSize = 400
slitColumnSpacing = 3.

# Create the smaller write field and corresponding markers
smField1 = Frame("SmallField1", (smFrameSize, smFrameSize), [])
smField1.make_align_markers(2., 20., (180., 180.), l_lgBeam, joy_markers=True)
smField1.make_slit_array(1., slitColumnSpacing, widths, length, 0, 100, 100, 30, l_smBeam)

smField2 = Frame("SmallField2", (smFrameSize, smFrameSize), [])
smField2.make_align_markers(2., 20., (180., 180.), l_lgBeam, joy_markers=True)
smField2.make_slit_array(1., slitColumnSpacing, widths, length, 45., 100, 100, 30, l_smBeam)

widths = [0.040, 0.080, 0.140, 0.220]
length = 15.

smField3 = Frame("SmallField3", (smFrameSize, smFrameSize), [])
smField3.make_align_markers(2., 20., (180., 180.), l_lgBeam, joy_markers=True)
smField3.make_branch_array(widths, length, 2., 2., 15., 60., 0, l_smBeam)

smField4 = Frame("SmallField4", (smFrameSize, smFrameSize), [])
smField4.make_align_markers(2., 20., (180., 180.), l_lgBeam, joy_markers=True)
smField4.make_branch_array(widths, length, 2., 2., 15., 60., 45., l_smBeam)

quantum_playground = make_qp()

centerAlignField = Frame("CenterAlignField", (smFrameSize, smFrameSize), [])
centerAlignField.make_align_markers(2., 20., (180., 180.), l_lgBeam, joy_markers=True)

centerLeftAlignField = Frame("CenterLeftAlignField", (smFrameSize, smFrameSize), [])
centerLeftAlignField.make_align_markers(2., 20., (180., 180.), l_lgBeam, joy_markers=True)
centerLeftAlignField.add(quantum_playground)

centerRightAlignField = Frame("CenterRightAlignField", (smFrameSize, smFrameSize), [])
centerRightAlignField.make_align_markers(2., 20., (180., 180.), l_lgBeam, joy_markers=True)
centerRightAlignField.add(quantum_playground, rotation=45)

# Add everything together to a top cell
topCell = Cell("TopCell")
topCell.add(lgField)
smFrameSpacing = 400  # Spacing between the three small frames
dx = smFrameSpacing + smFrameSize
dy = smFrameSpacing + smFrameSize
topCell.add(smField1, origin=(-dx / 2., dy / 2.))
topCell.add(smField2, origin=(dx / 2., dy / 2.))
topCell.add(smField3, origin=(-dx / 2., -dy / 2.))
topCell.add(smField4, origin=(dx / 2., -dy / 2.))
topCell.add(centerLeftAlignField, origin=(-dx / 2, 0.))
topCell.add(centerRightAlignField, origin=(dx / 2, 0.))
topCell.add(centerAlignField, origin=(0., 0.))
topCell.spacing = np.array([4000., 4000.])

# %%Create the layout and output GDS file
layout = Layout('LIBRARY')
if putOnWafer:  # Fit as many patterns on a 2inch wafer as possible
    wafer = MBE100Wafer('MembranesWafer', cells=[topCell])
    layout.add(wafer)
    # layout.show()
else:  # Only output a single copy of the pattern (not on a wafer)
    layout.add(topCell)
    layout.show()

filestring = str(waferVer) + '_' + WAFER_ID + '_' + date.today().strftime("%d%m%Y") + ' dMark' + str(tDicingMarks)
filename = filestring.replace(' ', '_') + '.gds'
layout.save(filename)

cell_layout = Layout('LIBRARY')
cell_layout.add(wafer.blocks[0])
cell_layout.save(filestring.replace(' ', '_') + '_block' + '.gds')

# Output up chip for doing aligned jobs
layout_field = Layout('LIBRARY')
layout_field.add(topCell)
layout_field.save(filestring.replace(' ', '_') + '_2mmField.gds')
