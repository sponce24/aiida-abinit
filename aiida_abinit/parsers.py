"""
AiiDA-abinit output parser. 
"""
from aiida.engine import ExitCode
from aiida.parsers.parser import Parser
from aiida.plugins import CalculationFactory
from aiida.plugins import DataFactory
from aiida.orm import Dict

import abipy.abilab as abilab
from abipy.flowtk import events

StructureData = DataFactory('structure')

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

        #try:
        #    returned = self._parse_trajectory()
        #    if isinstance(returned, StructureData):
        #        self.out('output_structure', returned)
        #    else:  # in case this is an error code
        #        return returned
        #except exceptions.NotExistent:
        #    pass

        return ExitCode(0)


    def _parse_GSR(self):
        """Parser for the Abnit GSR file that contains most information"""

        # Initialize the result dictionary
        result_dict = {"exceeded_walltime": False}

        # Output file - aiida.out
        fname = self.node.get_attribute('output_filename')

        if fname not in self.retrieved.list_object_names():
            return self.exit_codes.ERROR_OUTPUT_STDOUT_MISSING

        # Absolute path of the folder in which files are stored
        path = self.node.get_remote_workdir()

        # Read the output log file for potential errors. 
        parser = events.EventsParser()
        report = parser.parse(path+'/'+fname)
        #
        # Did the run completed ?
        if (not report.run_completed):
            return self.exit_codes.ERROR_OUTPUT_CONTAINS_ABORT

        # Did the run had ERRORS:
        if (len(report.errors) > 0):
            return self.exit_codes.ERROR_OUTPUT_CONTAINS_ABORT

        # Did the run contains WARNINGS:
        if (len(report.warnings) > 0):
            print('Abinit run returned the following WARNINGS')
            for w in report.warnings:
                print(w.message)

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

        gsr = abilab.abiopen(path+'/'+fname)
        result_dict["energy"] = gsr.energy
        result_dict["energy_units"] = "eV" 
        result_dict["pressure"] = gsr.pressure
        result_dict["forces"] = gsr.cart_forces

        self.out("output_parameters", Dict(dict=result_dict))

        return None


