# -*- coding: utf-8 -*-
import unittest
import webtest
import os

from openprocurement.api import VERSION
from openprocurement.api.models import TenderDocument
from openprocurement.api.migration import migrate_data, get_db_schema_version, set_db_schema_version, SCHEMA_VERSION


test_tender_data = {
    "procuringEntity": {
        "id": {
            "name": "Державне управління справами",
            "scheme": "https://ns.openprocurement.org/ua/edrpou",
            "uid": "00037256",
            "uri": "http://www.dus.gov.ua/"
        },
        "address": {
            "countryName": "Україна",
            "postalCode": "01220",
            "region": "м. Київ",
            "locality": "м. Київ",
            "streetAddress": "вул. Банкова, 11, корпус 1"
        },
    },
    "totalValue": {
        "amount": 500,
        "currency": "UAH"
    },
    "itemsToBeProcured": [
        {
            "description": "футляри до державних нагород",
            "classificationScheme": "Other",
            "otherClassificationScheme": "ДКПП",
            "classificationID": "17.21.1",
            "classificationDescription": "папір і картон гофровані, паперова й картонна тара",
            "unitOfMeasure": "item",
            "quantity": 5
        }
    ],
    "clarificationPeriod": {
        "endDate": "2014-10-31T00:00:00"
    },
    "tenderPeriod": {
        "endDate": "2014-11-06T10:00:00"
    },
    "awardPeriod": {
        "endDate": "2014-11-13T00:00:00"
    }
}


class PrefixedRequestClass(webtest.app.TestRequest):

    @classmethod
    def blank(cls, path, *args, **kwargs):
        path = '/api/%s%s' % (VERSION, path)
        return webtest.app.TestRequest.blank(path, *args, **kwargs)


class BaseWebTest(unittest.TestCase):

    """Base Web Test to test openprocurement.api.

    It setups the database before each test and delete it after.
    """

    def setUp(self):
        self.app = webtest.TestApp(
            "config:tests.ini", relative_to=os.path.dirname(__file__))
        self.app.RequestClass = PrefixedRequestClass
        self.couchdb_server = self.app.app.registry.couchdb_server
        self.db = self.app.app.registry.db

    def tearDown(self):
        del self.couchdb_server[self.db.name]


class BaseTenderWebTest(BaseWebTest):

    def setUp(self):
        super(BaseTenderWebTest, self).setUp()
        # Create tender
        response = self.app.post_json('/tenders', {'data': {}})
        tender = response.json['data']
        self.tender_id = tender['id']

    def taerDown(self):
        del self.db[self.tender_id]
        super(BaseTenderWebTest, self).taerDown()


class TenderDocumentTest(BaseWebTest):

    def test_simple_add_tender(self):
        u = TenderDocument()
        u.tenderID = "UA-X"

        assert u.id is None
        assert u.rev is None

        u.store(self.db)

        assert u.id is not None
        assert u.rev is not None

        fromdb = self.db.get(u.id)

        assert u.tenderID == fromdb['tenderID']
        assert u.doc_type == "TenderDocument"

        u.delete_instance(self.db)


class SporeTest(BaseWebTest):

    def test_spore(self):
        response = self.app.get('/spore')
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json["version"], VERSION)


