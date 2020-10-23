# -*- coding: utf-8 -*-
"""Base Abinit Workchain"""
from aiida import orm
from aiida.common import AttributeDict, exceptions
from aiida.engine import WorkChain, ToContext, if_, while_, append_, BaseRestartWorkChain, process_handler
from aiida.plugins import CalculationFactory, WorkflowFactory

AbinitCalculation = CalculationFactory('abinit')

class AbinitBaseWorkChain(BaseRestartWorkChain):
    """Base Abinit Workchain to perform a DFT calculation. Validates parameters and restart."""

    _process_class = AbinitCalculation

    @classmethod
    def define(cls, spec):
        """Define the process specification."""
        # yapf: disable
        super().define(spec)
        spec.expose_inputs(AbinitCalculation, namespace='abinit')
       
        spec.outline(
            cls.setup,
            cls.validate_parameters,
            cls.validate_pseudos,
            cls.validate_resources,
            while_(cls.should_run_process)(
                cls.prepare_process,
                cls.run_process,
                cls.inspect_process,
            ),
            cls.results,
        )
        spec.exit_code(201, 'ERROR_INVALID_INPUT_PSEUDO_POTENTIALS',
            message='The explicit `pseudos` or `pseudo_family` could not be used to get the necessary pseudos.')        

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
        self.ctx.inputs.parameters = self.ctx.inputs.parameters.get_dict()
        self.ctx.inputs.settings = self.ctx.inputs.settings.get_dict() if 'settings' in self.ctx.inputs else {}

        self.ctx.inputs.parameters.setdefault('ecut', 8.0)


    def validate_pseudos(self):
        """Validate the inputs related to pseudopotentials.

        Either the pseudo potentials should be defined explicitly in the `pseudos` namespace, or alternatively, a family
        can be defined in `pseudo_family` that will be used together with the input `StructureData` to generate the
        required mapping.
        """
        structure = self.ctx.inputs.structure
        pseudos = self.ctx.inputs.parameters.get('pp_dirpath', None)
        if (pseudos is None):
            return self.exit_codes.ERROR_INVALID_INPUT_PSEUDO_POTENTIALS

    def validate_resources(self):
        """Validate the inputs related to the resources.

        One can omit the normally required `options.resources` input for the `PwCalculation`, as long as the input
        `automatic_parallelization` is specified. If this is not the case, the `metadata.options` should at least
        contain the options `resources` and `max_wallclock_seconds`, where `resources` should define the `num_machines`.
        """
        if 'automatic_parallelization' not in self.inputs and 'options' not in self.ctx.inputs.metadata:
            return self.exit_codes.ERROR_INVALID_INPUT_RESOURCES

        # If automatic parallelization is not enabled, we better make sure that the options satisfy minimum requirements
        if 'automatic_parallelization' not in self.inputs:
            num_machines = self.ctx.inputs.metadata.options.get('resources', {}).get('num_machines', None)
            max_wallclock_seconds = self.ctx.inputs.metadata.options.get('max_wallclock_seconds', None)

            if num_machines is None or max_wallclock_seconds is None:
                return self.exit_codes.ERROR_INVALID_INPUT_RESOURCES_UNDERSPECIFIED

            #self.set_max_seconds(max_wallclock_seconds)

 #   def set_max_seconds(self, max_wallclock_seconds):
 #       """Set the `max_seconds` to a fraction of `max_wallclock_seconds` option to prevent out-of-walltime problems.

 #       :param max_wallclock_seconds: the maximum wallclock time that will be set in the scheduler settings.
 #       """
 #       #max_seconds_factor = self.defaults.delta_factor_max_seconds
 #       max_seconds = max_wallclock_seconds * 1.0
 #       #self.ctx.inputs.parameters['CONTROL']['max_seconds'] = max_seconds

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
            self.ctx.inputs.parameters['restartxf'] = 0

    def report_error_handled(self, calculation, action):
        """Report an action taken for a calculation that has failed.

        This should be called in a registered error handler if its condition is met and an action was taken.

        :param calculation: the failed calculation node
        :param action: a string message with the action taken
        """
        arguments = [calculation.process_label, calculation.pk, calculation.exit_status, calculation.exit_message]
        self.report('{}<{}> failed with exit status {}: {}'.format(*arguments))
        self.report('Action taken: {}'.format(action))


    @process_handler(priority=580, exit_codes=[
        AbinitCalculation.exit_codes.ERROR_OUT_OF_WALLTIME,
        ])
    def handle_out_of_walltime(self, calculation):
        """Handle `ERROR_OUT_OF_WALLTIME` exit code: calculation shut down neatly and we can simply restart."""
        try:
            self.ctx.inputs.structure = calculation.outputs.output_structure
        except exceptions.NotExistent:
            self.ctx.restart_calc = calculation
            self.report_error_handled(calculation, 'simply restart from the last calculation')
        else:
            self.ctx.restart_calc = None
            self.report_error_handled(calculation, 'out of walltime: structure changed so restarting from scratch')

        return ProcessHandlerReport(True)






