<!--
SPDX-FileCopyrightText: 2023 Florian Liermann

SPDX-License-Identifier: GPL-3.0-or-later
-->

# GNUHealth DHIS2

## Installation
If GNU Health was installed with the Ansible script, just run the `build.sh` script.
If you are not using the demo database you need to adjust the database name in the script in the following line.
```bash
trytond-admin -c ~/etc/trytond.conf -d [DATABASE_NAME] -u health_dhis2 -v
```
Otherwise, install the module manually using pip:
```bash
$ python3 -m pip install ./health_dhis2
```
## Running Tests

Switch to `gnuhealth` user and go to the home directory.
```bash
$ sudo -u gnuhealth /bin/bash
$ cd ~
```
Next activate the python virtual environment.
```bash
$ source venv/bin/activate
```
The tests require the `responses` package to be installed.
It should already be installed in the virtual environment, but if not you need to install it.
```bash
$ pip install responses
```

Next we need to set the name of the database to be used for testing.
The [tyton documentation](https://docs.tryton.org/projects/server/en/latest/topics/testing.html#testing-options) says this step isn't needed and that it will automatically choose a random name, but it throws an error for me without it.
It is possible this is fixed in a newer version of tryton.
```bash
$ export DB_NAME=test_health_dhis2
```
Now we can run the tests:
```bash
$ python -m unittest discover -s trytond.modules.health_dhis2.tests
```