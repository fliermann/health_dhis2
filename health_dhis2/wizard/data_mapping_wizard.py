# SPDX-FileCopyrightText: 2023 Florian Liermann
#
# SPDX-License-Identifier: GPL-3.0-or-later

from enum import Enum
from typing import Dict

from sql.aggregate import Count
from sql.functions import DateTrunc

from trytond.exceptions import UserError
from trytond.model import ModelView, fields
from trytond.pool import Pool
from trytond.wizard import Button, StateTransition, StateView, Wizard

from ..health_dhis2 import DataSetPeriodType, Dhis2DataMapping

__all__ = ['DataMappingWizard', 'DataMappingSelect', 'DataMappingResult',
           'DataMappingPresetDisease', 'DataMappingPresetOperationProcedure',
           'DataMappingPresetRawSQL', 'DataMappingPreset']


class DataMappingPreset(Enum):
    """Enum for the different presets"""
    RAW_SQL = "Raw SQL"
    DISEASE = "Disease"
    OPERATION_PROCEDURE = "Operation Procedure"


class DataMappingSelect(ModelView):
    """StateView to select the data mapping and the preset"""
    __name__ = 'gnuhealth.dhis2.data_mapping.wizard.select_mapping'

    data_mapping = fields.Many2One(
        'gnuhealth.dhis2.data_mapping', "Data Mapping",
        required=True)
    preset = fields.Selection(
        [(preset.name, preset.value) for preset in DataMappingPreset],
        "Preset", required=True)


class DataMappingPresetBase(ModelView):
    """Base class for the presets"""

    def get_query(self, period_type: DataSetPeriodType):
        """
        Implementation stub for the query generation
        :return: sql query object
        """
        raise NotImplementedError

    def get_query_string(self, period_type: DataSetPeriodType) -> str:
        """
        Convert the query object to a string
        :param period_type: period type of the data set
        :return: string of the sql query
        """
        query = self.get_query(period_type)

        # In case we have params in the query we need to add them
        # to the query string
        params = query.params
        if not params:
            return str(query)

        # We need to add quotes around the string parameters to
        # make the query valid
        params_new = ()
        for param in params:
            if isinstance(param, str):
                params_new += (f"'{param}'",)
            else:
                params_new += (param,)

        return str(query) % params_new


class DataMappingPresetDisease(DataMappingPresetBase):
    """
    Preset for retrieving the number of confirmed cases
    of a disease per month
    """
    __name__ = 'gnuhealth.dhis2.data_mapping.wizard.preset_disease'

    disease = fields.Many2One(
        'gnuhealth.pathology', "Disease", required=True)

    def get_query(self, period_type: DataSetPeriodType):
        """
        Generate the query to retrieve the number of confirmed cases
        of the selected disease
        :param period_type: period type of the data set
        :return: sql query object
        """
        Condition = Pool().get('gnuhealth.patient.disease')
        condition = Condition.__table__()
        query = condition.select(
            DateTrunc(
                period_type.to_date_trunc(),
                condition.diagnosed_date).as_('date'),
            Count(condition.id).as_('value'),
            where=(condition.pathology == self.disease.id) &
                  (condition.diagnosed_date != None),   # noqa: E711
            group_by=[
                DateTrunc(
                    period_type.to_date_trunc(),
                    condition.diagnosed_date)],
        )
        return query


class DataMappingPresetOperationProcedure(DataMappingPresetBase):
    """
    Preset for retrieving the number of operations
    with a specific procedure
    """
    __name__ = 'gnuhealth.dhis2.data_mapping.wizard.preset_operation_procedure'

    procedure = fields.Many2One(
        'gnuhealth.procedure', "Procedure", required=True)

    def get_query(self, period_type: DataSetPeriodType):
        """
        Generate the query to retrieve the number of operations with the
        selected procedure
        :param period_type: period type of the data set
        :return: sql query object
        """
        Operation = Pool().get('gnuhealth.operation')
        Surgery = Pool().get('gnuhealth.surgery')
        operation = Operation.__table__()
        surgery = Surgery.__table__()
        query = operation.join(
            surgery, condition=surgery.id == operation.name).select(
            DateTrunc(
                period_type.to_date_trunc(),
                surgery.surgery_date).as_('date'),
            Count(operation.id).as_('value'),
            where=(surgery.surgery_date != None) &  # noqa: E711
                  (self.procedure.id == operation.procedure),
            group_by=[
                DateTrunc(
                    period_type.to_date_trunc(),
                    surgery.surgery_date)],
        )
        return query


