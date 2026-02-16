import os
import sys
import traceback

# File-based debug logging (writes to addin directory)
_LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'debug.log')


def _log(msg):
    try:
        with open(_LOG_PATH, 'a') as f:
            f.write(msg + '\n')
    except Exception:
        pass


_log('--- Module load start ---')

try:
    import adsk.core
    _log('adsk.core imported OK')
except Exception as e:
    _log(f'adsk.core import FAILED: {e}')

try:
    import adsk.fusion
    _log('adsk.fusion imported OK')
except Exception as e:
    _log(f'adsk.fusion import FAILED: {e}')

try:
    import json
    _log('json imported OK')
except Exception as e:
    _log(f'json import FAILED: {e}')

ADDIN_DIR = os.path.dirname(os.path.abspath(__file__))
if ADDIN_DIR not in sys.path:
    sys.path.insert(0, ADDIN_DIR)
_log(f'ADDIN_DIR={ADDIN_DIR}')
_log(f'sys.path[0]={sys.path[0]}')

_handlers = []

CMD_ID = 'voronoiPatternCmd'
CMD_NAME = 'Voronoi Pattern'
CMD_DESC = 'Generate Voronoi lightening hole pattern on a face'


def _load_defaults():
    config_path = os.path.join(ADDIN_DIR, 'config', 'defaults.json')
    try:
        with open(config_path, 'r') as f:
            return json.load(f)
    except Exception:
        return {
            'seed_count': 40, 'min_rib_width': 3.0, 'edge_margin': 5.0,
            'corner_radius': 1.0, 'random_seed': 42, 'density_gradient': True,
        }


_log('Defining ValidateInputsHandler...')


class ValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            inputs = args.inputs
            face_input = inputs.itemById('targetFace')
            args.areInputsValid = face_input.selectionCount > 0
        except Exception:
            args.areInputsValid = False


_log('Defining CommandExecuteHandler...')


class CommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
            _log('Execute handler: importing libs...')
            import importlib
            import lib.polygon
            import lib.voronoi
            import lib.seed_generator
            import lib.sketch_drawer
            importlib.reload(lib.polygon)
            importlib.reload(lib.voronoi)
            importlib.reload(lib.seed_generator)
            importlib.reload(lib.sketch_drawer)

            from lib.voronoi import compute_voronoi
            from lib.polygon import (
                clip_polygon, clip_polygon_to_boundary,
                offset_polygon, polygon_area,
                polygon_centroid, point_in_polygon,
            )
            from lib.seed_generator import generate_seeds
            from lib.sketch_drawer import (
                draw_voronoi_pattern, get_face_boundary, get_exclude_circles,
            )
            _log('Execute handler: imports OK')

            app = adsk.core.Application.get()
            design = adsk.fusion.Design.cast(app.activeProduct)
            ui = app.userInterface
            inputs = args.command.commandInputs

            face_input = inputs.itemById('targetFace')
            face = adsk.fusion.BRepFace.cast(face_input.selection(0).entity)

            holes_input = inputs.itemById('excludeHoles')
            hole_entities = []
            for i in range(holes_input.selectionCount):
                hole_entities.append(holes_input.selection(i).entity)

            seed_count = inputs.itemById('seedCount').valueOne
            # Values are already in cm (Fusion internal unit)
            rib_width = inputs.itemById('minRibWidth').value
            edge_margin = inputs.itemById('edgeMargin').value
            corner_radius = inputs.itemById('cornerRadius').value
            random_seed = inputs.itemById('randomSeed').value
            density_gradient = inputs.itemById('densityGradient').value

            if face.geometry.surfaceType != adsk.core.SurfaceTypes.PlaneSurfaceType:
                ui.messageBox('Please select a planar face.')
                return

            # Create sketch first, then extract boundary in sketch space
            root = design.rootComponent
            sketch = root.sketches.add(face)

            boundary = get_face_boundary(face, sketch)
            exclude_circles = get_exclude_circles(hole_entities, sketch)

            if len(boundary) < 3:
                ui.messageBox('Could not extract face boundary.')
                return

            _log(f'boundary: {len(boundary)} points')
            _log(f'boundary area: {polygon_area(boundary)}')

            min_x = min(p[0] for p in boundary)
            max_x = max(p[0] for p in boundary)
            min_y = min(p[1] for p in boundary)
            max_y = max(p[1] for p in boundary)
            bbox = (min_x, min_y, max_x, max_y)
            _log(f'bbox: {bbox}')

            seeds = generate_seeds(
                boundary, seed_count, edge_margin,
                exclude_circles=exclude_circles,
                density_gradient=density_gradient,
                random_seed=random_seed,
            )
            _log(f'seeds: {len(seeds)}')

            if not seeds:
                ui.messageBox('No seed points generated. Try reducing edge margin.')
                return

            cells = compute_voronoi(seeds, bbox)
            _log(f'voronoi cells: {len(cells)}')

            # Wide rect clip just to handle far-away Voronoi vertices
            margin = max(max_x - min_x, max_y - min_y)
            wide_rect = (min_x - margin, min_y - margin,
                         max_x + margin, max_y + margin)

            processed_cells = []
            for cell in cells:
                if cell is None:
                    continue
                # First: rough clip to wide bounding box
                clipped = clip_polygon(cell, wide_rect)
                if len(clipped) < 3:
                    continue
                # Then: precise clip to actual face boundary
                clipped = clip_polygon_to_boundary(clipped, boundary)
                if len(clipped) < 3:
                    continue
                # Apply offset for rib width
                offset = offset_polygon(clipped, rib_width / 2.0)
                if offset is None:
                    continue
                if abs(polygon_area(offset)) < 0.005:
                    continue
                processed_cells.append(offset)

            _log(f'results: {len(processed_cells)} cells')

            if not processed_cells:
                ui.messageBox('No cells generated. Try reducing edge margin.')
                return

            draw_voronoi_pattern(sketch, processed_cells, corner_radius)

            ui.messageBox(f'Generated {len(processed_cells)} Voronoi cells.\n'
                          f'Use Extrude Cut to create the holes.')

        except Exception:
            _log(f'Execute handler ERROR: {traceback.format_exc()}')
            app = adsk.core.Application.get()
            app.userInterface.messageBox(
                f'Error generating pattern:\n{traceback.format_exc()}')


