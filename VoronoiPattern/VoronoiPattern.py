"""
Voronoi Pattern Generator - Fusion 360 Add-in

Generates Voronoi lightening hole patterns on flat faces
for sheet metal laser-cut parts.
"""

import adsk.core
import adsk.fusion
import traceback
import json
import os

# Add lib directory to path so imports work inside Fusion 360
ADDIN_DIR = os.path.dirname(os.path.abspath(__file__))
import sys
if ADDIN_DIR not in sys.path:
    sys.path.insert(0, ADDIN_DIR)

from lib.voronoi import compute_voronoi
from lib.polygon import clip_polygon, offset_polygon, polygon_area
from lib.seed_generator import generate_seeds
from lib.sketch_drawer import (
    draw_voronoi_pattern,
    get_face_boundary,
    get_exclude_circles,
)

# Global command handlers (prevent garbage collection)
_handlers = []

CMD_ID = 'voronoiPatternCmd'
CMD_NAME = 'Voronoi Pattern'
CMD_DESC = 'Generate Voronoi lightening hole pattern on a face'


def run(context):
    """Called when the add-in is started."""
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        # Load default parameters
        defaults = _load_defaults()

        # Create command definition
        cmd_def = ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()

        cmd_def = ui.commandDefinitions.addButtonDefinition(
            CMD_ID, CMD_NAME, CMD_DESC,
            os.path.join(ADDIN_DIR, 'resources')
        )

        # Connect command created handler
        on_created = CommandCreatedHandler(defaults)
        cmd_def.commandCreated.add(on_created)
        _handlers.append(on_created)

        # Add to TOOLS tab > ADD-INS panel
        tools_tab = ui.allToolbarTabs.itemById('ToolsTab')
        if tools_tab:
            panel = tools_tab.toolbarPanels.itemById('SolidScriptsAddinsPanel')
            if panel:
                existing = panel.controls.itemById(CMD_ID)
                if not existing:
                    panel.controls.addCommand(cmd_def)

    except Exception:
        app = adsk.core.Application.get()
        ui = app.userInterface
        ui.messageBox(f'Failed to start Voronoi Pattern:\n{traceback.format_exc()}')


def stop(context):
    """Called when the add-in is stopped."""
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        # Remove command from panel
        tools_tab = ui.allToolbarTabs.itemById('ToolsTab')
        if tools_tab:
            panel = tools_tab.toolbarPanels.itemById('SolidScriptsAddinsPanel')
            if panel:
                ctrl = panel.controls.itemById(CMD_ID)
                if ctrl:
                    ctrl.deleteMe()

        # Remove command definition
        cmd_def = ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()

    except Exception:
        pass


def _load_defaults():
    """Load default parameters from config file."""
    config_path = os.path.join(ADDIN_DIR, 'config', 'defaults.json')
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception:
        return {
            'seed_count': 40,
            'min_rib_width': 3.0,
            'edge_margin': 5.0,
            'corner_radius': 1.0,
            'random_seed': 42,
            'density_gradient': True,
        }


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    """Builds the dialog UI when the command is created."""

    def __init__(self, defaults):
        super().__init__()
        self.defaults = defaults

    def notify(self, args):
        try:
            cmd = adsk.core.Command.cast(args.command)
            inputs = cmd.commandInputs
            d = self.defaults

            # Face selection
            face_input = inputs.addSelectionInput(
                'targetFace', 'Target Face',
                'Select a planar face for the pattern')
            face_input.addSelectionFilter('PlanarFaces')
            face_input.setSelectionLimits(1, 1)

            # Exclude holes selection
            holes_input = inputs.addSelectionInput(
                'excludeHoles', 'Exclude Holes (optional)',
                'Select circular edges to exclude as mount holes')
            holes_input.addSelectionFilter('CircularEdges')
            holes_input.setSelectionLimits(0, 0)  # 0 = unlimited
            holes_input.isVisible = True

            # Seed count
            inputs.addIntegerSliderCommandInput(
                'seedCount', 'Seed Count',
                10, 200, False)
            inputs.itemById('seedCount').valueOne = d.get('seed_count', 40)

            # Min rib width
            rib_input = inputs.addValueInput(
                'minRibWidth', 'Min Rib Width',
                'mm', adsk.core.ValueInput.createByReal(
                    d.get('min_rib_width', 3.0) * 0.1))  # mm to cm

            # Edge margin
            margin_input = inputs.addValueInput(
                'edgeMargin', 'Edge Margin',
                'mm', adsk.core.ValueInput.createByReal(
                    d.get('edge_margin', 5.0) * 0.1))

            # Corner radius
            radius_input = inputs.addValueInput(
                'cornerRadius', 'Corner Radius',
                'mm', adsk.core.ValueInput.createByReal(
                    d.get('corner_radius', 1.0) * 0.1))

            # Random seed
            inputs.addIntegerSpinnerCommandInput(
                'randomSeed', 'Random Seed',
                0, 9999, 1, d.get('random_seed', 42))

            # Density gradient
            inputs.addBoolValueInput(
                'densityGradient', 'Density Gradient',
                True, '', d.get('density_gradient', True))

            # Connect execute handler
            on_execute = CommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            # Connect validate handler
            on_validate = ValidateInputsHandler()
            cmd.validateInputs.add(on_validate)
            _handlers.append(on_validate)

        except Exception:
            app = adsk.core.Application.get()
            app.userInterface.messageBox(traceback.format_exc())


class ValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    """Validate that inputs are valid before enabling OK button."""

    def notify(self, args):
        try:
            inputs = args.inputs
            face_input = inputs.itemById('targetFace')
            args.areInputsValid = face_input.selectionCount > 0
        except Exception:
            args.areInputsValid = False


class CommandExecuteHandler(adsk.core.CommandExecuteEventHandler):
    """Execute the Voronoi pattern generation."""

    def notify(self, args):
        try:
            app = adsk.core.Application.get()
            ui = app.userInterface
            design = adsk.fusion.Design.cast(app.activeProduct)

            inputs = args.command.commandInputs

            # Read inputs
            face_input = inputs.itemById('targetFace')
            face = adsk.fusion.BRepFace.cast(face_input.selection(0).entity)

            holes_input = inputs.itemById('excludeHoles')
            hole_entities = []
            for i in range(holes_input.selectionCount):
                hole_entities.append(holes_input.selection(i).entity)

            seed_count = inputs.itemById('seedCount').valueOne
            rib_width = inputs.itemById('minRibWidth').value * 10  # cm to mm
            edge_margin = inputs.itemById('edgeMargin').value * 10
            corner_radius = inputs.itemById('cornerRadius').value * 10
            random_seed = inputs.itemById('randomSeed').value
            density_gradient = inputs.itemById('densityGradient').value

            # Validate face is planar
            if not face.geometry.surfaceType == adsk.core.SurfaceTypes.PlaneSurfaceType:
                ui.messageBox('Please select a planar face. Curved surfaces are not supported.')
                return

            # Get boundary and exclusion circles
            boundary = get_face_boundary(face)
            exclude_circles = get_exclude_circles(hole_entities)

            if len(boundary) < 3:
                ui.messageBox('Could not extract face boundary.')
                return

            # Bounding box
            min_x = min(p[0] for p in boundary)
            max_x = max(p[0] for p in boundary)
            min_y = min(p[1] for p in boundary)
            max_y = max(p[1] for p in boundary)
            bbox = (min_x, min_y, max_x, max_y)

            # Generate seeds
            seeds = generate_seeds(
                boundary, seed_count, edge_margin,
                exclude_circles=exclude_circles,
                density_gradient=density_gradient,
                random_seed=random_seed,
            )

            if not seeds:
                ui.messageBox('No seed points could be generated. '
                              'Try reducing the edge margin or increasing seed count.')
                return

            # Compute Voronoi
            cells = compute_voronoi(seeds, bbox)

            # Clip and offset cells
            clip_rect = (min_x + edge_margin, min_y + edge_margin,
                         max_x - edge_margin, max_y - edge_margin)

            processed_cells = []
            for cell in cells:
                if cell is None:
                    continue

                clipped = clip_polygon(cell, clip_rect)
                if len(clipped) < 3:
                    continue

                offset = offset_polygon(clipped, rib_width / 2.0)
                if offset is None:
                    continue

                if abs(polygon_area(offset)) < 0.5:
                    continue

                processed_cells.append(offset)

            if not processed_cells:
                ui.messageBox('No pattern cells generated. '
                              'Try reducing rib width or edge margin.')
                return

            # Draw pattern in undo group
            design.timeline.markerPosition
            draw_voronoi_pattern(face, processed_cells, corner_radius)

            ui.messageBox(f'Generated {len(processed_cells)} Voronoi cells.\n'
                          f'Use Extrude Cut to create the holes.')

        except Exception:
            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                f'Error generating pattern:\n{traceback.format_exc()}')
