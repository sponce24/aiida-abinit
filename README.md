[![Build Status](https://github.com/sponce24/aiida-abinit/workflows/ci/badge.svg?branch=master)](https://github.com/sponce24/aiida-abinit/actions)
[![Coverage Status](https://coveralls.io/repos/github/sponce24/aiida-abinit/badge.svg?branch=master)](https://coveralls.io/github/sponce24/aiida-abinit?branch=master)
[![Docs status](https://readthedocs.org/projects/aiida-abinit/badge)](http://aiida-abinit.readthedocs.io/)
[![PyPI version](https://badge.fury.io/py/aiida-abinit.svg)](https://badge.fury.io/py/aiida-abinit)

# aiida-abinit

![ABINIT](miscellaneous/logos/logo-abinit-2015.png)
![AiiDA](miscellaneous/logos/AiiDA_transparent_logo.png)

The [AiiDA](http://www.aiida.net/) plugin for [ABINIT](https://www.abinit.org/).

[ABINIT](https://www.abinit.org/) is a software suite to calculate the optical, mechanical, vibrational, and other observable properties of materials. Starting from the quantum equations of density functional theory, you can build up to advanced applications with perturbation theories based on DFT, and many-body Green's functions (GW and DMFT) .
ABINIT can calculate molecules, nanostructures and solids with any chemical composition, and comes with several complete and robust tables of atomic potentials.
On-line tutorials are available for the main features of the code, and several schools and workshops are organized each year.

This plugin was created using [AiiDA plugin cutter](https://github.com/aiidateam/aiida-plugin-cutter).

## Installation

```shell
pip install aiida-abinit
verdi quicksetup  # better to set up a new profile
verdi plugin list aiida.calculations  # should now show your calclulation plugins
```

## Usage

Here goes a complete example of how to submit a test calculation using this plugin.

A quick demo of how to submit a calculation:
```shell
verdi daemon start     # make sure the daemon is running
cd examples
./example_dft.py       # run DFT test calculation
verdi process list -a  # check record of calculation
```

The plugin also includes verdi commands to inspect its data types:
```shell
verdi data abinit list
verdi data abinit export <PK>
```

## Development

```shell
git clone https://github.com/sponce24/aiida-abinit .
cd aiida-abinit
pip install -e .[pre-commit,testing]  # install extra dependencies
pre-commit install  # install pre-commit hooks
pytest -v  # discover and run all tests
```

See the [developer guide](http://aiida-abinit.readthedocs.io/en/latest/developer_guide/index.html) for more information.

## Acknowledgements

This work was supported by the the European Unions Horizon 2020 Research and Innovation Programme, 
under the [Marie Skłodowska-Curie Grant Agreement SELPH2D No. 839217](https://cordis.europa.eu/project/id/839217).

![MSC](miscellaneous/logos/MSC-logo.png)

## License

MIT

## Contact

The AiiDA-abinit plugin is developed and maintained by 

* [Samuel Poncé](https://www.samuelponce.com/) - samuel.pon@gmail.com
* [Guido Petretto](https://uclouvain.be/fr/repertoires/guido.petretto)

