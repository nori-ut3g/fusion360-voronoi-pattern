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


try:
    import adsk.core
    import adsk.fusion
    import json
except Exception as e:
    _log(f'import FAILED: {e}')

ADDIN_DIR = os.path.dirname(os.path.abspath(__file__))
if ADDIN_DIR not in sys.path:
    sys.path.insert(0, ADDIN_DIR)

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
            'hole_margin': 2.0, 'corner_radius': 1.0, 'random_seed': 42,
            'density_gradient': True,
        }


class ValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        try:
            inputs = args.inputs
            face_input = inputs.itemById('targetFace')
            args.areInputsValid = face_input.selectionCount > 0
        except Exception:
            args.areInputsValid = False


class CommandExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        try:
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
                clip_polygon_outside, expand_polygon,
                offset_polygon, polygon_area,
            )
            from lib.seed_generator import generate_seeds
            from lib.sketch_drawer import (
                draw_voronoi_pattern, get_face_boundary,
                get_face_holes, get_exclude_circles,
            )

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
            hole_margin = inputs.itemById('holeMargin').value
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
            face_holes = get_face_holes(face, sketch)

            # Expand each hole polygon outward by hole_margin
            expanded_holes = []
            for hole_poly in face_holes:
                expanded = expand_polygon(hole_poly, hole_margin)
                if expanded is not None:
                    expanded_holes.append(expanded)

            if len(boundary) < 3:
                ui.messageBox('Could not extract face boundary.')
                return

            min_x = min(p[0] for p in boundary)
            max_x = max(p[0] for p in boundary)
            min_y = min(p[1] for p in boundary)
            max_y = max(p[1] for p in boundary)
            bbox = (min_x, min_y, max_x, max_y)

            # Inset boundary for cell clipping (ensures edge margin)
            inset_boundary = offset_polygon(boundary, rib_width / 2.0)
            if inset_boundary is None:
                inset_boundary = boundary

            seeds = generate_seeds(
                boundary, seed_count, edge_margin,
                exclude_circles=exclude_circles,
                exclude_polygons=expanded_holes,
                density_gradient=density_gradient,
                random_seed=random_seed,
            )

            if not seeds:
                ui.messageBox('No seed points generated. Try reducing edge margin.')
                return

            cells = compute_voronoi(seeds, bbox, boundary=boundary)

            # Wide rect clip just to handle far-away Voronoi vertices
            margin = max(max_x - min_x, max_y - min_y)
            wide_rect = (min_x - margin, min_y - margin,
                         max_x + margin, max_y + margin)

            # Progress dialog for UI responsiveness and cancellation
            progress = ui.createProgressDialog()
            progress.cancelButtonText = 'Cancel'
            progress.isBackgroundTranslucent = False
            progress.isCancelButtonShown = True
            n_cells = len(cells)
            progress.show('Voronoi Pattern',
                          'Processing cells...', 0, n_cells + 1, 0)

            processed_cells = []
            for cell_idx, cell in enumerate(cells):
                # Update progress and check cancellation every 5 cells
                if cell_idx % 5 == 0:
                    if progress.wasCancelled:
                        progress.hide()
                        return
                    progress.progressValue = cell_idx
                    progress.message = (f'Processing cell {cell_idx + 1}'
                                        f' of {n_cells}')
                    adsk.doEvents()

                if cell is None:
                    continue
                # First: rough clip to wide bounding box
                clipped = clip_polygon(cell, wide_rect)
                if len(clipped) < 3:
                    continue
                # Then: clip to inset boundary (raw boundary - rib_width/2)
                clipped = clip_polygon_to_boundary(clipped, inset_boundary)
                if len(clipped) < 3:
                    continue
                # Apply offset for rib width
                offset = offset_polygon(clipped, rib_width / 2.0)
                if offset is None:
                    continue
                if abs(polygon_area(offset)) < 0.005:
                    continue
                # Clip cell against expanded hole regions
                skip = False
                for hole_poly in expanded_holes:
                    offset = clip_polygon_outside(offset, hole_poly)
                    if len(offset) < 3:
                        skip = True
                        break
                if skip:
                    continue
                if abs(polygon_area(offset)) < 0.005:
                    continue
                processed_cells.append(offset)

            _log(f'Generated {len(processed_cells)} cells from {len(seeds)} seeds')

            if not processed_cells:
                progress.hide()
                ui.messageBox('No cells generated. Try reducing edge margin.')
                return

            progress.message = 'Drawing pattern...'
            progress.progressValue = n_cells
            adsk.doEvents()

            draw_voronoi_pattern(sketch, processed_cells, corner_radius)

            progress.hide()

            ui.messageBox(f'Generated {len(processed_cells)} Voronoi cells.\n'
                          f'Use Extrude Cut to create the holes.')

        except Exception:
            _log(f'Execute handler ERROR: {traceback.format_exc()}')
            try:
                app = adsk.core.Application.get()
                # Hide progress dialog if it was shown
                try:
                    progress.hide()
                except Exception:
                    pass
                app.userInterface.messageBox(
                    f'Error generating pattern:\n{traceback.format_exc()}')
            except Exception:
                pass


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def __init__(self, defaults):
        super().__init__()
        self.defaults = defaults

    def notify(self, args):
        try:
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
                'holeMargin', 'Hole Margin', 'mm',
                adsk.core.ValueInput.createByReal(
                    d.get('hole_margin', 2.0) * 0.1))

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

        except Exception:
            _log(f'CommandCreated ERROR: {traceback.format_exc()}')
            app = adsk.core.Application.get()
            app.userInterface.messageBox(traceback.format_exc())


def run(context):
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface

        defaults = _load_defaults()

        cmd_def = ui.commandDefinitions.itemById(CMD_ID)
        if cmd_def:
            cmd_def.deleteMe()

        cmd_def = ui.commandDefinitions.addButtonDefinition(
            CMD_ID, CMD_NAME, CMD_DESC)

        on_created = CommandCreatedHandler(defaults)
        cmd_def.commandCreated.add(on_created)
        _handlers.append(on_created)

        tools_tab = ui.allToolbarTabs.itemById('ToolsTab')
        if tools_tab:
            panel = tools_tab.toolbarPanels.itemById('SolidScriptsAddinsPanel')
            if panel:
                existing = panel.controls.itemById(CMD_ID)
                if not existing:
                    panel.controls.addCommand(cmd_def)

        _log('Voronoi Pattern add-in started')

    except Exception:
        _log(f'run() ERROR: {traceback.format_exc()}')
        app = adsk.core.Application.get()
        ui = app.userInterface
        ui.messageBox(f'Failed to start Voronoi Pattern:\n{traceback.format_exc()}')


def stop(context):
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

    except Exception:
        _log(f'stop() ERROR: {traceback.format_exc()}')
