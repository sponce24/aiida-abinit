# -*- coding: utf-8 -*-
"""AiiDA-abinit output parser."""
from os import path
from tempfile import TemporaryDirectory
import logging

from abipy.dynamics.hist import HistFile
from abipy.flowtk import events
from abipy import abilab
import netCDF4 as nc
import numpy as np
from pymatgen.core import units

from aiida.common.exceptions import NotExistent
from aiida.engine import ExitCode
from aiida.orm import BandsData, Dict, StructureData, TrajectoryData
from aiida.parsers.parser import Parser

UNITS_SUFFIX = '_units'
DEFAULT_CHARGE_UNITS = 'e'
DEFAULT_DIPOLE_UNITS = 'Debye'
DEFAULT_ENERGY_UNITS = 'eV'
DEFAULT_FORCE_UNITS = 'eV / Angstrom'
DEFAULT_K_POINTS_UNITS = '1 / Angstrom'
DEFAULT_LENGTH_UNITS = 'Angstrom'
DEFAULT_MAGNETIZATION_UNITS = 'Bohr mag. / cell'
DEFAULT_POLARIZATION_UNITS = 'C / m^2'
DEFAULT_STRESS_UNITS = 'GPa'


class AbinitParser(Parser):
    """Basic parser for the ouptut of an Abinit calculation."""

    def parse(self, **kwargs):
        """Parse outputs, store results in database."""
        try:
            settings = self.node.inputs.settings.get_dict()
        except NotExistent:
            settings = {}

        # Look for optional settings input node and potential 'parser_options' dictionary within it
        parser_options = settings.get('parser_options', None)
        if parser_options is not None:
            error_on_warning = parser_options.get(error_on_warning, False)
            report_comments = parser_options.get(report_comments, True)
        else:
            error_on_warning = False
            report_comments = True

        try:
            retrieved = self.retrieved
        except NotExistent:
            return self.exit_codes.ERROR_NO_RETRIEVED_FOLDER

        parameters = self.node.inputs.parameters.get_dict()
        ionmov = parameters.get('ionmov', 0)
        optcell = parameters.get('optcell', 0)
        is_relaxation = ionmov != 0 or optcell != 0

        prefix = self.node.get_attribute('prefix')
        retrieve_list = self.node.get_attribute('retrieve_list')
        output_filename = self.node.get_attribute('output_filename')
        with TemporaryDirectory() as dirpath:
            retrieved.copy_tree(dirpath)

            if output_filename in retrieve_list:
                stdout_filepath = path.join(dirpath, output_filename)
                exit_code = self._parse_stdout(
                    stdout_filepath, error_on_warning=error_on_warning, report_comments=report_comments
                )
                if exit_code is not None:
                    return exit_code
            else:
                return self.exit_codes.ERROR_OUTPUT_MISSING

            if f'{prefix}o_GSR.nc' in retrieve_list:
                gsr_filepath = path.join(dirpath, f'{prefix}o_GSR.nc')
                self._parse_gsr(gsr_filepath, is_relaxation)
            else:
                return self.exit_codes.ERROR_MISSING_GSR_OUTPUT_FILE

            if f'{prefix}o_HIST.nc' in retrieve_list:
                hist_filepath = path.join(dirpath, f'{prefix}o_HIST.nc')
                self._parse_trajectory(hist_filepath)
            else:
                if is_relaxation:
                    return self.exit_codes.ERROR_MISSING_HIST_OUTPUT_FILE

        return ExitCode(0)

    def _report_message(self, level, message):
        if not isinstance(level, int):
            level = getattr(logging, level.upper(), None)
        if '\n' in message:
            message_lines = message.strip().split('\n')
            message_lines = [f'\t{line}' for line in message_lines]
            message = '\n' + '\n'.join(message_lines)
        self.logger.log(level, '%s', message)

    def _parse_stdout(self, filepath, error_on_warning=False, report_comments=True):
        """Abinit stdout parser."""
        # Read the output log file for potential errors.
        parser = events.EventsParser()
        try:
            report = parser.parse(filepath)
        except:  # pylint: disable=bare-except
            return self.exit_codes.ERROR_OUTPUT_PARSE

        # Handle `ERROR`s
        if len(report.errors) > 0:
            for error in report.errors:
                self._report_message('ERROR', error.message)
            return self.exit_codes.ERROR_OUTPUT_CONTAINS_ERRORS

        # Handle `WARNING`s
        if len(report.warnings) > 0:
            for warning in report.warnings:
                self._report_message('WARNING', warning.message)
            # Need to figure out how to handle the ordering of errors.
            # In theory, this is restartable, but it can occur alongside out
            # of walltime, in which case it probably _isn't_ restartable.
            # for warning in report.warnings:
            #     if ('nstep' in warning.message and
            #         'was not enough SCF cycles to converge.' in warning.message):
            #         return self.exit_codes.ERROR_SCF_CONVERGENCE_NOT_REACHED
            if error_on_warning:
                # This can be quite harsh; inefficient k-point parallelization can cause
                # a non-zero exit in this case.
                return self.exit_codes.ERROR_OUTPUT_CONTAINS_WARNINGS

        # Handle `COMMENT`s
        if len(report.comments) > 0:
            if report_comments:
                self.logger.setLevel('INFO')
                for comment in report.comments:
                    self._report_message('INFO', comment.message)
            for comment in report.comments:
                if ('Approaching time limit' in comment.message and 'Will exit istep loop' in comment.message):
                    return self.exit_codes.ERROR_OUT_OF_WALLTIME

        # Did the run complete?
        if not report.run_completed:
            return self.exit_codes.ERROR_RUN_NOT_COMPLETED

    def _parse_gsr(self, filepath, is_relaxation):
        """Abinit GSR parser."""
        # abipy.electrons.gsr.GsrFile has a method `from_binary_string`;
        # could try to use this instead of copying the files
        with abilab.abiopen(filepath) as gsr:
            gsr_data = {
                'abinit_version': gsr.abinit_version,
                'nband': gsr.nband,
                'nelect': gsr.nelect,
                'nkpt': gsr.nkpt,
                'nspden': gsr.nspden,
                'nspinor': gsr.nspinor,
                'nsppol': gsr.nsppol,
                'cart_stress_tensor': gsr.cart_stress_tensor.tolist(),
                'cart_stress_tensor' + UNITS_SUFFIX: DEFAULT_STRESS_UNITS,
                'is_scf_run': bool(gsr.is_scf_run),
                'cart_forces': gsr.cart_forces.tolist(),
                'cart_forces' + UNITS_SUFFIX: DEFAULT_FORCE_UNITS,
                # 'forces': gsr.cart_forces.tolist(),  # backwards compatibility
                # 'forces' + UNITS_SUFFIX: DEFAULT_FORCE_UNITS,
                'energy': float(gsr.energy),
                'energy' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_localpsp': float(gsr.energy_terms.e_localpsp),
                'e_localpsp' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_eigenvalues': float(gsr.energy_terms.e_eigenvalues),
                'e_eigenvalues' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_ewald': float(gsr.energy_terms.e_ewald),
                'e_ewald' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_hartree': float(gsr.energy_terms.e_hartree),
                'e_hartree' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_corepsp': float(gsr.energy_terms.e_corepsp),
                'e_corepsp' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_corepspdc': float(gsr.energy_terms.e_corepspdc),
                'e_corepspdc' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_kinetic': float(gsr.energy_terms.e_kinetic),
                'e_kinetic' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_nonlocalpsp': float(gsr.energy_terms.e_nonlocalpsp),
                'e_nonlocalpsp' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_entropy': float(gsr.energy_terms.e_entropy),
                'e_entropy' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'entropy': float(gsr.energy_terms.entropy),
                'entropy' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_xc': float(gsr.energy_terms.e_xc),
                'e_xc' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_xcdc': float(gsr.energy_terms.e_xcdc),
                'e_xcdc' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_paw': float(gsr.energy_terms.e_paw),
                'e_paw' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_pawdc': float(gsr.energy_terms.e_pawdc),
                'e_pawdc' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_elecfield': float(gsr.energy_terms.e_elecfield),
                'e_elecfield' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_magfield': float(gsr.energy_terms.e_magfield),
                'e_magfield' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_fermie': float(gsr.energy_terms.e_fermie),
                'e_fermie' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_sicdc': float(gsr.energy_terms.e_sicdc),
                'e_sicdc' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_exactX': float(gsr.energy_terms.e_exactX),
                'e_exactX' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'h0': float(gsr.energy_terms.h0),
                'h0' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_electronpositron': float(gsr.energy_terms.e_electronpositron),
                'e_electronpositron' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'edc_electronpositron': float(gsr.energy_terms.edc_electronpositron),
                'edc_electronpositron' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e0_electronpositron': float(gsr.energy_terms.e0_electronpositron),
                'e0_electronpositron' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'e_monopole': float(gsr.energy_terms.e_monopole),
                'e_monopole' + UNITS_SUFFIX: DEFAULT_ENERGY_UNITS,
                'pressure': float(gsr.pressure),
                'pressure' + UNITS_SUFFIX: DEFAULT_STRESS_UNITS
            }
            structure = StructureData(pymatgen=gsr.structure)

            try:
                # Will return an integer 0 if non-magnetic calculation is run; convert it to a float
                total_magnetization = float(gsr.ebands.get_collinear_mag())
                gsr_data['total_magnetization'] = total_magnetization
                gsr_data['total_magnetization' + UNITS_SUFFIX] = DEFAULT_MAGNETIZATION_UNITS
            except ValueError as exc:
                # `get_collinear_mag`` will raise ValueError if it doesn't know what to do
                if 'Cannot calculate collinear magnetization' in exc.args[0]:
                    pass
                else:
                    raise exc

            try:
                bands_data = BandsData()
                bands_data.set_kpoints(gsr.ebands.kpoints.get_cart_coords())
                bands_data.set_bands(np.array(gsr.ebands.eigens), units=str(gsr.ebands.eigens.unit))
                self.out('output_bands', bands_data)
            # HACK: refine this exception catch
            except:  # pylint: disable=bare-except
                pass

        self.out('output_parameters', Dict(dict=gsr_data))
        if not is_relaxation:
            self.out('output_structure', structure)

    def _parse_trajectory(self, filepath):
        """Abinit trajectory parser."""

        def _voigt_to_tensor(voigt):
            tensor = np.zeros((3, 3))
            tensor[0, 0] = voigt[0]
            tensor[1, 1] = voigt[1]
            tensor[2, 2] = voigt[2]
            tensor[1, 2] = voigt[3]
            tensor[0, 2] = voigt[4]
            tensor[0, 1] = voigt[5]
            tensor[2, 1] = tensor[1, 2]
            tensor[2, 0] = tensor[0, 2]
            tensor[1, 0] = tensor[0, 1]
            return tensor

        with HistFile(filepath) as hist_file:
            structures = hist_file.structures

        output_structure = StructureData(pymatgen=structures[-1])

        with nc.Dataset(filepath, 'r') as data_set:  # pylint: disable=no-member
            n_steps = data_set.dimensions['time'].size
            energy_ha = data_set.variables['etotal'][:].data  # Ha
            energy_kin_ha = data_set.variables['ekin'][:].data  # Ha
            forces_cart_ha_bohr = data_set.variables['fcart'][:, :, :].data  # Ha/bohr
            positions_cart_bohr = data_set.variables['xcart'][:, :, :].data  # bohr
            stress_voigt = data_set.variables['strten'][:, :].data  # Ha/bohr^3

        stepids = np.arange(n_steps)
        symbols = np.array([specie.symbol for specie in structures[0].species], dtype='<U2')
        cells = np.array([structure.lattice.matrix for structure in structures]).reshape((n_steps, 3, 3))
        energy = energy_ha * units.Ha_to_eV
        energy_kin = energy_kin_ha * units.Ha_to_eV
        forces = forces_cart_ha_bohr * units.Ha_to_eV / units.bohr_to_ang
        positions = positions_cart_bohr * units.bohr_to_ang
        stress = np.array([_voigt_to_tensor(sv) for sv in stress_voigt]) * units.Ha_to_eV / units.bohr_to_ang**3
        total_force = np.array([np.sum(f) for f in forces_cart_ha_bohr]) * units.Ha_to_eV / units.bohr_to_ang

        output_trajectory = TrajectoryData()
        output_trajectory.set_trajectory(stepids=stepids, cells=cells, symbols=symbols, positions=positions)
        output_trajectory.set_array('energy', energy)  # eV
        output_trajectory.set_array('energy_kin', energy_kin)  # eV
        output_trajectory.set_array('forces', forces)  # eV/angstrom
        output_trajectory.set_array('stress', stress)  # eV/angstrom^3
        output_trajectory.set_array('total_force', total_force)  # eV/angstrom

        self.out('output_trajectory', output_trajectory)
        self.out('output_structure', output_structure)