class MigrateTest(BaseWebTest):

    def test_migrate(self):
        self.assertEqual(get_db_schema_version(self.db), SCHEMA_VERSION)
        migrate_data(self.db, 1)
        self.assertEqual(get_db_schema_version(self.db), SCHEMA_VERSION)

    def test_migrate_from0to1(self):
        set_db_schema_version(self.db, 0)
        data = {'doc_type': 'TenderDocument',
                'modifiedAt': '2014-10-15T00:00:00.000000'}
        _id, _rev = self.db.save(data)
        item = self.db.get(_id)
        migrate_data(self.db, 1)
        migrated_item = self.db.get(_id)
        self.assertFalse('modified' in item)
        self.assertTrue('modifiedAt' in item)
        self.assertTrue('modified' in migrated_item)
        self.assertFalse('modifiedAt' in migrated_item)
        self.assertEqual(item['modifiedAt'], migrated_item['modified'])

    def test_migrate_from1to2(self):
        set_db_schema_version(self.db, 1)
        data = {
            "procuringEntity": {
                "address": {
                    "country-name": "Україна",
                    "postal-code": "01220",
                    "street-address": "вул. Банкова, 11, корпус 1"
                },
            },
            'doc_type': 'TenderDocument',
            'bidders': [{
                "address": {
                    "country-name": "Україна",
                    "postal-code": "01220",
                    "street-address": "вул. Банкова, 11, корпус 1"
                },
            }]
        }
        _id, _rev = self.db.save(data)
        item = self.db.get(_id)
        migrate_data(self.db, 2)
        migrated_item = self.db.get(_id)
        self.assertTrue('country-name' in item["procuringEntity"]["address"])
        self.assertFalse('countryName' in item["procuringEntity"]["address"])
        self.assertTrue('country-name' in item["bidders"][0]["address"])
        self.assertFalse('countryName' in item["bidders"][0]["address"])
        self.assertFalse(
            'country-name' in migrated_item["procuringEntity"]["address"])
        self.assertTrue(
            'countryName' in migrated_item["procuringEntity"]["address"])
        self.assertFalse(
            'country-name' in migrated_item["bidders"][0]["address"])
        self.assertTrue(
            'countryName' in migrated_item["bidders"][0]["address"])

    def test_migrate_from2to3(self):
        set_db_schema_version(self.db, 2)
        data = {
            'doc_type': 'TenderDocument',
            'bidders': [{
                "_id": "UUID",
                "id": {
                    "name": "Державне управління справами"
                },
            }]
        }
        _id, _rev = self.db.save(data)
        item = self.db.get(_id)
        migrate_data(self.db, 3)
        migrated_item = self.db.get(_id)
        self.assertTrue('bidders' in item)
        self.assertFalse('bids' in item)
        self.assertFalse('bidders' in migrated_item)
        self.assertTrue('bids' in migrated_item)
        self.assertEqual(
            item["bidders"][0]["_id"], migrated_item["bids"][0]["id"])
        self.assertEqual(item["bidders"][0]["id"]["name"], migrated_item[
                         "bids"][0]["bidders"][0]["id"]["name"])


