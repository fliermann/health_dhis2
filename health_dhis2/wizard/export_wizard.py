# SPDX-FileCopyrightText: 2023 Florian Liermann
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from pathlib import Path
from typing import Dict

from trytond.model import ModelView, fields
from trytond.wizard import Button, StateTransition, StateView, Wizard

_all__ = ['Dhis2ExportSelect', 'Dhis2ExportResult', 'Dhis2ExportWizard']


class Dhis2ExportSelect(ModelView):
    """
    StateView to select the DHIS2 server.
    All the data mappings of the selected server will be exported.
    """
    __name__ = 'gnuhealth.dhis2.export.start'

    server = fields.Many2One(
        'gnuhealth.dhis2.server', "Server", required=True)


class Dhis2ExportResult(ModelView):
    """StateView to show the results of export"""
    __name__ = 'gnuhealth.dhis2.export.result'

    result = fields.Text("Result", readonly=True)


class Dhis2ExportWizard(Wizard):
    """Wizard to export the data mappings from the DHIS2 server"""
    __name__ = 'gnuhealth.dhis2.export.wizard'

    start = StateView(
        'gnuhealth.dhis2.export.start',
        'health_dhis2.dhis_export_start_view',
        [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Export", 'export', 'tryton-ok', default=True)
        ],
    )
    export = StateTransition()
    result = StateView(
        'gnuhealth.dhis2.export.result',
        'health_dhis2.dhis_export_result_view',
        [
            Button("Close", 'end', 'tryton-cancel')
        ],
    )

    def transition_export(self) -> str:
        """
        Export the data mappings from the DHIS2 server by creating a new
        JSON file.
        """
        self.result.result = "Starting export...\n"
        export = {'data_mappings': []}
        server = self.start.server
        for data_set in server.data_sets:
            for data_element in data_set.data_elements:
                for data_mapping in data_element.data_mapping:
                    export['data_mappings'].append({
                        'data_element_id': data_mapping.data_element.
                        data_element_id,
                        'attribute_option_id': data_mapping.attribute_option.
                        category_option_combo_id,
                        'category_option_id': data_mapping.category_option.
                        category_option_combo_id,
                        'name': data_mapping.name,
                        'sql_query': data_mapping.sql_query,
                        'mapping_active': data_mapping.mapping_active,
                    })
        filename = Path.home()/f'health_dhis2_export_{self.start.server.label}'
        with open(filename, 'w') as file:
            json.dump(export, file)
        self.result.result += f"Successfully exported data mappings to " \
                              f"{filename}"
        return 'result'

    def default_result(self, _) -> Dict:
        """Default values for the result view"""
        return {'result': self.result.result}
