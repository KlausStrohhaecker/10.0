import pcbnew
import wx
import os


#
# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
#

def mm(v):
    return pcbnew.FromMM(v)


def polygon_bbox(poly):

    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]

    return (
        min(xs),
        min(ys),
        max(xs),
        max(ys),
    )


def point_in_polygon(x, y, poly):

    inside = False

    n = len(poly)

    p1x, p1y = poly[0]

    for i in range(n + 1):

        p2x, p2y = poly[i % n]

        if y > min(p1y, p2y):

            if y <= max(p1y, p2y):

                if x <= max(p1x, p2x):

                    if p1y != p2y:

                        xinters = (
                            (y - p1y)
                            * (p2x - p1x)
                            / (p2y - p1y)
                            + p1x
                        )

                    if p1x == p2x or x <= xinters:
                        inside = not inside

        p1x, p1y = p2x, p2y

    return inside


#
# ------------------------------------------------------------
# Dialog
# ------------------------------------------------------------
#

class ViaDialog(wx.Dialog):

    def __init__(self, parent):

        super().__init__(
            parent,
            title="Via Stitching"
        )

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        grid = wx.FlexGridSizer(
            rows=5,
            cols=2,
            vgap=8,
            hgap=8
        )

        grid.AddGrowableCol(1, 1)

        #
        # Pad
        #

        grid.Add(
            wx.StaticText(
                self,
                label="Via pad size [mm]"
            ),
            0,
            wx.ALIGN_CENTER_VERTICAL
        )

        self.pad = wx.TextCtrl(
            self,
            value="0.6"
        )

        grid.Add(
            self.pad,
            1,
            wx.EXPAND
        )

        #
        # Hole
        #

        grid.Add(
            wx.StaticText(
                self,
                label="Via hole size [mm]"
            ),
            0,
            wx.ALIGN_CENTER_VERTICAL
        )

        self.hole = wx.TextCtrl(
            self,
            value="0.3"
        )

        grid.Add(
            self.hole,
            1,
            wx.EXPAND
        )

        #
        # Spacing
        #

        grid.Add(
            wx.StaticText(
                self,
                label="Via grid spacing [mm]"
            ),
            0,
            wx.ALIGN_CENTER_VERTICAL
        )

        self.spacing = wx.TextCtrl(
            self,
            value="5"
        )

        grid.Add(
            self.spacing,
            1,
            wx.EXPAND
        )

        #
        # Clearance
        #

        grid.Add(
            wx.StaticText(
                self,
                label="Clearance [mm]"
            ),
            0,
            wx.ALIGN_CENTER_VERTICAL
        )

        self.clearance = wx.TextCtrl(
            self,
            value="0.3"
        )

        grid.Add(
            self.clearance,
            1,
            wx.EXPAND
        )

        #
        # Net
        #

        grid.Add(
            wx.StaticText(
                self,
                label="Net name"
            ),
            0,
            wx.ALIGN_CENTER_VERTICAL
        )

        self.net = wx.TextCtrl(
            self,
            value="GND"
        )

        grid.Add(
            self.net,
            1,
            wx.EXPAND
        )

        main_sizer.Add(
            grid,
            1,
            wx.ALL | wx.EXPAND,
            12
        )

        warning = wx.StaticText(
            self,
            label=(
                "Note: Unfill all zones first to "
                "avoid spurious net re-assignments"
            )
        )

        main_sizer.Add(
            warning,
            0,
            wx.LEFT | wx.RIGHT | wx.BOTTOM,
            12
        )

        button_sizer = self.CreateSeparatedButtonSizer(
            wx.OK | wx.CANCEL
        )

        main_sizer.Add(
            button_sizer,
            0,
            wx.ALL | wx.EXPAND,
            12
        )

        self.SetSizerAndFit(main_sizer)


    def get_values(self):

        return {

            "pad": float(
                self.pad.GetValue()
            ),

            "hole": float(
                self.hole.GetValue()
            ),

            "spacing": float(
                self.spacing.GetValue()
            ),

            "clearance": float(
                self.clearance.GetValue()
            ),

            "net": self.net.GetValue().strip(),
        }


