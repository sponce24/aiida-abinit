# `aiida-abinit`
[![PyPI version](https://badge.fury.io/py/aiida-abinit.svg)](https://badge.fury.io/py/aiida-abinit)
[![Build Status](https://github.com/sponce24/aiida-abinit/actions/workflows/ci.yml/badge.svg?event=push)](https://github.com/sponce24/aiida-abinit/actions)


This is an [AiiDA](http://www.aiida.net/) plugin for [ABINIT](https://www.abinit.org/).

## Installation
To install from PyPI, simply execute:

    pip install aiida-abinit

To install from source, execute:

    git clone https://github.com/sponce24/aiida-abinit
    pip install aiida-abinit

## Pseudopotentials
Pseudopotentials are installed and managed through the [`aiida-pseudo` plugin](https://pypi.org/project/aiida-pseudo/).
The easiest way to install pseudopotentials is to install a version of the [PseudoDojo](http://www.pseudo-dojo.org/) through the CLI of `aiida-pseudo`.
To install the default PseudoDojo version, run:

    aiida-pseudo install pseudo-dojo

List the installed pseudopotential families with the command `aiida-pseudo list`.

## Acknowledgements

This work was supported by the the European Unions Horizon 2020 Research and Innovation Programme,
under the [Marie Skłodowska-Curie Grant Agreement SELPH2D No. 839217](https://cordis.europa.eu/project/id/839217).

![MSC](docs/source/images/MSC-logo.png)

## License

MIT

## Contact

`aiida-abinit` is developed and maintained by

* [Samuel Poncé](https://www.samuelponce.com/) - samuel.pon@gmail.com
* [Guido Petretto](https://uclouvain.be/fr/repertoires/guido.petretto)
* [Austin Zadoks](https://people.epfl.ch/austin.zadoks/?lang=en) - austin.zadoks@epfl.ch
