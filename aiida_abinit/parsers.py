# -*- coding: utf-8 -*-
"""AiiDA-abinit output parser."""
import abipy.abilab as abilab
import netCDF4 as nc
import numpy as np
from pymatgen.core import units
from abipy.dynamics.hist import HistFile
from abipy.flowtk import events

from aiida.common import exceptions
from aiida.engine import ExitCode
from aiida.orm import Dict, StructureData, TrajectoryData
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
        ionmov = self.node.inputs['parameters'].get_dict().get('ionmov', 0)
        optcell = self.node.inputs['parameters'].get_dict().get('optcell', 0)

        if ionmov == 0 and optcell == 0:
            is_relaxation = False
        else:
            is_relaxation = True

        try:
            _ = self.retrieved
        except exceptions.NotExistent:
            return self.exit_codes.ERROR_NO_RETRIEVED_TEMPORARY_FOLDER

        exit_code = self._parse_gsr()
        if exit_code is not None:
            return exit_code

        if is_relaxation:
            exit_code = self._parse_trajectory()  # pylint: disable=assignment-from-none
            if exit_code is not None:
                return exit_code

        return ExitCode(0)

    def _parse_gsr(self):
        """Abinit GSR parser."""
        ## STDOUT ##
        # Output file - aiida.out
        fname = self.node.get_attribute('output_filename')
        # Absolute path of the folder in which files are stored
        path = self.node.get_remote_workdir()

        if fname not in self.retrieved.list_object_names():
            return self.exit_codes.ERROR_MISSING_OUTPUT_FILES

        # Read the output log file for potential errors.
        parser = events.EventsParser()
        report = parser.parse(path + '/' + fname)

        # Did the run have ERRORS:
        if len(report.errors) > 0:
            for error in report.errors:
                self.logger.error(error.message)
            return self.exit_codes.ERROR_OUTPUT_CONTAINS_ABORT

        # Did the run contain WARNINGS:
        if len(report.warnings) > 0:
            for warning in report.warnings:
                self.logger.warning(warning.message)

        # Did the run complete
        if not report.run_completed:
            return self.exit_codes.ERROR_OUTPUT_CONTAINS_ABORT

        ## GSR ##
        # Output GSR Abinit NetCDF file - Default name is aiidao_GSR.nc
        fname = self.node.get_attribute('output_gsr')
        # Absolute path of the folder in which aiidao_GSR.nc is stored
        path = self.node.get_remote_workdir()

        if fname not in self.retrieved.list_object_names():
            return self.exit_codes.ERROR_MISSING_OUTPUT_FILES

        with abilab.abiopen(path + '/' + fname) as gsr:
            gsr_data = {
                'abinit_version': gsr.abinit_version,
                'cart_stress_tensor': gsr.cart_stress_tensor.tolist(),
                'cart_stress_tensor' + UNITS_SUFFIX: DEFAULT_STRESS_UNITS,
                'is_scf_run': bool(gsr.is_scf_run),
                # 'cart_forces': gsr.cart_forces.tolist(),
                # 'cart_forces' + units_suffix: DEFAULT_FORCE_UNITS,
                'forces': gsr.cart_forces.tolist(),  # backwards compatibility
                'forces' + UNITS_SUFFIX: DEFAULT_FORCE_UNITS,
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
            try:
                # will return an integer 0 if non-magnetic calculation is run; convert it to a float
                total_magnetization = float(gsr.ebands.get_collinear_mag())
                gsr_data['total_magnetization'] = total_magnetization
                gsr_data['total_magnetization' + UNITS_SUFFIX] = DEFAULT_MAGNETIZATION_UNITS
            except ValueError as valerr:
                # get_collinear_mag will raise ValueError if it doesn't know what to do
                if 'Cannot calculate collinear magnetization' in valerr.args[0]:
                    pass
                else:
                    raise valerr

        self.out('output_parameters', Dict(dict=gsr_data))

    def _parse_trajectory(self):
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

        # Absolute path of the folder in which aiidao_GSR.nc is stored
        path = self.node.get_remote_workdir()
        # HIST Abinit NetCDF file - Default name is aiidao_HIST.nc
        fname = self.node.get_attribute('output_hist')

        if fname not in self.retrieved.list_object_names():
            return self.exit_codes.ERROR_MISSING_OUTPUT_FILES

        with HistFile(path + '/' + fname) as hist_file:
            structures = hist_file.structures

        output_structure = StructureData(pymatgen=structures[-1])

        with nc.Dataset(path + '/' + fname, 'r') as data_set:  # pylint: disable=no-member
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
