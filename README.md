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

### Install Abinit (here for Abinit v.9.2.1)
```shell
wget https://www.abinit.org/sites/default/files/packages/abinit-9.2.1.tar.gz
tar -xvf abinit-9.2.1.tar.gz
cd abinit-9.2.1
mkdir build
cd build
../configure
```

The configure will likely tel you that you have missing mandatory libraries (Netcdf etc).
```shell
cd fallbacks
./build-abinit-fallbacks.sh
```

This will build HDF5, libXC, NetCDF and NetCDF Fortran (it will take time to compile ... go get a coffee)
Next you need to create an .ac file to tell the code where these new libs are

```shell
vim max.ac 
```
Add the lines that the `build-abinit-fallbacks.sh` reported you to the `max.ac` file. 
You should also add the path to your MPI installation (like openmpi) if you want to run in parallel. 
For example:
```shell
with_mpi=/home/max/codes/openmpi-4.0.2/
enable_mpi_io="yes"
with_libxc=/home/max/codes/abinit-9.2.1/build/fallbacks/install_fb/gnu/7.5/libxc/4.3.4
with_hdf5=/home/max/codes/abinit-9.2.1/build/fallbacks/install_fb/gnu/7.5/hdf5/1.10.6
with_netcdf=/home/max/codes/abinit-9.2.1/build/fallbacks/install_fb/gnu/7.5/netcdf4/4.6.3
with_netcdf_fortran=/home/max/codes/abinit-9.2.1/build/fallbacks/install_fb/gnu/7.5/netcdf4_fortran/4.5.2
with_xmlf90=/home/max/codes/abinit-9.2.1/build/fallbacks/install_fb/gnu/7.5/xmlf90/1.5.3.1
with_libpsml=/home/max/codes/abinit-9.2.1/build/fallbacks/install_fb/gnu/7.5/libpsml/1.1.7
```
Then re-run the configure
```shell
../configure --with-config-file=max.ac
make
```
It should work and be compiled. 

If you have trouble installing Abinit, please visit the [Abinit documentation](https://docs.abinit.org/installation/).

You can export the 'abinit' executable with
```shell
export PATH=/home/max/codes/abinit-9.2.1/build/src/98_main:$PATH
```

And do the tests to make sure everything works:
```shell
cd ../tests/
python runtests.py --build-tree=/home/max/codes/abinit-9.2.1/build
```

### Install AiiDA

First create a virtual python environement with conda (install it if you do not have it):
```shell
conda create -n aiida-abinit -c conda-forge aiida-core=1.4.2 aiida-core.services=1.4.2
```

Then activate your virtual environement
```shell
conda activate aiida-abinit
reentry scan
```

You should then clone this GitHub repo
```shell
git clone https://github.com/sponce24/aiida-abinit
cd aiida-abinit
pip install -e . --ignore-installed --use-feature=2020-resolver
```

This should install `aiida-core` and `aiida-abinit`. 

You should now setup the computer and the code:
```shell
cd examples
```

You should open the ``computer.yml`` and adapt it to your environement. 
Then run:
```shell
verdi computer setup --config computer.yml
```
This will setup your current local machine as the computer. You can also adapt the ``computer.yml`` to setup a remote machine. 
If you do:
```shell
verdi computer list
```
It should show your computer. 

Now setup the Abinit code. Also edit the ``code.yml`` indicating your path. 
Then do:
```shell
verdi code setup --config code.yml
```
This should setup the Abinit code. You can verify that you have it by doing:
```shell
verdi code list
```

Finally, you should make sure that you have the abinit calculation plugin by doing:
```shell
verdi plugin list aiida.calculations 
```

This should show ``* abinit``

You are now all setup. Congratulations !!

## Usage

Here goes a complete example of how to submit a test calculation using this plugin.

A quick demo of how to submit a calculation:
```shell
verdi daemon start     # make sure the daemon is running
cd examples
python example_dft.py --code abinit-9.2.1-ab@localhost # run DFT test calculation
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
* [Austin Zadoks](https://people.epfl.ch/austin.zadoks/?lang=en) - austin.zadoks@epfl.ch

