"""
Calculations provided by aiida_abinit.

Register calculations via the "aiida.calculations" entry point in setup.json.
"""
from aiida import orm
from aiida.common import datastructures
from aiida.engine import CalcJob
from aiida.orm import SinglefileData
from aiida.plugins import DataFactory

DiffParameters = DataFactory('abinit')


class AbinitCalculation(CalcJob):
    """
    AiiDA calculation plugin wrapping the abinit executable.

    Simple AiiDA plugin wrapper for running a basic Abinit DFT calculation.
    """
    @classmethod
    def define(cls, spec):
        """Define inputs and outputs of the calculation."""
        # yapf: disable
        super(AbinitCalculation, cls).define(spec)

        # Inputs
        spec.input('metadata.options.input_filename', valid_type=str, default='aiida.in')
        spec.input('metadata.options.output_filename', valid_type=str, default='aiida.out')
        spec.input('parameters', valid_type=orm.Dict, help='the input parameters')
        spec.input('structure', valid_type=StructureData, required=False, help='the main input structure')
        spec.input('settings', valid_type=orm.Dict, required=False, help='special settings')        

        # Abinit parser 
        spec.inputs['metadata']['options']['parser_name'].default = 'abinit'

        # Use mpi by default.
        spec.input('metadata.options.withmpi', valid_type=bool, default=True)
        spec.inputs['metadata']['options']['resources'].default = {
                'num_machines': 1, 'num_mpiprocs_per_machine': 1, }

        # Unrecoverable errors: file missing
        spec.exit_code(100, 'ERROR_MISSING_OUTPUT_FILES', message='Calculation did not produce all expected output files.')
        
        # Unrecoverable errors: resources like the retrieved folder or its expected contents are missing.
        spec.exit_code(200, 'ERROR_NO_RETRIEVED_FOLDER', message='The retrieved folder data node could not be accessed.')
        spec.exit_code(210, 'ERROR_OUTPUT_MISSING', message='The retrieved folder did not contain the required output file.')

        # Unrecoverable errors: required retrieved files could not be read, parsed or are otherwise incomplete.
        spec.exit_code(301, 'ERROR_OUTPUT_READ', message='The output file could not be read.')
        spec.exit_code(302, 'ERROR_OUTPUT_PARSE', message='The output file could not be parsed.')
        spec.exit_code(303, 'ERROR_OUTPUT_INCOMPLETE', message='The output file was incomplete.')
        spec.exit_code(304, 'ERROR_OUTPUT_CONTAINS_ABORT', message='The output file contains the word "ABORT"')
        spec.exit_code(312, 'ERROR_STRUCTURE_PARSE', message='The output structure could not be parsed.')
        spec.exit_code(350, 'ERROR_UNEXPECTED_PARSER_EXCEPTION', message='The parser raised an unexpected exception.')

        # Outputs
        spec.output('output_parameters', valid_type=orm.Dict, required=True, help='The result of the Abinit calculation.')
        spec.output('output_structure', valid_type=orm.StructureData, required=False,
            help='Optional relaxed crystal structure')
        spec.default_output_node = 'output_parameters'

        # SP: Not sure if I should set this ?
        # spec.outputs.dynamic = True

    def prepare_for_submission(self, folder):
        """
        Create input files.

        :param folder: an `aiida.common.folders.Folder` where the plugin should temporarily place all files needed by
            the calculation.
        :return: `aiida.common.datastructures.CalcInfo` instance
        """
        codeinfo = datastructures.CodeInfo()
        codeinfo.code_uuid = self.inputs.code.uuid
        # codeinfo.stdin_name = self.options.input_filename
        # This gives the path to the input file to Abinit rather than passing the input from standard input
        #print('self.inputs ',self.inputs)
        print('self.inputs.input_filename ',self.options.input_filename)
        codeinfo.cmdline_params = ['<', self.options.input_filename]
        codeinfo.stdout_name = self.metadata.options.output_filename
        codeinfo.withmpi = self.inputs.metadata.options.withmpi

        # Prepare a `CalcInfo` to be returned to the engine
        calcinfo = datastructures.CalcInfo()
        calcinfo.codes_info = [codeinfo]
        calcinfo.retrieve_list = [self.metadata.options.output_filename]

        return calcinfo
