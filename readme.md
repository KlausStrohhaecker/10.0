# KiCAD 9.x Tips and Tricks

## A) GND Via Stitching, hack to remove conflicts with fills (and general editing)

1. Install plugin "kicad-action-scripts"

2. Deploy stitching vias 0.6/0.3mm, 0.3mm clearance, 3mm grid, rectangular pattern, ignore areas on other layers

3. select the via group and any "graphics" (copper fills) and move (shift-M) away, off board

4. ungroup the vias

5. delete the vias which conflict with the fills (as per DRC), or other you want to remove

6. regroup the vias

7. select the vias and the fills

8. move back to original position