class TenderResourceTest(BaseWebTest):

    def test_empty_listing(self):
        response = self.app.get('/tenders')
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.body, '{"tenders": []}')

    def test_listing(self):
        response = self.app.get('/tenders')
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(len(response.json['tenders']), 0)

        for i in range(3):
            response = self.app.post_json('/tenders', {'data': {}})
            self.assertEqual(response.status, '201 Created')
            self.assertEqual(response.content_type, 'application/json')

        response = self.app.get('/tenders')
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(len(response.json['tenders']), 3)

    def test_create_tender_invalid(self):
        request_path = '/tenders'
        response = self.app.post(request_path, 'data', status=415)
        self.assertEqual(response.status, '415 Unsupported Media Type')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description':
                u"Content-Type header should be one of ['application/json']", u'location': u'header', u'name': u'Content-Type'}
        ])

        response = self.app.post(
            request_path, 'data', content_type='application/json', status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'No JSON object could be decoded',
                u'location': u'body', u'name': u'data'}
        ])

        response = self.app.post_json(request_path, 'data', status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Data not available',
                u'location': u'body', u'name': u'data'}
        ])

        response = self.app.post_json(request_path, {'not_data': {}}, status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Data not available',
                u'location': u'body', u'name': u'data'}
        ])

        response = self.app.post_json(request_path, {'data': {
                                      'invalid_field': 'invalid_value'}}, status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Rogue field', u'location':
                u'body', u'name': u'invalid_field'}
        ])

        response = self.app.post_json(request_path, {'data': {
                                      'totalValue': 'invalid_value'}}, status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': [
                u'Please use a mapping for this field or Value instance instead of unicode.'], u'location': u'body', u'name': u'totalValue'}
        ])

        response = self.app.post_json(request_path, {
                                      'data': {'method': 'invalid_value'}}, status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': [
                u"Value must be one of ['Open', 'Selective', 'Limited']."], u'location': u'body', u'name': u'method'}
        ])

    def test_create_tender_generated(self):
        data = {'id': 'hash', 'doc_id': 'hash2', 'tenderID': 'hash3'}
        response = self.app.post_json('/tenders', {'data': data})
        self.assertEqual(response.status, '201 Created')
        self.assertEqual(response.content_type, 'application/json')
        tender = response.json['data']
        self.assertEqual(set(tender), set([u'id', u'modified', u'tenderID']))
        self.assertNotEqual(data['id'], tender['id'])
        self.assertNotEqual(data['doc_id'], tender['id'])
        self.assertNotEqual(data['tenderID'], tender['tenderID'])

    def test_create_tender(self):
        response = self.app.get('/tenders')
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(len(response.json['tenders']), 0)

        response = self.app.post_json('/tenders', {"data": test_tender_data})
        self.assertEqual(response.status, '201 Created')
        self.assertEqual(response.content_type, 'application/json')
        tender = response.json['data']
        self.assertEqual(set(tender) - set(test_tender_data), set(
            [u'id', u'modified', u'tenderID']))
        self.assertTrue(tender['id'] in response.headers['Location'])

        response = self.app.get('/tenders/{}'.format(tender['id']))
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['data'], tender)

    def test_get_tender(self):
        response = self.app.get('/tenders')
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(len(response.json['tenders']), 0)

        response = self.app.post_json('/tenders', {'data': {}})
        self.assertEqual(response.status, '201 Created')
        tender = response.json['data']

        response = self.app.get('/tenders/{}'.format(tender['id']))
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['data'], tender)

    def test_put_tender(self):
        response = self.app.get('/tenders')
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(len(response.json['tenders']), 0)

        response = self.app.post_json('/tenders', {'data': {}})
        self.assertEqual(response.status, '201 Created')
        tender = response.json['data']
        tender['method'] = 'Open'
        modified = tender.pop('modified')

        response = self.app.put_json('/tenders/{}'.format(
            tender['id']), {'data': tender})
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        new_tender = response.json['data']
        new_modified = new_tender.pop('modified')
        self.assertEqual(tender, new_tender)
        self.assertNotEqual(modified, new_modified)

    def test_patch_tender(self):
        response = self.app.get('/tenders')
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(len(response.json['tenders']), 0)

        response = self.app.post_json('/tenders', {'data': {}})
        self.assertEqual(response.status, '201 Created')
        tender = response.json['data']
        modified = tender.pop('modified')

        response = self.app.patch_json('/tenders/{}'.format(
            tender['id']), {'data': {'method': 'Open'}})
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        new_tender = response.json['data']
        new_modified = new_tender.pop('modified')
        tender['method'] = 'Open'
        self.assertEqual(tender, new_tender)
        self.assertNotEqual(modified, new_modified)

    def test_modified_tender(self):
        response = self.app.get('/tenders')
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(len(response.json['tenders']), 0)

        response = self.app.post_json('/tenders', {'data': {}})
        self.assertEqual(response.status, '201 Created')
        tender = response.json['data']
        modified = tender['modified']

        response = self.app.get('/tenders/{}'.format(tender['id']))
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['data']['modified'], modified)

        response = self.app.patch_json('/tenders/{}'.format(
            tender['id']), {'data': {'method': 'Open'}})
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        self.assertNotEqual(response.json['data']['modified'], modified)
        tender = response.json['data']
        modified = tender['modified']

        response = self.app.get('/tenders/{}'.format(tender['id']))
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['data'], tender)
        self.assertEqual(response.json['data']['modified'], modified)

    def test_tender_not_found(self):
        response = self.app.get('/tenders')
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(len(response.json['tenders']), 0)

        response = self.app.get('/tenders/some_id', status=404)
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Not Found', u'location': u'url', u'name': u'id'}
        ])

        response = self.app.put_json(
            '/tenders/some_id', {'data': {}}, status=404)
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Not Found', u'location': u'url', u'name': u'id'}
        ])

        response = self.app.patch_json(
            '/tenders/some_id', {'data': {}}, status=404)
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Not Found', u'location': u'url', u'name': u'id'}
        ])