class DataMappingPresetRawSQL(DataMappingPresetBase):
    """This preset allows users to input their own SQL query"""
    __name__ = 'gnuhealth.dhis2.data_mapping.wizard.preset_raw_sql'

    sql = fields.Text("SQL Query")

    def get_query_string(self, _) -> str:
        """
        Return the raw SQL query
        :return: raw SQL query
        """
        return self.sql


class DataMappingResult(ModelView):
    """StateView to show the results of the configured SQL query"""
    __name__ = 'gnuhealth.dhis2.data_mapping.wizard.result'

    result = fields.Text("SQL query result", readonly=True)


class DataMappingWizard(Wizard):
    """Wizard for configuring a data mapping"""
    __name__ = 'gnuhealth.dhis2.data_mapping.wizard'

    start = StateView(
        'gnuhealth.dhis2.data_mapping.wizard.select_mapping',
        'health_dhis2.dhis_data_mapping_wizard_select_view',
        [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Next", 'select_preset', 'tryton-ok',
                   default=True)
        ],
    )
    select_preset = StateTransition()
    display_result = StateTransition()

    result = StateView(
        'gnuhealth.dhis2.data_mapping.wizard.result',
        'health_dhis2.dhis_data_mapping_wizard_result_view',
        [
            Button("Cancel", 'end', 'tryton-cancel'),
            Button("Save", 'save', 'tryton-ok', default=True)
        ],
    )
    save = StateTransition()

    def __init__(self, *args) -> None:
        """
        Initialize the wizard by automatically adding the StateViews of the
        presets
        """
        for preset in DataMappingPreset:
            setattr(self, f'preset_{preset.name.lower()}', StateView(
                f'gnuhealth.dhis2.data_mapping.wizard.preset_'
                f'{preset.name.lower()}',
                f'health_dhis2.dhis_data_mapping_wizard_preset_'
                f'{preset.name.lower()}_view',
                [
                    Button("Cancel", 'end', 'tryton-cancel'),
                    Button("Next", 'display_result',
                           'tryton-ok', default=True)
                ]))
            self.states[f'preset_{preset.name.lower()}'] = (
                getattr(self, f'preset_{preset.name.lower()}'))
        super().__init__(*args)

    def transition_select_preset(self) -> str:
        """
        Transition to the selected preset
        :return: name of the selected preset state
        :raises UserError: if the period type is not supported or the
        organisation unit is missing
        """
        # The presets only work with data sets with a period type that is
        # supported by DateTrunc
        # (Daily, Weekly, Monthly, Quarterly, Yearly)
        try:
            DataSetPeriodType(
                self.start.data_mapping.data_element.data_set.period_type)
        except ValueError:
            raise UserError(
                f"The period type '"
                f"{self.start.data_mapping.data_element.data_set.period_type}'"
                f" of the selected data set is not supported.")

        if not self.start.data_mapping.data_element.data_set.org_unit:
            raise UserError(
                "The data set of the selected data element has no "
                "organisation unit assigned.")

        return f'preset_{self.start.preset.lower()}'

    def transition_display_result(self) -> str:
        """
        Test the query and display the result
        :return: name of the next state
        """
        preset = getattr(self, f'preset_{self.start.preset.lower()}')
        query = preset.get_query_string(DataSetPeriodType(
            self.start.data_mapping.data_element.data_set.period_type))
        description, data = Dhis2DataMapping.test_query(query)
        result_str = ", ".join([column.name for column in description]) + "\n"
        for row in data:
            col_strs = []
            for column, value in zip(description, row):
                if column.name == 'date':
                    col_strs.append(DataSetPeriodType(
                        self.start.data_mapping.data_element.data_set
                        .period_type).get_date_str(
                        value))
                elif column.name == 'value':
                    col_strs.append(str(value))
            result_str += ', '.join(col_strs) + '\n'
        self.result.result = result_str
        return 'result'

    def default_result(self, _) -> Dict:
        """Default values for the result view"""
        return {'result': self.result.result}

    def transition_save(self) -> str:
        """
        Saves the query to the data mapping and exits the wizard
        :return: name of the end state
        """
        preset = getattr(self, f'preset_{self.start.preset.lower()}')
        query = preset.get_query_string(DataSetPeriodType(
            self.start.data_mapping.data_element.data_set.period_type))
        self.start.data_mapping.sql_query = query
        self.start.data_mapping.mapping_active = True
        self.start.data_mapping.save()
        return 'end'
