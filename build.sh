#!/bin/sh

# SPDX-FileCopyrightText: 2023 Florian Liermann
#
# SPDX-License-Identifier: GPL-3.0-or-later

# Copy data
cp -r ./health_dhis2 /opt/gnuhealth
chown -R gnuhealth /opt/gnuhealth/health_dhis2

# Switch to gnuhealth user
exec sudo -u gnuhealth /bin/bash - << eof

# Install module
source ~/venv/bin/activate
python3 -m pip install ~/health_dhis2
trytond-admin -c ~/etc/trytond.conf -d ghdemo42 -u health_dhis2 -v
echo "Installed Module"

# Restart server
systemctl restart gnuhealth.service --no-block
echo "Restarted Service"
exit