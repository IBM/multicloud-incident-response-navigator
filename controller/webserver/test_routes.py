from app import app, db
import unittest

app.testing = True

class TestRoutes(unittest.TestCase):

    def setUp(self):
        self.app = app
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()

    def test_add_resource_view_db(self):
        testapp = app.test_client()
        result = testapp.post(
            '/resource/test_cluster_0',
            data=dict(
	        uid = 'test_cluster_0',
	        rtype = 'resourcetype',
	        name ='resourcename',
	        cluster = 'test_cluster',
	        namespace = 'test_ns'),
            follow_redirects=True
        )
        all_resources = testapp.get('/view_resources').json
        # print('HI', all_resources)
        self.assertEqual(len(all_resources['resources']),1)
        expected_dict = {"id":"1",
                         "uid": "test_cluster_0",
                         "rtype": "resourcetype",
                         "name": "resourcename",
                         "cluster": "test_cluster",
                         "namespace": "test_ns",
                         "app_path": "None",
                         "application": "None",
                         "cluster_path": "None",
                         "created_at": "None",
                         "info": "None",
                         "sev_measure": "None"
                         }
        for key in expected_dict.keys():
            self.assertEqual(expected_dict[key], all_resources['resources'][0][key])

    def test_switch_mode(self):
        testapp = app.test_client()
        result = testapp.post('/resource/cluster1_0', data=dict(uid='cluster1_0',rtype='grandpa',name='grandpa1',cluster='cluster1',namespace='ns1',app_path='/root/'),follow_redirects=True)
        result = testapp.post('/resource/cluster1_1', data=dict(uid='cluster1_1',rtype='dad', name='dad1',cluster='cluster1', namespace='ns1', app_path='/root/cluster1_0/'),follow_redirects=True)
        result = testapp.post('/resource/cluster1_2', data=dict(uid='cluster1_2',rtype='son', name='son1',cluster='cluster1',namespace='ns1',app_path='/root/cluster1_0/cluster1_1/'),follow_redirects=True)
        result = testapp.post('/resource/cluster1_3', data=dict(uid='cluster1_3', rtype='mom', name='mom1',cluster='cluster1', namespace = 'ns1', app_path = '/root/cluster1_0/'), follow_redirects = True)
        result = testapp.post('/resource/cluster1_4', data=dict(uid='cluster1_4', rtype='daughter', name='daughter1',cluster='cluster1', namespace = 'ns1', app_path = '/root/cluster1_0/cluster1_3/'), follow_redirects = True)

        result = testapp.post('/edge/root/cluster1_0', data=dict(start_uid='root', end_uid='cluster1_0', relation="Root<-grandpa"), follow_redirects=True)
        result = testapp.post('/edge/cluster1_0/cluster1_1', data=dict(start_uid='cluster1_0', end_uid='cluster1_1', relation="grandpa<-dad"), follow_redirects=True)
        result = testapp.post('/edge/cluster1_1/cluster1_2', data=dict(start_uid='cluster1_1', end_uid='cluster1_2', relation="dad<-son"), follow_redirects=True)
        result = testapp.post('/edge/cluster1_0/cluster1_3', data=dict(start_uid='cluster1_0', end_uid='cluster1_3', relation="grandpa<-mom"), follow_redirects=True)
        result = testapp.post('/edge/cluster1_3/cluster1_4', data=dict(start_uid='cluster1_3', end_uid='cluster1_4', relation="mom<-daughter"), follow_redirects=True)

        new_info = testapp.get('/mode/app/switch/cluster1_3').json
        print('HI', new_info)
        self.assertEqual(['grandpa1'], new_info['path'])
        self.assertEqual(['grandpa'], new_info['rtypes'])
        self.assertEqual(2, len(new_info['table_items']))
        self.assertIn( new_info['table_items'][0]['uid'], ['cluster1_1', 'cluster1_3'])
        self.assertIn( new_info['table_items'][1]['uid'], ['cluster1_1', 'cluster1_3'])

    # # TODO unfinished
    # def test_redirect(self):
    #     testapp = app.test_client()
    #     result = testapp.post(
    #         '/resource/test_cluster_0',
    #         data=dict(
    #             uid='test_cluster_0',
    #             rtype='resourcetype',
    #             name='resourcename',
    #             cluster='test_cluster',
    #             namespace='test_ns'),
    #         follow_redirects=True
    #     )
    #     result = testapp.get('/redirectme')
    #     print(result)
    #     self.assertEqual(len(result['resources']), 1)
    #     expected_dict = {"id": "1",
    #                      "uid": "test_cluster_0",
    #                      "rtype": "resourcetype",
    #                      "name": "resourcename",
    #                      "cluster": "test_cluster",
    #                      "namespace": "test_ns",
    #                      "app_path": "None",
    #                      "application": "None",
    #                      "cluster_path": "None",
    #                      "created_at": "None",
    #                      "info": "None",
    #                      "sev_measure": "None"
    #                      }
    #     for key in expected_dict.keys():
    #         self.assertEqual(expected_dict[key], result['resources'][0][key])