#
# ------------------------------------------------------------
# Plugin
# ------------------------------------------------------------
#

class ViaStitchingPlugin(pcbnew.ActionPlugin):

    def defaults(self):
        self.name = "Via Stitching"
        self.category = "Modify PCB"
        self.description = "Generate via stitching"
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(
            os.path.dirname(__file__),
            "icon.png"
        )

    #
    # --------------------------------------------------------
    #
    # Main
    #
    # --------------------------------------------------------
    #

    def Run(self):

        board = pcbnew.GetBoard()

        dialog = ViaDialog(None)

        if dialog.ShowModal() != wx.ID_OK:
            return

        try:

            params = dialog.get_values()

            self.validate(board, params)

            polygons = self.determine_region(board)

            self.place_vias(
                board,
                polygons,
                params
            )

            pcbnew.Refresh()

        except Exception:

            import traceback
            
            wx.MessageBox(
                traceback.format_exc(),
                "Via Stitching Error",
                wx.OK | wx.ICON_ERROR
            )


    #
    # --------------------------------------------------------
    #
    # Validation
    #
    # --------------------------------------------------------
    #

    def validate(self, board, params):

        if params["pad"] <= 0:
            raise RuntimeError(
                "Pad size must be > 0"
            )

        if params["hole"] <= 0:
            raise RuntimeError(
                "Hole size must be > 0"
            )

        if params["spacing"] <= 0:
            raise RuntimeError(
                "Spacing must be > 0"
            )

        if params["clearance"] < 0:
            raise RuntimeError(
                "Clearance must be >= 0"
            )

        if params["pad"] <= params["hole"]:

            raise RuntimeError(
                "Pad size must be larger than hole size"
            )

        nets = board.GetNetsByName()

        if params["net"] not in nets:

            raise RuntimeError(
                f"\n\nNet '{params['net']}' does not exist\n"
            )

        netcode = nets[params["net"]].GetNetCode()

    #
    # --------------------------------------------------------
    #
    # Determine region
    #
    # --------------------------------------------------------
    #

    def determine_region(self, board):

        selected_zones = []
        non_zone_selected = False

        #
        # Zones
        #

        for zone in board.Zones():

            if zone.IsSelected():
                selected_zones.append(zone)

        #
        # Invalid selections
        #

        for track in board.GetTracks():

            if track.IsSelected():
                non_zone_selected = True

        for fp in board.GetFootprints():

            if fp.IsSelected():
                non_zone_selected = True

        for drawing in board.GetDrawings():

            if drawing.IsSelected():
                non_zone_selected = True

        if non_zone_selected:

            raise RuntimeError(
                "Only zones can be selected as defining area"
            )

        polygons = []

        #
        # No selection:
        # use board bbox
        #

        if len(selected_zones) == 0:

            bbox = board.GetBoardEdgesBoundingBox()

            poly = [

                (
                    bbox.GetLeft(),
                    bbox.GetTop()
                ),

                (
                    bbox.GetRight(),
                    bbox.GetTop()
                ),

                (
                    bbox.GetRight(),
                    bbox.GetBottom()
                ),

                (
                    bbox.GetLeft(),
                    bbox.GetBottom()
                ),
            ]

            polygons.append(poly)

            return polygons

        #
        # Zone outlines
        #

        for zone in selected_zones:

            shape = zone.Outline()

            if shape.OutlineCount() == 0:
                continue

            line = shape.Outline(0)

            poly = []

            for i in range(line.PointCount()):

                p = line.CPoint(i)

                poly.append(
                    (p.x, p.y)
                )

            if len(poly) >= 3:
                polygons.append(poly)

        if len(polygons) == 0:

            raise RuntimeError(
                "No usable polygons found"
            )

        return polygons


    #
    # --------------------------------------------------------
    #
    # Collision checking
    #
    # --------------------------------------------------------
    #

    def can_place_via(
        self,
        board,
        x,
        y,
        radius,
        target_netcode
    ):

        via_rect = pcbnew.BOX2I(
            pcbnew.VECTOR2I(
                int(x - radius),
                int(y - radius)
            ),
            pcbnew.VECTOR2I(
                int(radius * 2),
                int(radius * 2)
            )
        )

        test_point = pcbnew.VECTOR2I(
            int(x),
            int(y)
        )

        #
        # ----------------------------------------------------
        # Tracks and vias
        # ----------------------------------------------------
        #

        for item in board.GetTracks():

            #
            # Fast bbox reject
            #

            if not item.GetBoundingBox().Intersects(via_rect):
                continue

            #
            # Exact geometry
            #

            try:

                dist = item.GetEffectiveShape().Distance(
                    test_point
                )

                if dist < radius:
                    return False

            except:
                return False

        #
        # ----------------------------------------------------
        # Pads
        # ----------------------------------------------------
        #

        for fp in board.GetFootprints():

            for pad in fp.Pads():

                #
                # Fast bbox reject
                #

                if not pad.GetBoundingBox().Intersects(via_rect):
                    continue

                #
                # Exact geometry
                #

                try:

                    dist = pad.GetEffectiveShape().Distance(
                        test_point
                    )

                    if dist < radius:
                        return False

                except:
                    return False

        #
        # ----------------------------------------------------
        # Copper drawings
        # ----------------------------------------------------
        #

        for drawing in board.GetDrawings():

            try:

                layer = drawing.GetLayer()

                if layer < pcbnew.F_Cu:
                    continue

                if layer > pcbnew.B_Cu:
                    continue

                #
                # Fast bbox reject
                #

                if not drawing.GetBoundingBox().Intersects(via_rect):
                    continue

                #
                # Exact geometry
                #

                try:

                    dist = drawing.GetEffectiveShape().Distance(
                        test_point
                    )

                    if dist >= radius:
                        continue

                except:
                    continue

                #
                # Same-net filled rectangles allowed
                #

                try:

                    if (
                        drawing.GetShapeStr() == "Rect" and
                        drawing.IsFilled() and
                        drawing.GetNetCode() == target_netcode
                    ):

                        continue

                except:
                    pass

                return False

            except:
                pass

        #
        # Zones always allowed
        #

        return True

    #
    # --------------------------------------------------------
    #
    # Placement
    #
    # --------------------------------------------------------
    #

    def place_vias(
        self,
        board,
        polygons,
        params
    ):

        spacing = mm(
            params["spacing"]
        )

        pad = mm(
            params["pad"]
        )

        hole = mm(
            params["hole"]
        )

        clearance = mm(
            params["clearance"]
        )

        radius = (
            pad * 0.45
        ) + clearance

        netcode = board.GetNetcodeFromNetname(
            params["net"]
        )

        netinfo = board.FindNet(netcode)

        group = pcbnew.PCB_GROUP(board)

        group.SetName(
            f"Via Stitching ({params['net']})"
        )

        board.Add(group)

        created = []

        for poly in polygons:

            bbox = polygon_bbox(poly)

            rectangle_mode = (
                len(poly) == 4
            )

            x = bbox[0] + spacing

            while x < bbox[2] - spacing:

                y = bbox[1] + spacing

                while y < bbox[3] - spacing:

                    inside = True

                    if not rectangle_mode:

                        inside = point_in_polygon(
                            x,
                            y,
                            poly
                        )

                    if inside:

                        if self.can_place_via(
                            board,
                            x,
                            y,
                            radius,
                            netcode
                        ):

                            via = pcbnew.PCB_VIA(board)

                            via.SetViaType(
                                pcbnew.VIATYPE_THROUGH
                            )

                            via.SetPosition(
                                pcbnew.VECTOR2I(
                                    int(x),
                                    int(y)
                                )
                            )

                            via.SetWidth(
                                int(pad)
                            )

                            via.SetDrill(
                                int(hole)
                            )

                            via.SetNetCode(
                                netcode
                            )

                            via.SetNet(
                                netinfo
                            )

                            board.Add(via)

                            group.AddItem(via)

                            created.append(via)

                    y += spacing

                x += spacing

        pcbnew.Refresh()

        wx.MessageBox(
            f"Placed {len(created)} vias",
            "Via Stitching",
            wx.OK | wx.ICON_INFORMATION
        )

