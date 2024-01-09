# SPDX-FileCopyrightText: 2023 Florian Liermann
#
# SPDX-License-Identifier: GPL-3.0-or-later

from datetime import datetime
from enum import Enum
from typing import Dict, List

import requests

from trytond.exceptions import UserError
from trytond.model import ModelSQL, ModelView, fields
from trytond.pool import Pool
from trytond.transaction import Transaction

from .exceptions import (
    DHIS2APIError, NotFoundError, UnauthorizedError, UnhandledConflictError)

__all__ = ['Dhis2Server', 'Dhis2OrganisationUnit', 'Dhis2CategoryCombo',
           'Dhis2CategoryOptionCombo', 'Dhis2DataSet', 'Dhis2DataElement',
           'Dhis2DataMapping', 'DataSetPeriodType']


class DataSetPeriodType(Enum):
    """Enum for the supported period types of a data set"""
    DAILY = "Daily"
    WEEKLY = "Weekly"
    MONTHLY = "Monthly"
    QUARTERLY = "Quarterly"
    YEARLY = "Yearly"

    def to_date_trunc(self) -> str:
        """
        Convert the period type to a string that can be used with DateTrunc

        :return: string of the period type
        """
        match self:
            case DataSetPeriodType.DAILY:
                return 'day'
            case DataSetPeriodType.WEEKLY:
                return 'week'
            case DataSetPeriodType.MONTHLY:
                return 'month'
            case DataSetPeriodType.QUARTERLY:
                return 'quarter'
            case DataSetPeriodType.YEARLY:
                return 'year'
            case _:
                raise ValueError(f"Period type '{self}' is not supported")

    def get_date_str(self, date: datetime) -> str:
        """
        Get the date string for DHIS2 for the given date and period type
        https://docs.dhis2.org/archive/en/2.25/developer/html
        /webapi_date_perid_format.html
        :param date: datetime object
        :return: string of the date in the correct format required by DHIS2
        :raises ValueError: if the period type is not supported
        """
        match self:
            case DataSetPeriodType.DAILY:
                return date.strftime('%Y%m%d')
            case DataSetPeriodType.WEEKLY:
                return date.strftime('%Y%V')
            case DataSetPeriodType.MONTHLY:
                return date.strftime('%Y%m')
            case DataSetPeriodType.QUARTERLY:
                return date.strftime('%Y') + 'Q' + str(
                    (date.month - 1) // 4 + 1)
            case DataSetPeriodType.YEARLY:
                return date.strftime('%Y')
            case _:
                raise ValueError(f"Period type '{self}' is not supported")


class Dhis2Server(ModelSQL, ModelView):
    """DHIS2 Server Configuration"""
    __name__ = 'gnuhealth.dhis2.server'
    _rec_name = 'label'

    label = fields.Char(
        "Label", required=True, help="Label for server (eg., remote1)")
    url = fields.Char("URL", required=True)
    pat = fields.Char("PAT", help="Personal Access Token", required=True)
    sync_time = fields.DateTime(
        "Sync Time", readonly=True,
        help="The time of the last server sync")
    validated = fields.Boolean(
        "Validated", readonly=True,
        help="A flag to indicate if the server has been successfully synced")

    # Children
    org_units = fields.One2Many(
        'gnuhealth.dhis2.org_unit', "server",
        "Organisation Units", readonly=True)
    data_sets = fields.One2Many(
        'gnuhealth.dhis2.data_set', "server", "Data Sets",
        readonly=True)
    category_combos = fields.One2Many(
        'gnuhealth.dhis2.category_combo', 'server',
        "Category Combos", readonly=True)

    @classmethod
    def __setup__(cls) -> None:
        """Override the __setup__ method to add the buttons"""
        super().__setup__()
        cls._buttons.update({
            'sync_button': {},
            'submit_data_button': {},
        })

    @classmethod
    @ModelView.button
    def sync_button(cls, records) -> None:
        """Synchronize the data with DHIS2"""
        for record in records:
            record.sync()

    @classmethod
    @ModelView.button
    def submit_data_button(cls, records) -> None:
        """Iterate over all data mappings and submit their data to DHIS2"""
        for record in records:
            for data_set in record.data_sets:
                for data_element in data_set.data_elements:
                    for data_mapping in data_element.data_mapping:
                        data_mapping.submit_data()

    def _request(self, http_method: str, endpoint: str,
                 params: Dict = None, data: Dict = None) -> Dict:
        """
        Send a request to the DHIS2 server
        :param http_method: the HTTP method to use
        :param endpoint: the endpoint to send the request to
        :param params: dict of the http query parameters
        :param data: dict of the json data to send
        :return: dict of the response data if the request was successful
        :raises DHIS2APIError: if the request failed
        """
        full_url = f'{self.url}/api{endpoint}'
        headers = {'Authorization': f'ApiToken {self.pat}',
                   'Content-Type': 'application/json'}
        response = requests.request(method=http_method, url=full_url,
                                    headers=headers, params=params, json=data)
        match response.status_code:
            case 200:
                response_data = response.json()
                return response_data
            case 401:
                raise UnauthorizedError("Invalid access token")
            case 404:
                raise NotFoundError("Endpoint not found")
            case 409:
                # Ignore E7641 conflicts (future period) because dhis2 just
                # ignores those values
                response_data = response.json()
                for conflict in response_data['response']['conflicts']:
                    if conflict['errorCode'] != 'E7641':
                        raise UnhandledConflictError(
                            f"Conflict {response.status_code}:\n "
                            f"{response.text}")
                return response_data
            case _:
                raise DHIS2APIError(
                    f"Request failed with status code {response.status_code} "
                    f"and message {response.text}")

    def get(self, endpoint: str, params: Dict = None) -> Dict:
        """
        Wrapper of the _request function for GET requests
        :param endpoint: the endpoint to send the request to
        :param params: dict of the http query parameters
        :return: dict of the response data if the request was successful
        """
        return self._request('GET', endpoint, params)

    def post(self, endpoint, params: Dict = None, data: Dict = None) -> Dict:
        """
        Wrapper of the _request function for POST requests
        :param endpoint: the endpoint to send the request to
        :param params: dict of the http query parameters
        :param data: dict of the json data
        :return:
        """
        return self._request('POST', endpoint, params, data=data)

    def get_me(self) -> Dict:
        """
        Get the details of the user of the PAT
        :return: dict of user details
        """
        return self.get('/me')

    def get_datasets(self) -> List:
        """
        Get all data sets from the dhis2 server
        :return: a list of all data sets
        """
        return self.get('/dataSets')['dataSets']

    def get_dataset(self, dataset_id: int) -> Dict:
        """
        Get the details of a specific data set
        :param dataset_id: id of the data set
        :return: dict of the data set details
        """
        return self.get(f'/dataSets/{dataset_id}')

    def get_data_element(self, data_element_id: int) -> Dict:
        """
        Get the details of a specific data element
        :param data_element_id: id of the data element
        :return: dict of the data element details
        """
        return self.get(f'/dataElements/{data_element_id}')

    def get_org_unit(self, org_unit_id: int) -> Dict:
        """
        Get the details of a specific organisation unit
        :param org_unit_id: id of the organisation unit
        :return: dict of the organisation unit details
        """
        return self.get(f'/organisationUnits/{org_unit_id}')

    def get_category_combos(self) -> List:
        """
        Get all category combos from the dhis2 server
        :return: list of all category combos
        """
        return self.get('/categoryCombos')['categoryCombos']

    def get_category_combo(self, category_combo_id: int) -> Dict:
        """
        Get the details of a specific category combo
        :param category_combo_id: id of the category combo
        :return: dict of the category combo details
        """
        return self.get(f'/categoryCombos/{category_combo_id}')

    def get_category_option_combo(self, category_option_combo_id: int) -> Dict:
        """
        Get the details of a specific category option combo
        :param category_option_combo_id: id of the category option combo
        :return: dict of the category option combo details
        """
        return self.get(f'/categoryOptionCombos/{category_option_combo_id}')

    def sync(self) -> None:
        """
        Synchronize the server with the DHIS2 server,
        delete entries that are not in DHIS2 anymore and create new ones
        """
        pool = Pool()
        OrgUnit = pool.get('gnuhealth.dhis2.org_unit')
        CategoryCombo = pool.get('gnuhealth.dhis2.category_combo')
        DataSet = pool.get('gnuhealth.dhis2.data_set')

        try:
            # Check if PAT is valid
            me = self.get_me()

            # Sync organisation units
            dhis_org_units = me['organisationUnits']
            for org_unit in self.org_units:
                for dhis_org_unit in dhis_org_units:
                    if org_unit.org_unit_id == dhis_org_unit['id']:
                        org_unit.sync()
                        dhis_org_units.remove(dhis_org_unit)
                        break
                else:
                    OrgUnit.delete([org_unit])
            for dhis_org_unit in dhis_org_units:
                dhis_org_unit_details = self.get_org_unit(dhis_org_unit['id'])
                OrgUnit.create([{
                    'server': self.id,
                    'org_unit_id': dhis_org_unit['id'],
                    'name': dhis_org_unit_details['displayName'],
                }])

            # Sync category combos
            dhis_category_combos = self.get_category_combos()
            for category_combo in self.category_combos:
                for dhis_category_combo in dhis_category_combos:
                    if (dhis_category_combo['id'] ==
                            category_combo.category_combo_id):
                        category_combo.sync()
                        dhis_category_combos.remove(dhis_category_combo)
                        break
                else:
                    CategoryCombo.delete([category_combo])
            for dhis_category_combo in dhis_category_combos:
                dhis_category_combo_details = self.get_category_combo(
                    dhis_category_combo['id'])
                category_combo = CategoryCombo.create([{
                    'server': self.id,
                    'category_combo_id': dhis_category_combo['id'],
                    'name': dhis_category_combo_details['displayName'],
                    'data_dimension_type': dhis_category_combo_details[
                        'dataDimensionType'],
                }])
                category_combo[0].sync()

            # Sync data sets
            dhis_data_sets = self.get_datasets()
            for data_set in self.data_sets:
                for dhis_data_set in dhis_data_sets:
                    if data_set.data_set_id == dhis_data_set['id']:
                        data_set.sync()
                        dhis_data_sets.remove(dhis_data_set)
                        break
                else:
                    DataSet.delete([data_set])
            for dhis_data_set in dhis_data_sets:
                dhis_data_set_details = self.get_dataset(dhis_data_set['id'])
                data_set = DataSet.create([{
                    'server': self.id,
                    'name': dhis_data_set_details['displayName'],
                    'data_set_id': dhis_data_set['id'],
                    'period_type': dhis_data_set_details['periodType'],
                }])
                data_set[0].sync()
        except Exception as e:
            self.validated = False
            raise e
        else:
            self.validated = True
        self.sync_time = datetime.now()

    @classmethod
    def sync_all(cls) -> None:
        """
        Synchronize all DHIS2 servers, this method is called
        by the scheduler
        """
        servers = cls.search([])
        for server in servers:
            server.sync()

    @classmethod
    def submit_all_data(cls) -> None:
        """
        Iterate over all data mappings and submits their data to DHIS2,
        this method is called by the scheduler
        """
        servers = cls.search([])
        for server in servers:
            for data_set in server.data_sets:
                for data_element in data_set.data_elements:
                    for data_mapping in data_element.data_mapping:
                        data_mapping.submit_data()


class Dhis2OrganisationUnit(ModelSQL, ModelView):
    """DHIS2 Organisation Unit"""
    __name__ = 'gnuhealth.dhis2.org_unit'
    _rec_name = 'name'

    server = fields.Many2One(
        'gnuhealth.dhis2.server', "Server", required=True,
        ondelete='CASCADE', readonly=True)
    org_unit_id = fields.Char(
        "Organisation Unit ID", required=True,
        help="The ID of the organisation unit", readonly=True)
    name = fields.Char(
        "Name", required=True,
        help="Name of the organisation unit", readonly=True)

    def sync(self) -> None:
        """Synchronize this organisation unit with DHIS2"""
        dhis_org_unit = self.server.get_org_unit(self.org_unit_id)
        self.name = dhis_org_unit['displayName']
        self.save()


class Dhis2CategoryCombo(ModelSQL, ModelView):
    """DHIS2 Category Combo"""
    __name__ = 'gnuhealth.dhis2.category_combo'
    _rec_name = 'name'

    server = fields.Many2One(
        'gnuhealth.dhis2.server', "Server", required=True,
        ondelete='CASCADE', readonly=True)
    category_combo_id = fields.Char(
        "Category Combo ID", required=True,
        help="The ID of the category combo", readonly=True)
    name = fields.Char(
        "Name", required=True, help="Name of the category combo",
        readonly=True)
    data_dimension_type = fields.Char(
        "Data Dimension Type", required=True,
        help="The data dimension type of the category combo", readonly=True)
    category_options = fields.One2Many(
        'gnuhealth.dhis2.category_option_combo',
        'category_combo', "Category Options", readonly=True)
    data_sets = fields.One2Many(
        'gnuhealth.dhis2.data_set', 'category_combo',
        "Data Sets", readonly=True)

    def sync(self) -> None:
        """
        Synchronize this category combo with DHIS2 and
        update the category options
        """
        dhis_category_combo = self.server.get_category_combo(
            self.category_combo_id)
        self.name = dhis_category_combo['displayName']
        self.data_dimension_type = dhis_category_combo['dataDimensionType']
        self.save()

        # Sync category options
        dhis_category_options = dhis_category_combo['categoryOptionCombos']
        for category_option in self.category_options:
            for dhis_category_option in dhis_category_options:
                if category_option.category_option_combo_id == \
                        dhis_category_option['id']:
                    category_option.sync()
                    dhis_category_options.remove(dhis_category_option)
                    break
            else:
                category_option.delete()
        for dhis_category_option in dhis_category_options:
            dhis_category_option_details = (
                self.server.get_category_option_combo(
                    dhis_category_option['id']))
            Pool().get('gnuhealth.dhis2.category_option_combo').create([{
                'server': self.server.id,
                'category_combo': self.id,
                'category_option_combo_id': dhis_category_option['id'],
                'name': dhis_category_option_details['displayName'],
            }])


class Dhis2CategoryOptionCombo(ModelSQL, ModelView):
    """DHIS2 Category Option Combo"""
    __name__ = 'gnuhealth.dhis2.category_option_combo'
    _rec_name = 'name'

    server = fields.Many2One(
        'gnuhealth.dhis2.server', "Server", required=True,
        ondelete='CASCADE', readonly=True)
    category_combo = fields.Many2One(
        'gnuhealth.dhis2.category_combo', "Category Combo",
        required=True, ondelete='CASCADE', readonly=True)
    category_option_combo_id = fields.Char(
        "Category Option Combo ID", required=True,
        help="The ID of the category option combo", readonly=True)
    name = fields.Char(
        "Name", required=True,
        help="Name of the category option combo", readonly=True)

    def sync(self) -> None:
        """Synchronize this category option combo with DHIS2"""
        dhis_category_option_combo = self.server.get_category_option_combo(
            self.category_option_combo_id)
        self.name = dhis_category_option_combo['displayName']
        self.save()


class Dhis2DataSet(ModelSQL, ModelView):
    """DHIS2 Data Set"""
    __name__ = 'gnuhealth.dhis2.data_set'
    _rec_name = 'name'

    server = fields.Many2One(
        'gnuhealth.dhis2.server', "Server", required=True,
        ondelete='CASCADE', readonly=True)
    org_unit = fields.Many2One(
        'gnuhealth.dhis2.org_unit', "Organisation Unit")
    category_combo = fields.Many2One(
        'gnuhealth.dhis2.category_combo', "Category Combo",
        readonly=True)
    name = fields.Char(
        "Name", required=True, help="Name of the data set", readonly=True)
    data_set_id = fields.Char(
        "Data Set ID", required=True,
        help="The ID of the data set", readonly=True)
    period_type = fields.Char(
        "Period Type", required=True,
        help="The period type of the data set", readonly=True)
    data_elements = fields.One2Many(
        'gnuhealth.dhis2.data_element', 'data_set',
        "Data Elements", readonly=True)

    server_url = fields.Function(fields.Char("Link"), 'get_server_url')

    def get_server_url(self, _) -> str:
        """
        Helper function for the field.Function to get the server url
        :param _: unused parameter
        :return: the url of the server
        """
        return self.server.url

    def sync(self) -> None:
        """Synchronize this data set with DHIS2 and update the data elements"""
        # Sync data set
        CategoryCombo = Pool().get('gnuhealth.dhis2.category_combo')
        DataElement = Pool().get('gnuhealth.dhis2.data_element')

        dhis_data_set = self.server.get_dataset(self.data_set_id)
        self.name = dhis_data_set['displayName']
        self.period_type = dhis_data_set['periodType']
        self.category_combo = CategoryCombo.search(
            [('category_combo_id', '=',
              dhis_data_set['categoryCombo']['id'])])[0]
        self.save()

        # Sync data elements
        dhis_data_elements = dhis_data_set['dataSetElements']
        for data_element in self.data_elements:
            for dhis_data_element in dhis_data_elements:
                if data_element.data_element_id == \
                        dhis_data_element['dataElement']['id']:
                    data_element.sync()
                    dhis_data_elements.remove(dhis_data_element)
                    break
            else:
                data_element.delete()
        for dhis_data_element in dhis_data_elements:
            dhis_data_element_details = self.server.get_data_element(
                dhis_data_element['dataElement']['id'])
            data_element = DataElement.create([{
                'data_set': self.id,
                'name': dhis_data_element_details['displayName'],
                'data_element_id': dhis_data_element['dataElement']['id'],
                'aggregation_type': dhis_data_element_details[
                    'aggregationType'],
                'value_type': dhis_data_element_details['valueType'],
                'domain_type': dhis_data_element_details['domainType'],
                'category_combo': CategoryCombo.search(
                    [('category_combo_id', '=',
                      dhis_data_element_details['categoryCombo']['id'])])[0]
            }])
            data_element[0].sync()


class Dhis2DataElement(ModelSQL, ModelView):
    """DHIS2 Data Element"""
    __name__ = 'gnuhealth.dhis2.data_element'
    _rec_name = 'name'

    data_set = fields.Many2One(
        'gnuhealth.dhis2.data_set', "Data Set", required=True,
        ondelete='CASCADE', readonly=True)
    name = fields.Char(
        "Name", required=True, help="Name of the data element",
        readonly=True)
    data_element_id = fields.Char(
        "Data Element ID", required=True,
        help="The ID of the data element", readonly=True)
    aggregation_type = fields.Char(
        "Aggregation Type", required=True,
        help="The aggregation type of the data element", readonly=True)
    value_type = fields.Char(
        "Value Type", required=True,
        help="The value type of the data element", readonly=True)
    domain_type = fields.Char(
        "Domain Type", required=True,
        help="The domain type of the data element", readonly=True)
    data_mapping = fields.One2Many(
        'gnuhealth.dhis2.data_mapping', 'data_element',
        "Data Mappings", readonly=True)
    category_combo = fields.Many2One(
        'gnuhealth.dhis2.category_combo', "Category Combo",
        required=True, readonly=True)

    def sync(self) -> None:
        """
        Synchronize this data element with DHIS2 and
        update the data mappings
        """
        CategoryCombo = Pool().get('gnuhealth.dhis2.category_combo')
        DataMapping = Pool().get('gnuhealth.dhis2.data_mapping')

        dhis_data_element = self.data_set.server.get_data_element(
            self.data_element_id)
        self.name = dhis_data_element['displayName']
        self.aggregation_type = dhis_data_element['aggregationType']
        self.value_type = dhis_data_element['valueType']
        self.domain_type = dhis_data_element['domainType']
        self.category_combo = CategoryCombo.search([
            ('category_combo_id', '=',
             dhis_data_element['categoryCombo']['id'])])[0]
        self.save()

        # Create a list of all possible category option combinations
        category_combinations = []
        for attribute_option in self.data_set.category_combo.category_options:
            for category_option in self.category_combo.category_options:
                category_combinations.append(
                    (attribute_option, category_option))

        # Create data mappings
        for data_mapping in self.data_mapping:
            for category_combination in category_combinations:
                if (data_mapping.attribute_option.category_option_combo_id
                        == category_combination[0].category_option_combo_id
                        and
                        data_mapping.category_option.category_option_combo_id
                        == category_combination[1].category_option_combo_id):
                    category_combinations.remove(category_combination)
                    data_mapping.sync()
                    break
            else:
                data_mapping.delete()
        for category_combination in category_combinations:
            DataMapping.create([{
                'data_element': self.id,
                'attribute_option': category_combination[0].id,
                'category_option': category_combination[1].id,
                'name': f'{self.name} ({category_combination[0].name}) - '
                        f'{category_combination[1].name}',
            }])


class Dhis2DataMapping(ModelSQL, ModelView):
    """
    This table contains the mapping between the DHIS2 data elements and
    the GNU Health data
    """
    __name__ = 'gnuhealth.dhis2.data_mapping'
    _rec_name = 'name'

    data_element = fields.Many2One(
        'gnuhealth.dhis2.data_element', "Data Element",
        required=True, ondelete='CASCADE', readonly=True)
    attribute_option = fields.Many2One(
        'gnuhealth.dhis2.category_option_combo',
        "Attribute Option", required=True, ondelete='CASCADE',
        readonly=True)
    category_option = fields.Many2One(
        'gnuhealth.dhis2.category_option_combo',
        "Category Option", required=True,
        ondelete='CASCADE', readonly=True)
    name = fields.Char(
        "Name", required=True, help="Name of the data mapping",
        readonly=True)
    sql_query = fields.Char(
        "SQL Query", readonly=True,
        help="The SQL query that fetches the data from the database")
    mapping_active = fields.Boolean(
        "Active", help="A flag to indicate if the data mapping is active")

    def sync(self) -> None:
        """Synchronize this data mapping with DHIS2"""
        self.name = f"{self.data_element.name} - {self.category_option.name}"
        self.save()

    @staticmethod
    def _execute_query(query: str) -> (List, List):
        """
        Executes the given query and returns the column names and the result
        :param query: string of the query to execute
        :return: a tuple of the column names and the result
        """
        with Transaction().connection.cursor() as cursor:
            # For some reason double quotation marks get duplicated when
            # saving the query
            cursor.execute(query.replace("\"\"", "\""))
            cursor.execute(query)
            data = cursor.fetchall()
            return cursor.description, data

    @staticmethod
    def test_query(query: str) -> (List, List):
        """
        Checks if the sql query is valid and the result contains the required
        columns
        :param query: string of the query to execute
        :return: the column names and the result of the query
        :raises UserError: if the query is invalid or does not contain
        the correct columns
        """
        if not query:
            raise UserError("No query defined")

        description, data = Dhis2DataMapping._execute_query(query)
        for column in description:
            if column.name == 'date':
                break
        else:
            raise UserError("The query must contain a date column")
        for column in description:
            if column.name == 'value':
                break
        else:
            raise UserError("The query must contain a value column")
        return description, data

    def submit_data(self, dry_run: bool = False) -> None:
        """
        Executes the sql query and submits the data to DHIS2
        :param dry_run: if True, the data will not be saved to DHIS2
        """
        if not self.sql_query or not self.mapping_active:
            return
        description, data = Dhis2DataMapping._execute_query(self.sql_query)

        # Submit data to DHIS2
        data_value_set = {'dryRun': dry_run,
                          'dataValues': [],
                          'attributeOptionCombo':
                              self.attribute_option.category_option_combo_id}
        for row in data:
            data_value = {
                'dataElement': self.data_element.data_element_id,
                'orgUnit': self.data_element.data_set.org_unitorg_unit_id,
                'categoryOptionCombo':
                    self.category_option.category_option_combo_id,
            }
            for column, value in zip(description, row):
                if column.name == 'date':
                    data_value['period'] = DataSetPeriodType(
                        self.data_element.data_set.period_type).get_date_str(
                        value)
                elif column.name == 'value':
                    data_value['value'] = value
            data_value_set['dataValues'].append(data_value)
        self.data_element.data_set.server.post(
            '/dataValueSets', data=data_value_set)