class TenderDocumentResourceTest(BaseTenderWebTest):

    def test_empty_listing(self):
        response = self.app.get('/tenders/{}/documents'.format(self.tender_id))
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json, {"documents": {}})

    def test_get_tender_not_found(self):
        response = self.app.get('/tenders/some_id/documents', status=404)
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Not Found', u'location':
                u'url', u'name': u'tender_id'}
        ])

    def test_post_tender_not_found(self):
        response = self.app.post('/tenders/some_id/documents', status=404, upload_files=[
                                 ('upload', 'name.doc', 'content')])
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Not Found', u'location':
                u'url', u'name': u'tender_id'}
        ])

    def test_put_tender_not_found(self):
        response = self.app.put('/tenders/some_id/documents/some_id', status=404, upload_files=[
                                ('upload', 'name.doc', 'content2')])
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Not Found', u'location':
                u'url', u'name': u'tender_id'}
        ])

    def test_put_tender_document_not_found(self):
        response = self.app.put('/tenders/{}/documents/some_id'.format(
            self.tender_id), status=404, upload_files=[('upload', 'name.doc', 'content2')])
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Not Found', u'location': u'url', u'name': u'id'}
        ])

    def test_get_tender_document_not_found(self):
        response = self.app.get('/tenders/{}/documents/some_id'.format(
            self.tender_id), status=404)
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Not Found', u'location': u'url', u'name': u'id'}
        ])

    def test_create_tender_document(self):
        response = self.app.post('/tenders/{}/documents'.format(
            self.tender_id), upload_files=[('upload', 'name.doc', 'content')])
        self.assertEqual(response.status, '201 Created')
        self.assertEqual(response.content_type, 'application/json')
        self.assertTrue('name.doc' in response.headers['Location'])
        self.assertTrue('name.doc' in response.json["documents"])

        response = self.app.get('/tenders/{}/documents'.format(
            self.tender_id, 'name.doc'))
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        self.assertTrue('name.doc' in response.json["documents"])

        response = self.app.get('/tenders/{}/documents/{}'.format(
            self.tender_id, 'name.doc'))
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'text/html')
        self.assertEqual(response.content_length, 7)
        self.assertEqual(response.body, 'content')

    def test_put_tender_document(self):
        response = self.app.post('/tenders/{}/documents'.format(
            self.tender_id), upload_files=[('upload', 'name.doc', 'content')])
        self.assertEqual(response.status, '201 Created')
        self.assertEqual(response.content_type, 'application/json')
        self.assertTrue('name.doc' in response.json["documents"])

        response = self.app.put('/tenders/{}/documents/{}'.format(
            self.tender_id, 'name.doc'), upload_files=[('upload', 'name.doc', 'content2')])
        self.assertEqual(response.status, '200 OK')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json["content_type"], 'application/msword')
        self.assertEqual(response.json["length"], '8')


