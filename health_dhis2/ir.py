# SPDX-FileCopyrightText: 2023 Florian Liermann
#
# SPDX-License-Identifier: GPL-3.0-or-later

from trytond.pool import PoolMeta


class Cron(metaclass=PoolMeta):
    """Extended cron class to automatically sync DHIS2 servers"""
    __name__ = 'ir.cron'

    @classmethod
    def __setup__(cls):
        """Override/Extend the setup method to add more options to the
        scheduler"""
        super().__setup__()
        cls.method.selection.append((
            'gnuhealth.dhis2.server|sync_all',
            "Synchronize all DHIS2 servers"))
        cls.method.selection.append((
            'gnuhealth.dhis2.server|submit_all_data',
            "Submit all mapped data to DHIS2 servers"))
