# SPDX-FileCopyrightText: 2023 Florian Liermann
#
# SPDX-License-Identifier: GPL-3.0-or-later

from trytond.pool import Pool

from . import health_dhis2, ir
from .wizard import (
    data_mapping_wizard, export_wizard, import_wizard, server_wizard)

__all__ = ['register']


def register() -> None:
    """Register models and wizards for the module."""
    # SQL Models
    Pool.register(
        health_dhis2.Dhis2Server,
        health_dhis2.Dhis2OrganisationUnit,
        health_dhis2.Dhis2CategoryCombo,
        health_dhis2.Dhis2CategoryOptionCombo,
        health_dhis2.Dhis2DataSet,
        health_dhis2.Dhis2DataElement,
        health_dhis2.Dhis2DataMapping,

        # Server Setup Wizard
        server_wizard.AddDhis2Init,
        server_wizard.AddDhis2SyncResult,

        # Data Mapping Wizard
        data_mapping_wizard.DataMappingSelect,
        data_mapping_wizard.DataMappingResult,

        # Data Mapping Wizard Presets
        data_mapping_wizard.DataMappingPresetDisease,
        data_mapping_wizard.DataMappingPresetOperationProcedure,
        data_mapping_wizard.DataMappingPresetRawSQL,

        # Export Wizard
        export_wizard.Dhis2ExportSelect,
        export_wizard.Dhis2ExportResult,

        # Import Wizard
        import_wizard.Dhis2ImportSelect,
        import_wizard.Dhis2ImportResult,

        # Cron
        ir.Cron,
        module='health_dhis2', type_='model')

    # Wizards
    Pool.register(
        server_wizard.AddDhis2Wizard,
        data_mapping_wizard.DataMappingWizard,
        export_wizard.Dhis2ExportWizard,
        import_wizard.Dhis2ImportWizard,
        module='health_dhis2', type_='wizard')