class TenderBidderResourceTest(BaseTenderWebTest):

    def test_create_tender_bidder_invalid(self):
        request_path = '/tenders/{}/bidders'.format(self.tender_id)
        response = self.app.post(request_path, 'data', status=415)
        self.assertEqual(response.status, '415 Unsupported Media Type')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description':
                u"Content-Type header should be one of ['application/json']", u'location': u'header', u'name': u'Content-Type'}
        ])

        response = self.app.post(
            request_path, 'data', content_type='application/json', status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'No JSON object could be decoded',
                u'location': u'body', u'name': u'data'}
        ])

        response = self.app.post_json(request_path, 'data', status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Data not available',
                u'location': u'body', u'name': u'data'}
        ])

        response = self.app.post_json(
            request_path, {'not_data': {}}, status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Data not available',
                u'location': u'body', u'name': u'data'}
        ])

        response = self.app.post_json(request_path, {'data': {
                                      'invalid_field': 'invalid_value'}}, status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Rogue field', u'location':
                u'body', u'name': u'invalid_field'}
        ])

        #response = self.app.post_json(request_path, {'data': {}}, status=422)
        #self.assertEqual(response.status, '422 Unprocessable Entity')
        #self.assertEqual(response.content_type, 'application/json')
        #self.assertEqual(response.json['status'], 'error')
        # self.assertEqual(response.json['errors'], [
        #{u'description': [
        # u'This field is required.'], u'location': u'body', u'name': u'id'}
        #])

        response = self.app.post_json(request_path, {
                                      'data': {'bidders': [{'id': 'invalid_value'}]}}, status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': {u'id': [
                u'Please use a mapping for this field or identifier instance instead of unicode.']}, u'location': u'body', u'name': u'bidders'}
        ])

        response = self.app.post_json(request_path, {
                                      'data': {'bidders': [{'id': {}}]}}, status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': [u'id'],
                u'location': u'body', u'name': u'bidders'}
        ])

        response = self.app.post_json(request_path, {'data': {'bidders': [{
                                      'id': {'name': 'name', 'uri': 'invalid_value'}}]}}, status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': [u'id'],
                u'location': u'body', u'name': u'bidders'}
        ])

    def test_post_tender_not_found(self):
        response = self.app.post_json('/tenders/some_id/bidders', {
                                      'data': {'bidders': [{'id': {'name': 'Name'}}]}}, status=404)
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Not Found', u'location':
                u'url', u'name': u'tender_id'}
        ])

    def test_create_tender_bidder(self):
        response = self.app.post_json('/tenders/{}/bidders'.format(
            self.tender_id), {'data': {'bidders': [{'id': {'name': 'Name'}}]}})
        self.assertEqual(response.status, '201 Created')
        self.assertEqual(response.content_type, 'application/json')
        bidder = response.json['data']
        self.assertEqual(bidder['bidders'][0]['id']['name'], 'Name')
        self.assertTrue('id' in bidder)
        # self.assertTrue(bidder['id'] in response.headers['Location'])


class TenderBidderDocumentResourceTest(BaseTenderWebTest):

    def setUp(self):
        super(TenderBidderDocumentResourceTest, self).setUp()
        # Create bid
        response = self.app.post_json('/tenders/{}/bidders'.format(
            self.tender_id), {'data': {'bidders': [{'id': {'name': 'Name'}}]}})
        bid = response.json['data']
        self.bid_id = bid['id']

    def test_post_tender_not_found(self):
        response = self.app.post('/tenders/some_id/bidders/some_id/documents', status=404, upload_files=[
                                 ('upload', 'name.doc', 'content')])
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Not Found', u'location':
                u'url', u'name': u'tender_id'}
        ])

    def test_post_tender_bid_not_found(self):
        response = self.app.post('/tenders/{}/bidders/some_id/documents'.format(self.tender_id), status=404, upload_files=[('upload', 'name.doc', 'content')])
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Not Found', u'location':
                u'url', u'name': u'bid_id'}
        ])

    def test_create_tender_bidder_document(self):
        response = self.app.post('/tenders/{}/bidders/{}/documents'.format(
            self.tender_id, self.bid_id), upload_files=[('upload', 'name.doc', 'content')])
        self.assertEqual(response.status, '201 Created')
        self.assertEqual(response.content_type, 'application/json')
        #self.assertTrue('name.doc' in response.headers['Location'])
        self.assertTrue('name.doc' in response.json["documents"])


