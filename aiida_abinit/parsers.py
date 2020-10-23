"""
AiiDA-abinit output parser. 
"""
from aiida.engine import ExitCode
from aiida.parsers.parser import Parser
from aiida.common import exceptions
from aiida.plugins import DataFactory
from aiida.orm import Dict

import abipy.abilab as abilab
from abipy.flowtk import events
from abipy.dynamics.hist import HistFile
from pymatgen.core.trajectory import Trajectory
import netCDF4 as nc
import numpy as np

StructureData = DataFactory('structure')
ArrayData = DataFactory('array')

class AbinitParser(Parser):
    """
    Basic AiiDA parser for the ouptut of an Abinit calculation.  
    """

    def parse(self, **kwargs):
        """
        Parse outputs, store results in database.
         
        Receives in input a dictionary of retrieved nodes. 
        """

        try:
            _ = self.retrieved
        except exceptions.NotExistent:
            return self.exit_codes.ERROR_NO_RETRIEVED_FOLDER

        exit_code = self._parse_GSR()
        if exit_code is not None:
            return exit_code

        try:
            returned = self._parse_trajectory()
            if isinstance(returned, StructureData):
                self.out('output_structure', returned)
            else:  # in case this is an error code
                return returned
        except exceptions.NotExistent:
            pass

        return ExitCode(0)

    def _parse_GSR(self):
        """Parser for the Abnit GSR file that contains most information"""

        # Initialize the result dictionary
        result_dict = {}

        # Output file - aiida.out
        fname = self.node.get_attribute('output_filename')

        if fname not in self.retrieved.list_object_names():
            return self.exit_codes.ERROR_OUTPUT_STDOUT_MISSING

        # Absolute path of the folder in which files are stored
        path = self.node.get_remote_workdir()

        # Read the output log file for potential errors. 
        parser = events.EventsParser()
        report = parser.parse(path+'/'+fname)

        # Did the run had ERRORS:
        if len(report.errors) > 0:
            for e in report.errors:
                self.logger.error(e.message)
            return self.exit_codes.ERROR_OUTPUT_CONTAINS_ABORT

        # Did the run completed ?
        if not report.run_completed:
            return self.exit_codes.ERROR_OUTPUT_CONTAINS_ABORT

        # Did the run contains WARNINGS:
        if len(report.warnings) > 0:
            for w in report.warnings:
                self.logger.warning(w.message)

        # Extract the text content from the output
        #try:
        #    output_string = self.retrieved.get_object_content(fname)
        #except IOError:
        #    return self.exit_codes.ERROR_OUTPUT_STDOUT_READ

        # Output GSR Abinit NetCDF file - Default name is aiidao_GSR.nc 
        fname = self.node.get_attribute('output_gsr')

        if fname not in self.retrieved.list_object_names():
            return self.exit_codes.ERROR_OUTPUT_STDOUT_MISSING

        # Absolute path of the folder in which aiidao_GSR.nc is stored
        path = self.node.get_remote_workdir()

        with abilab.abiopen(path+'/'+fname) as gsr:
            result_dict["energy"] = gsr.energy
            result_dict["energy_units"] = "eV"
            result_dict["pressure"] = gsr.pressure
            result_dict["forces"] = gsr.cart_forces

        self.out("output_parameters", Dict(dict=result_dict))

        return None

    def _parse_trajectory(self):
        """Abinit trajectory parser."""

        # HIST Abinit NetCDF file - Default name is aiidao_HIST.nc 
        fname = self.node.get_attribute('output_hist')

        if fname not in self.retrieved.list_object_names():
            return self.exit_codes.ERROR_OUTPUT_STDOUT_MISSING

        # Absolute path of the folder in which aiidao_GSR.nc is stored
        path = self.node.get_remote_workdir()

        with HistFile(path+'/'+fname) as h:
            traj_struct = Trajectory.from_structures(h.structures)
            n_steps = len(h.structures)

        # AiiDA trajectory
        output_trajectory = ArrayData()

        name_spec = np.array([site.specie.symbol for site in traj_struct.get_structure(0).sites])

        cells = np.zeros((n_steps, 3, 3))
        positions = np.zeros((n_steps, len(name_spec), 3))
        for i in range(n_steps):
            structure = traj_struct.get_structure(i)
            cells[i, :, :] = structure.lattice.matrix
            positions[i, :, :] = np.array([site.coords for site in structure.sites])
 
        output_trajectory.set_array("atomic_species_name", name_spec)
        output_trajectory.set_array("cells", cells)
        output_trajectory.set_array("postitions", positions)

        stress = np.zeros((n_steps, 3, 3)) 

        root = nc.Dataset(path+'/'+fname,'r')
        stress_voigt = root.variables['strten'][:,:].data
        stress[:, 0, 0] = stress_voigt[:, 0] 
        stress[:, 1, 1] = stress_voigt[:, 1] 
        stress[:, 2, 2] = stress_voigt[:, 2] 
        stress[:, 1, 2] = stress_voigt[:, 3] 
        stress[:, 0, 2] = stress_voigt[:, 4] 
        stress[:, 0, 1] = stress_voigt[:, 5] 
        stress[:, 2, 1] = stress[:, 1, 2]
        stress[:, 2, 0] = stress[:, 0, 2]
        stress[:, 1, 0] = stress[:, 0, 1]

        energy = root.variables['etotal'][:].data
        forces_cart = root.variables['fcart'][:,:,:].data

        output_trajectory.set_array("energy", energy)
        output_trajectory.set_array("forces", forces_cart)
        output_trajectory.set_array("stress", stress)

        self.out("output_trajectory", output_trajectory)

        return None


