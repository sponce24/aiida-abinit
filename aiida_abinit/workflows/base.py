# -*- coding: utf-8 -*-
"""Base Abinit WorkChain implementation."""
from aiida import orm
from aiida.common import AttributeDict, exceptions
from aiida.engine import (BaseRestartWorkChain, ProcessHandlerReport, process_handler, while_)
from aiida.plugins import CalculationFactory
from aiida_abinit.utils import (create_kpoints_from_distance, validate_and_prepare_pseudos_inputs)

AbinitCalculation = CalculationFactory('abinit')


class AbinitBaseWorkChain(BaseRestartWorkChain):
    """Base Abinit Workchain to perform a DFT calculation. Validates parameters and restart."""

    _process_class = AbinitCalculation

    @classmethod
    def define(cls, spec):
        """Define the process specification."""
        # yapf: disable
        super().define(spec)

        spec.input('kpoints',
                   valid_type=orm.KpointsData,
                   required=False,
                   help='An explicit k-points mesh or list. Either this or `kpoints_distance` '
                        'must be provided.')
        spec.input('kpoints_distance',
                   valid_type=orm.Float,
                   required=False,
                   help='The minimum desired distance in 1/Å between k-points in reciprocal space. The explicit '
                        'k-point mesh will be generated automatically by a calculation function based on the input '
                        'structure.')
        spec.expose_inputs(AbinitCalculation,
                           namespace='abinit',
                           exclude=('kpoints',))

        spec.outline(
            cls.setup,
            cls.validate_parameters,
            cls.validate_kpoints,
            cls.validate_pseudos,
            cls.validate_resources,
            while_(cls.should_run_process)(
                cls.prepare_process,
                cls.run_process,
                cls.inspect_process,
            ),
            cls.results,
        )

        spec.expose_outputs(AbinitCalculation)

        spec.exit_code(201, 'ERROR_INVALID_INPUT_PSEUDO_POTENTIALS',
            message='`pseudos` could not be used to get the necessary pseudos.')
        spec.exit_code(202, 'ERROR_MISSING_INPUT_KPOINTS',
            message='Neither the `kpoints` nor the `kpoints_distance` input was specified (one required).')
        spec.exit_code(203, 'ERROR_REDUNDANT_INPUT_KPOINTS',
            message='Both the `kpoints` and the `kpoints_distance` inputs were specified but they are exclusive.')
        spec.exit_code(204, 'ERROR_INVALID_INPUT_KPOINTS',
            message='Either the `kpoints` or `kpoints_distance` input is invalid.')
        spec.exit_code(205, 'ERROR_INVALID_INPUT_RESOURCES',
            message='Neither the `options` nor `automatic_parallelization` input was specified.')

    def setup(self):
        """Call the `setup` of the `BaseRestartWorkChain` and then create the inputs dictionary in `self.ctx.inputs`.

        This `self.ctx.inputs` dictionary will be used by the `BaseRestartWorkChain` to submit the calculations in the
        internal loop.
        """
        super().setup()
        self.ctx.restart_calc = None
        self.ctx.inputs = AttributeDict(self.exposed_inputs(AbinitCalculation, 'abinit'))

    def validate_parameters(self):
        """Validate inputs that might depend on each other and cannot be validated by the spec.

        Also define dictionary `inputs` in the context, that will contain the inputs for the calculation that will be
        launched in the `run_calculation` step.
        """
        super().setup()
        self.ctx.inputs.parameters = self.ctx.inputs.parameters.get_dict()
        self.ctx.inputs.settings = self.ctx.inputs.settings.get_dict() if 'settings' in self.ctx.inputs else {}
        self.ctx.inputs.parameters.setdefault('ecut', 8.0)

    def validate_kpoints(self):
        """Validate the inputs related to k-points.

        Either an explicit `KpointsData` with given mesh/path, or a desired k-points distance should be specified. In
        the case of the latter, the `KpointsData` will be constructed for the input `StructureData` using the
        `create_kpoints_from_distance` calculation function.
        """
        if 'kpoints' in self.inputs and 'kpoints_distance' in self.inputs:
            return self.exit_codes.ERROR_REDUNDANT_INPUT_KPOINTS

        if 'kpoints' not in self.inputs and 'kpoints_distance' not in self.inputs:
            return self.exit_codes.ERROR_MISSING_INPUT_KPOINTS

        if 'kpoints' in self.inputs:
            kpoints = self.inputs.kpoints
        else:
            kpoints_distance = self.inputs.kpoints_distance
            if kpoints_distance <= 0.0:
                return self.exit_codes.ERROR_INVALID_INPUT_KPOINTS
            kpoints_distance_inputs = {
                'structure': self.inputs.abinit.structure,
                'distance': kpoints_distance,
                'metadata': {'call_link_label': 'create_kpoints_from_distance'}
            }
            kpoints = create_kpoints_from_distance(**kpoints_distance_inputs)  # pylint: disable=unexpected-keyword-arg

        self.ctx.inputs.kpoints = kpoints

    def validate_pseudos(self):
        """Validate the inputs related to pseudopotentials.

        The pseudo potentials should be defined explicitly in the `pseudos` namespace
        """
        structure = self.ctx.inputs.structure
        pseudos = self.inputs.abinit.get('pseudos', None)

        try:
            self.ctx.inputs.pseudos = validate_and_prepare_pseudos_inputs(structure, pseudos)
        except ValueError as exception:
            self.report(f'{exception}')
            return self.exit_codes.ERROR_INVALID_INPUT_PSEUDO_POTENTIALS  # pylint: disable=no-member

    def prepare_process(self):
        """Prepare the inputs for the next calculation.

        If a `restart_calc` has been set in the context, its `remote_folder` will be used as the `parent_folder` input
        for the next calculation and the `restart_mode` is set to `restart`. Otherwise, no `parent_folder` is used and
        `restart_mode` is set to `from_scratch`.
        """
        if self.ctx.restart_calc:
            self.ctx.inputs.parameters['restartxf'] = -2
            self.ctx.inputs.parent_folder = self.ctx.restart_calc.outputs.remote_folder
        else:
            # Explicitly set that this is not a restart; makes querying easier
            self.ctx.inputs.parameters['restartxf'] = 0

    def report_error_handled(self, calculation, action):
        """Report an action taken for a calculation that has failed.

        This should be called in a registered error handler if its condition is met and an action was taken.

        :param calculation: the failed calculation node
        :param action: a string message with the action taken
        """
        arguments = [calculation.process_label, calculation.pk, calculation.exit_status, calculation.exit_message]
        self.report('{}<{}> failed with exit status {}: {}'.format(*arguments))
        self.report(f'Action taken: {action}')

    @process_handler(priority=580, exit_codes=[
        AbinitCalculation.exit_codes.ERROR_OUT_OF_WALLTIME,
        ])
    def handle_out_of_walltime(self, calculation):
        """Handle `ERROR_OUT_OF_WALLTIME` exit code: calculation shut down neatly and we can simply restart."""
        try:
            self.ctx.inputs.structure = calculation.outputs.output_structure
        except exceptions.NotExistent:
            self.ctx.restart_calc = calculation
            self.report_error_handled(calculation, 'restart from the last calculation')
        else:
            self.ctx.restart_calc = None
            self.report_error_handled(calculation, 'out of walltime: structure changed, so restarting from scratch')

        return ProcessHandlerReport(True)
