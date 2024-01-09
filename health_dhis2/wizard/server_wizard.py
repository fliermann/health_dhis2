# SPDX-FileCopyrightText: 2023 Florian Liermann
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Dict

from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.wizard import Button, StateTransition, StateView, Wizard

_all__ = ['AddDhis2Wizard', 'AddDhis2Init', 'AddDhis2SyncResult']


class AddDhis2Init(ModelView):
    """
    StateView to initialize the DHIS2 server.
    The user needs to provide a label, url and personal access token.
    """
    __name__ = 'gnuhealth.dhis2.server.wizard.init'

    label = fields.Char(
        "Label", required=True, help="Label for server (eg., remote1)")
    url = fields.Char("URL", required=True)
    pat = fields.Char("Personal Access Token", required=True)


class AddDhis2SyncResult(ModelView):
    """StateView to show the results of the synchronization attempt with the
    DHIS2 server"""
    __name__ = 'gnuhealth.dhis2.server.wizard.sync_result'

    result = fields.Text("Result", readonly=True)


class AddDhis2Wizard(Wizard):
    """Wizard to add a new DHIS2 server"""
    __name__ = 'gnuhealth.dhis2.server.wizard'

    start = StateView(
        'gnuhealth.dhis2.server.wizard.init',
        'health_dhis2.dhis_add_init_view',
        [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Sync", 'first_sync', 'tryton-ok', default=True)
        ],
    )
    first_sync = StateTransition()
    result = StateView(
        'gnuhealth.dhis2.server.wizard.sync_result',
        'health_dhis2.dhis_add_sync_result_view',
        [
            Button("Close", 'end', 'tryton-cancel')
        ],
    )

    def transition_first_sync(self) -> str:
        """
        Test the connection to the DHIS2 server and synchronize the data.
        Will create a new DHIS2 server if successful.
        :return: name of the next state
        """
        pool = Pool()
        Server = pool.get('gnuhealth.dhis2.server')

        try:
            server = Server.create([{
                'label': self.start.label,
                'url': self.start.url,
                'pat': self.start.pat,
            }])[0]
            self.result.result = "Connecting to DHIS2 server...\n"
            server.get_me()
            self.result.result += "Successfully connected to DHIS2 server\n"
            self.result.result += "Synchronizing server data...\n"
            server.sync()
            self.result.result += "Successfully synchronized server data\n"
        except Exception as e:
            Server.delete([server])
            self.result.result += str(e)
            return 'result'
        self.result.result += "Successfully synced DHIS2 server"
        return 'result'

    def default_result(self, _) -> Dict:
        """Default values for the result view"""
        return {'result': self.result.result}