_log('Defining CommandCreatedHandler...')


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, defaults):
        super().__init__()
        self.defaults = defaults

    def notify(self, args):
        try:
            _log('CommandCreated handler called')
            cmd = adsk.core.Command.cast(args.command)
            inputs = cmd.commandInputs
            d = self.defaults

            face_input = inputs.addSelectionInput(
                'targetFace', 'Target Face',
                'Select a planar face for the pattern')
            face_input.addSelectionFilter('PlanarFaces')
            face_input.setSelectionLimits(1, 1)

            holes_input = inputs.addSelectionInput(
                'excludeHoles', 'Exclude Holes (optional)',
                'Select circular edges to exclude as mount holes')
            holes_input.addSelectionFilter('CircularEdges')
            holes_input.setSelectionLimits(0, 0)
            holes_input.isVisible = True

            inputs.addIntegerSliderCommandInput(
                'seedCount', 'Seed Count', 10, 200, False)
            inputs.itemById('seedCount').valueOne = d.get('seed_count', 40)

            inputs.addValueInput(
                'minRibWidth', 'Min Rib Width', 'mm',
                adsk.core.ValueInput.createByReal(
                    d.get('min_rib_width', 3.0) * 0.1))

            inputs.addValueInput(
                'edgeMargin', 'Edge Margin', 'mm',
                adsk.core.ValueInput.createByReal(
                    d.get('edge_margin', 5.0) * 0.1))

            inputs.addValueInput(
                'cornerRadius', 'Corner Radius', 'mm',
                adsk.core.ValueInput.createByReal(
                    d.get('corner_radius', 1.0) * 0.1))

            inputs.addIntegerSpinnerCommandInput(
                'randomSeed', 'Random Seed', 0, 9999, 1,
                d.get('random_seed', 42))

            inputs.addBoolValueInput(
                'densityGradient', 'Density Gradient',
                True, '', d.get('density_gradient', True))

            on_execute = CommandExecuteHandler()
            cmd.execute.add(on_execute)
            _handlers.append(on_execute)

            on_validate = ValidateInputsHandler()
            cmd.validateInputs.add(on_validate)
            _handlers.append(on_validate)

            _log('CommandCreated handler done OK')

        except Exception:
            _log(f'CommandCreated ERROR: {traceback.format_exc()}')
            app = adsk.core.Application.get()
            app.userInterface.messageBox(traceback.format_exc())


_log('Classes defined OK')


def run(context):
    _log('run() called')
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        defaults = _load_defaults()
        _log(f'defaults loaded: {defaults}')

        cmd_def = ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()
            _log('old command definition deleted')

        cmd_def = ui.commandDefinitions.addButtonDefinition(
            CMD_ID, CMD_NAME, CMD_DESC)
        _log('button definition created')

        on_created = CommandCreatedHandler(defaults)
        cmd_def.commandCreated.add(on_created)
        _handlers.append(on_created)
        _log('commandCreated handler added')

        tools_tab = ui.allToolbarTabs.itemById('ToolsTab')
        if tools_tab:
            panel = tools_tab.toolbarPanels.itemById('SolidScriptsAddinsPanel')
            if panel:
                existing = panel.controls.itemById(CMD_ID)
                if not existing:
                    panel.controls.addCommand(cmd_def)
                    _log('command added to toolbar panel')
                else:
                    _log('command already exists in panel')
            else:
                _log('SolidScriptsAddinsPanel not found')
        else:
            _log('ToolsTab not found')

        _log('run() completed OK')

    except Exception:
        _log(f'run() ERROR: {traceback.format_exc()}')
        app = adsk.core.Application.get()
        ui = app.userInterface
        ui.messageBox(f'Failed to start Voronoi Pattern:\n{traceback.format_exc()}')


def stop(context):
    _log('stop() called')
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        tools_tab = ui.allToolbarTabs.itemById('ToolsTab')
        if tools_tab:
            panel = tools_tab.toolbarPanels.itemById('SolidScriptsAddinsPanel')
            if panel:
                ctrl = panel.controls.itemById(CMD_ID)
                if ctrl:
                    ctrl.deleteMe()

        cmd_def = ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()

        _log('stop() completed OK')

    except Exception:
        _log(f'stop() ERROR: {traceback.format_exc()}')


_log('--- Module load complete ---')
