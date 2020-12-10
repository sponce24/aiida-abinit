"""
AiiDA-abinit output parser. 
"""
import abipy.abilab as abilab
import netCDF4 as nc
import numpy as np
from abipy.dynamics.hist import HistFile
from abipy.flowtk import events
from aiida.common import exceptions
from aiida.engine import ExitCode
from aiida.orm import Dict, TrajectoryData, StructureData
from aiida.parsers.parser import Parser
from aiida.plugins import DataFactory
from pymatgen import Element
from pymatgen.core import units

units_suffix = '_units'
default_charge_units = 'e'
default_dipole_units = 'Debye'
default_energy_units = 'eV'
default_force_units = 'ev / angstrom'
default_k_points_units = '1 / angstrom'
default_length_units = 'Angstrom'
default_magnetization_units = 'Bohrmag / cell'
default_polarization_units = 'C / m^2'
default_stress_units = 'GPascal'


class AbinitParser(Parser):
    """
    Basic AiiDA parser for the ouptut of an Abinit calculation.  
    """
    def parse(self, **kwargs):
        """
        Parse outputs, store results in database.
         
        Receives in input a dictionary of retrieved nodes. 
        """
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

        exit_code = self._parse_GSR()
        if exit_code is not None:
            return exit_code

        if is_relaxation:
            exit_code = self._parse_trajectory()  # pylint: disable=assignment-from-none
            if exit_code is not None:
                return exit_code

        return ExitCode(0)

    def _parse_GSR(self):
        """Parser for the Abnit GSR file that contains most information"""
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
            for e in report.errors:
                self.logger.error(e.message)
            return self.exit_codes.ERROR_OUTPUT_CONTAINS_ABORT

        # Did the run contain WARNINGS:
        if len(report.warnings) > 0:
            for w in report.warnings:
                self.logger.warning(w.message)

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
                'abinit_version':
                gsr.abinit_version,
                'cart_stress_tensor':
                gsr.cart_stress_tensor.tolist(),
                'cart_stress_tensor' + units_suffix:
                default_stress_units,
                'is_scf_run':
                bool(gsr.is_scf_run),
                # 'cart_forces': gsr.cart_forces.tolist(),
                # 'cart_forces' + units_suffix: default_force_units,
                'forces':
                gsr.cart_forces.tolist(),  # backwards compatibility
                'forces' + units_suffix:
                default_force_units,
                'energy':
                float(gsr.energy),
                'energy' + units_suffix:
                default_energy_units,
                'e_localpsp':
                float(gsr.energy_terms.e_localpsp),
                'e_localpsp' + units_suffix:
                default_energy_units,
                'e_eigenvalues':
                float(gsr.energy_terms.e_eigenvalues),
                'e_eigenvalues' + units_suffix:
                default_energy_units,
                'e_ewald':
                float(gsr.energy_terms.e_ewald),
                'e_ewald' + units_suffix:
                default_energy_units,
                'e_hartree':
                float(gsr.energy_terms.e_hartree),
                'e_hartree' + units_suffix:
                default_energy_units,
                'e_corepsp':
                float(gsr.energy_terms.e_corepsp),
                'e_corepsp' + units_suffix:
                default_energy_units,
                'e_corepspdc':
                float(gsr.energy_terms.e_corepspdc),
                'e_corepspdc' + units_suffix:
                default_energy_units,
                'e_kinetic':
                float(gsr.energy_terms.e_kinetic),
                'e_kinetic' + units_suffix:
                default_energy_units,
                'e_nonlocalpsp':
                float(gsr.energy_terms.e_nonlocalpsp),
                'e_nonlocalpsp' + units_suffix:
                default_energy_units,
                'e_entropy':
                float(gsr.energy_terms.e_entropy),
                'e_entropy' + units_suffix:
                default_energy_units,
                'entropy':
                float(gsr.energy_terms.entropy),
                'entropy' + units_suffix:
                default_energy_units,
                'e_xc':
                float(gsr.energy_terms.e_xc),
                'e_xc' + units_suffix:
                default_energy_units,
                'e_xcdc':
                float(gsr.energy_terms.e_xcdc),
                'e_xcdc' + units_suffix:
                default_energy_units,
                'e_paw':
                float(gsr.energy_terms.e_paw),
                'e_paw' + units_suffix:
                default_energy_units,
                'e_pawdc':
                float(gsr.energy_terms.e_pawdc),
                'e_pawdc' + units_suffix:
                default_energy_units,
                'e_elecfield':
                float(gsr.energy_terms.e_elecfield),
                'e_elecfield' + units_suffix:
                default_energy_units,
                'e_magfield':
                float(gsr.energy_terms.e_magfield),
                'e_magfield' + units_suffix:
                default_energy_units,
                'e_fermie':
                float(gsr.energy_terms.e_fermie),
                'e_fermie' + units_suffix:
                default_energy_units,
                'e_sicdc':
                float(gsr.energy_terms.e_sicdc),
                'e_sicdc' + units_suffix:
                default_energy_units,
                'e_exactX':
                float(gsr.energy_terms.e_exactX),
                'e_exactX' + units_suffix:
                default_energy_units,
                'h0':
                float(gsr.energy_terms.h0),
                'h0' + units_suffix:
                default_energy_units,
                'e_electronpositron':
                float(gsr.energy_terms.e_electronpositron),
                'e_electronpositron' + units_suffix:
                default_energy_units,
                'edc_electronpositron':
                float(gsr.energy_terms.edc_electronpositron),
                'edc_electronpositron' + units_suffix:
                default_energy_units,
                'e0_electronpositron':
                float(gsr.energy_terms.e0_electronpositron),
                'e0_electronpositron' + units_suffix:
                default_energy_units,
                'e_monopole':
                float(gsr.energy_terms.e_monopole),
                'e_monopole' + units_suffix:
                default_energy_units,
                'pressure':
                float(gsr.pressure),
                'pressure' + units_suffix:
                default_stress_units
            }
            try:
                # will return an integer 0 if non-magnetic calculation is run; convert it to a float
                total_magnetization = float(gsr.ebands.get_collinear_mag())
                gsr_data['total_magnetization'] = total_magnetization
                gsr_data['total_magnetization' + units_suffix] = default_magnetization_units
            except ValueError as valerr:
                # get_collinear_mag will raise ValueError if it doesn't know what to do
                if 'Cannot calculate collinear magnetization' in valerr.args[0]:
                    pass
                else:
                    raise valerr


        self.out("output_parameters", Dict(dict=gsr_data))

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

        with HistFile(path + '/' + fname) as hf:
            structures = hf.structures

        output_structure = StructureData(pymatgen=structures[-1])

        with nc.Dataset(path + '/' + fname, 'r') as ds:  # pylint: disable=no-member
            n_steps = ds.dimensions['time'].size
            energy_ha = ds.variables['etotal'][:].data  # Ha
            energy_kin_ha = ds.variables['ekin'][:].data  # Ha
            forces_cart_ha_bohr = ds.variables['fcart'][:, :, :].data  # Ha/bohr
            positions_cart_bohr = ds.variables['xcart'][:, :, :].data  # bohr
            stress_voigt = ds.variables['strten'][:, :].data  # Ha/bohr^3

        stepids = np.arange(n_steps)
        symbols = np.array([specie.symbol for specie in structures[0].species],
                           dtype='<U2')
        cells = np.array(
            [structure.lattice.matrix for structure in structures]).reshape(
                (n_steps, 3, 3))
        energy = energy_ha * units.Ha_to_eV
        energy_kin = energy_kin_ha * units.Ha_to_eV
        forces = forces_cart_ha_bohr * units.Ha_to_eV / units.bohr_to_ang
        positions = positions_cart_bohr * units.bohr_to_ang
        stress = np.array([_voigt_to_tensor(sv) for sv in stress_voigt
                           ]) * units.Ha_to_eV / units.bohr_to_ang**3
        total_force = np.array([np.sum(f) for f in forces_cart_ha_bohr
                                ]) * units.Ha_to_eV / units.bohr_to_ang

        output_trajectory = TrajectoryData()
        output_trajectory.set_trajectory(stepids=stepids,
                                         cells=cells,
                                         symbols=symbols,
                                         positions=positions)
        output_trajectory.set_array("energy", energy)  # eV
        output_trajectory.set_array("energy_kin", energy_kin)  # eV
        output_trajectory.set_array("forces", forces)  # eV/angstrom
        output_trajectory.set_array("stress", stress)  # eV/angstrom^3
        output_trajectory.set_array("total_force", total_force)  # eV/angstrom

        self.out("output_trajectory", output_trajectory)
        self.out("output_structure", output_structure)
