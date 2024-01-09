# SPDX-FileCopyrightText: 2023 Florian Liermann
#
# SPDX-License-Identifier: GPL-3.0-or-later

import json
from typing import Dict

from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.wizard import Button, StateTransition, StateView, Wizard

_all__ = ['Dhis2ImportSelect', 'Dhis2ImportResult', 'Dhis2ImportWizard']


class Dhis2ImportSelect(ModelView):
    """
    StateView to select the file to import.
    All the data mappings of the selected file will be imported.
    """
    __name__ = 'gnuhealth.dhis2.import.start'

    file = fields.Binary("File", required=True)


class Dhis2ImportResult(ModelView):
    """StateView to show the results of the import"""
    __name__ = 'gnuhealth.dhis2.import.result'

    result = fields.Text("Result", readonly=True)


class Dhis2ImportWizard(Wizard):
    """Wizard to import the data mappings to the DHIS2 server"""
    __name__ = 'gnuhealth.dhis2.import.wizard'

    start = StateView(
        'gnuhealth.dhis2.import.start',
        'health_dhis2.dhis_import_start_view',
        [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Import", 'file_import', 'tryton-ok', default=True)
        ],
    )
    file_import = StateTransition()
    result = StateView(
        'gnuhealth.dhis2.import.result',
        'health_dhis2.dhis_import_result_view',
        [
            Button("Close", 'end', 'tryton-cancel')
        ],
    )

    def transition_file_import(self) -> str:
        """
        Import the data mappings from the DHIS2 server
        from the JSON file.
        """
        pool = Pool()
        DataMapping = pool.get('gnuhealth.dhis2.data_mapping')

        self.result.result = "Starting import...\n"
        imports = json.dumps(json.loads(self.start.file.decode('utf8')))
        data_mappings = DataMapping.search([])
        for import_ in json.loads(imports)['data_mappings']:
            for data_mapping in data_mappings:
                if (import_['data_element_id'] == data_mapping.data_element
                        .data_element_id and import_['attribute_option_id'] ==
                        data_mapping.attribute_option.category_option_combo_id
                        and import_['category_option_id'] == data_mapping
                        .category_option.category_option_combo_id):
                    data_mapping.sql_query = import_['sql_query']
                    data_mapping.mapping_active = import_['mapping_active']
                    self.result.result += f"Imported {data_mapping.name}\n"
                    data_mapping.save()
                    break
            else:
                self.result.result += f"Could not find {import_['name']}\n"
        return 'result'

    def default_result(self, _) -> Dict:
        """Default values for the result view"""
        return {'result': self.result.result}
