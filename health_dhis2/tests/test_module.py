# SPDX-FileCopyrightText: 2023 Florian Liermann
#
# SPDX-License-Identifier: GPL-3.0-or-later

import os
import unittest
import warnings

import requests.exceptions
import responses
from responses import _recorder, matchers

from trytond.pool import Pool
from trytond.tests.test_tryton import ModuleTestCase, with_transaction

from ..exceptions import NotFoundError, UnauthorizedError


class HealthDhis2TestCase(ModuleTestCase):
    """Test Dhis2 module"""
    module = 'health_dhis2'

    def setUp(self):
        super(HealthDhis2TestCase, self).setUp()
        # Ignore ResourceWarning: unclosed <socket.socket...> warnings
        warnings.simplefilter('ignore', ResourceWarning)

    @responses.activate
    @with_transaction()
    def test_api_404(self):
        """
        Test that server is set to not validated if the api
        is not reachable
        """
        responses.add(responses.GET, 'http://test_dhis.com/api/me', status=404)
        pool = Pool()
        Server = pool.get('gnuhealth.dhis2.server')
        server = Server.create([{
            'label': 'test',
            'url': 'http://test_dhis.com',
            'pat': 'test',
            'validated': True,
        }])[0]
        self.assertEqual(server.validated, True)
        with self.assertRaises(NotFoundError):
            server.sync()
        self.assertEqual(server.validated, False)

    @responses.activate
    @with_transaction()
    def test_api_401(self):
        """Test invalid personal access token"""
        responses.add(responses.GET, 'http://test_dhis.com/api/me', status=401)
        pool = Pool()
        Server = pool.get('gnuhealth.dhis2.server')
        server = Server.create([{
            'label': 'test',
            'url': 'http://test_dhis.com',
            'pat': 'test',
            'validated': True,
        }])[0]
        with self.assertRaises(UnauthorizedError):
            server.sync()

    @responses.activate
    @with_transaction()
    def test_sync(self):
        """Test the synchronization to DHIS2"""
        responses._add_from_file(
            file_path=os.path.join(os.path.dirname(__file__),
                                   'responses.yaml'))
        pool = Pool()
        Server = pool.get('gnuhealth.dhis2.server')
        DataMapping = pool.get('gnuhealth.dhis2.data_mapping')

        server = Server.create([{
            'label': 'test',
            'url': 'http://localhost:8080',
            'pat': 'd2pat_foo',
        }])[0]
        server.sync()

        # Check that the server is validated and the org unit is created
        self.assertEqual(server.validated, True)
        self.assertEqual(len(server.org_units), 1)
        self.assertEqual(server.org_units[0].org_unit_id, 'fRx7slGzH46')
        self.assertEqual(server.org_units[0].name, "Test Organisation Unit")

        # Check that all data mappings are created
        data_mappings = DataMapping.search([])
        self.assertEqual(len(data_mappings), 20)

    @responses.activate
    @with_transaction()
    def test_submit_data(self):
        """Test submitting data to DHIS2"""

        # Create objects
        pool = Pool()
        Server = pool.get('gnuhealth.dhis2.server')
        OrgUnit = pool.get('gnuhealth.dhis2.org_unit')
        CategoryCombo = pool.get('gnuhealth.dhis2.category_combo')
        CategoryOptionCombo = pool.get('gnuhealth.dhis2.category_option_combo')
        DataSet = pool.get('gnuhealth.dhis2.data_set')
        DataElement = pool.get('gnuhealth.dhis2.data_element')
        DataMapping = pool.get('gnuhealth.dhis2.data_mapping')
        Pathology = pool.get('gnuhealth.pathology')
        Party = pool.get('party.party')
        HealthProfessional = pool.get('gnuhealth.healthprofessional')
        Patient = pool.get('gnuhealth.patient')
        Disease = pool.get('gnuhealth.patient.disease')

        server = Server.create([{
            'label': 'test',
            'url': 'http://localhost:8080',
            'pat': 'd2pat_foo',
        }])[0]
        org_unit = OrgUnit.create([{
            'server': server,
            'org_unit_id': 'ORG_UNIT',
            'name': "Test Organisation Unit",
        }])[0]
        category_combo = CategoryCombo.create([{
            'server': server,
            'category_combo_id': 'CAT_COMBO',
            'name': "Test Category Combo",
            'data_dimension_type': 'Aggregation',
        }])[0]
        category_option_combo = CategoryOptionCombo.create([{
            'server': server,
            'category_option_combo_id': 'CAT_OPTION',
            'name': "Test Category Option Combo",
            'category_combo': category_combo,
        }])[0]
        data_set = DataSet.create([{
            'server': server,
            'org_unit': org_unit,
            'data_set_id': 'CAT_COMBO',
            'name': "Test Data Set",
            'period_type': 'Monthly',
            'category_combo': category_combo,
        }])[0]
        data_element = DataElement.create([{
            'data_set': data_set,
            'data_element_id': 'DATA_ELEMENT',
            'name': "Test Data Element",
            'aggregation_type': 'Sum',
            'value_type': 'Number',
            'domain_type': 'Aggregate',
            'category_combo': category_combo,
        }])[0]
        data_mapping = DataMapping.create([{
            'data_element': data_element,
            'name': "Test Data Mapping",
            'attribute_option': category_option_combo,
            'category_option': category_option_combo,
            'sql_query': 'SELECT DATE_TRUNC(\'month\', '
                         '\"a\".\"diagnosed_date\") AS \"date\", '
                         'COUNT(\"a\".\"id\") AS \"value\" FROM '
                         '\"gnuhealth_patient_disease\" AS \"a\" WHERE (('
                         '\"a\".\"pathology\" = 1) AND ('
                         '\"a\".\"diagnosed_date\" IS NOT NULL)) GROUP BY '
                         'DATE_TRUNC( \'month\', \"a\".\"diagnosed_date\")',
            'mapping_active': True,
        }])[0]

        # Create pathology
        pathology = Pathology.create([{
            'name': 'foo',
            'code': 'bar',
        }])[0]

        # Create health professional
        party = Party.create([{
            'name': 'foo',
            'is_healthprof': True,
            'is_patient': True,
            'is_person': True,
            'ref': 'FOO',
            'federation_account': 'FOO',
            'fed_country': 'FOO',
            'gender': 'm',
        }])[0]
        health_professional = HealthProfessional.create([{
            'name': party,
        }])[0]
        patient = Patient.create([{
            'name': party,
        }])[0]

        # Fill gnuhealth.patient.disease with data
        diseases = []
        for _ in range(5):
            diseases.append({
                'diagnosed_date': '2023-10-01',
                'pathology': pathology,
                'healthprof': health_professional,
                'name': patient,
            })
        Disease.create(diseases)

        responses.post(
            url='http://localhost:8080/api/dataValueSets',
            match=[matchers.json_params_matcher(
                {'dryRun': False,
                 'dataValues': [
                     {'dataElement': 'DATA_ELEMENT',
                      'orgUnit': 'ORG_UNIT',
                      'categoryOptionCombo': 'CAT_OPTION',
                      'period': '202310',
                      'value': 5}
                 ],
                 'attributeOptionCombo': 'CAT_OPTION'})],
            status=200,
            body='{}',
        )
        try:
            data_mapping.submit_data()
        except requests.exceptions.ConnectionError as e:
            self.fail(f"Sent the wrong data to DHIS2: {e}")

    @with_transaction()
    @_recorder.record(file_path='/tmp/responses.yaml')
    @unittest.skip("Only used for recording the responses of the DHIS2 API")
    def test_record(self):
        """
        Record the responses of the DHIS2 API.
        A local DHIS2 instance must be running on `http://localhost:8080` and
        a valid personal access token
        must be entered below. The recorded responses are then stored in
        `/tmp/responses.yaml`.
        """
        pool = Pool()
        Server = pool.get('gnuhealth.dhis2.server')
        server = Server.create([{
            'label': 'test',
            'url': 'http://localhost:8080',
            'pat': 'd2pat_ajXIs6yoe5erRqisvby4PxZqQCo5d5Lx1092887431',
        }])[0]
        server.sync()


del ModuleTestCase