class TenderAwardResourceTest(BaseTenderWebTest):

    def test_create_tender_award_invalid(self):
        request_path = '/tenders/{}/awards'.format(self.tender_id)
        response = self.app.post(request_path, 'data', status=415)
        self.assertEqual(response.status, '415 Unsupported Media Type')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description':
                u"Content-Type header should be one of ['application/json']", u'location': u'header', u'name': u'Content-Type'}
        ])

        response = self.app.post(
            request_path, 'data', content_type='application/json', status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'No JSON object could be decoded',
                u'location': u'body', u'name': u'data'}
        ])

        response = self.app.post_json(request_path, 'data', status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Data not available',
                u'location': u'body', u'name': u'data'}
        ])

        response = self.app.post_json(
            request_path, {'not_data': {}}, status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Data not available',
                u'location': u'body', u'name': u'data'}
        ])

        response = self.app.post_json(request_path, {'data': {
                                      'invalid_field': 'invalid_value'}}, status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Rogue field', u'location':
                u'body', u'name': u'invalid_field'}
        ])

        #response = self.app.post_json(request_path, {'data': {}}, status=422)
        #self.assertEqual(response.status, '422 Unprocessable Entity')
        #self.assertEqual(response.content_type, 'application/json')
        #self.assertEqual(response.json['status'], 'error')
        # self.assertEqual(response.json['errors'], [
        #{u'description': [
        # u'This field is required.'], u'location': u'body', u'name': u'id'}
        #])

        response = self.app.post_json(request_path, {
                                      'data': {'suppliers': [{'id': 'invalid_value'}]}}, status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': {u'id': [
                u'Please use a mapping for this field or identifier instance instead of unicode.']}, u'location': u'body', u'name': u'suppliers'}
        ])

        response = self.app.post_json(request_path, {
                                      'data': {'suppliers': [{'id': {}}]}}, status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': [u'id'],
                u'location': u'body', u'name': u'suppliers'}
        ])

        response = self.app.post_json(request_path, {'data': {'suppliers': [{
                                      'id': {'name': 'name', 'uri': 'invalid_value'}}]}}, status=422)
        self.assertEqual(response.status, '422 Unprocessable Entity')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': [u'id'],
                u'location': u'body', u'name': u'suppliers'}
        ])

    def test_post_tender_not_found(self):
        response = self.app.post_json('/tenders/some_id/awards', {
                                      'data': {'suppliers': [{'id': {'name': 'Name'}}]}}, status=404)
        self.assertEqual(response.status, '404 Not Found')
        self.assertEqual(response.content_type, 'application/json')
        self.assertEqual(response.json['status'], 'error')
        self.assertEqual(response.json['errors'], [
            {u'description': u'Not Found', u'location':
                u'url', u'name': u'tender_id'}
        ])

    def test_create_tender_award(self):
        response = self.app.post_json('/tenders/{}/awards'.format(
            self.tender_id), {'data': {'suppliers': [{'id': {'name': 'Name'}}]}})
        self.assertEqual(response.status, '201 Created')
        self.assertEqual(response.content_type, 'application/json')
        award = response.json['data']
        self.assertEqual(award['suppliers'][0]['id']['name'], 'Name')
        self.assertTrue('awardID' in award)
        # self.assertTrue(award['id'] in response.headers['Location'])


def suite():
    suite = unittest.TestSuite()
    suite.addTest(unittest.makeSuite(MigrateTest))
    suite.addTest(unittest.makeSuite(SporeTest))
    suite.addTest(unittest.makeSuite(TenderAwardResourceTest))
    suite.addTest(unittest.makeSuite(TenderBidderDocumentResourceTest))
    suite.addTest(unittest.makeSuite(TenderBidderResourceTest))
    suite.addTest(unittest.makeSuite(TenderDocumentResourceTest))
    suite.addTest(unittest.makeSuite(TenderDocumentTest))
    suite.addTest(unittest.makeSuite(TenderResourceTest))
    return suite


if __name__ == '__main__':
    unittest.main(defaultTest='suite')