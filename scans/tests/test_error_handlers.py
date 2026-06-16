"""Project-wide error handler tests.

Django forces DEBUG=False during `manage.py test`, so the
`handler404` setting in `config/urls.py` is active here, so the test
client will route a nonexistent URL through our custom handler and
template, not Django's debug 404.
"""
from django.test import TestCase


class CustomErrorHandlersTests(TestCase):
    def test_404_renders_custom_template(self):
        response = self.client.get("/this-url-does-not-exist/")
        self.assertEqual(response.status_code, 404)
        # The custom template ships the phrases below; Django's debug
        # 404 doesn't. Two distinct markers so a one-off match isn't
        # enough to pass.
        self.assertContains(response, "Off the map", status_code=404)
        self.assertContains(response, "404: not found", status_code=404)

    def test_404_links_back_to_app_root(self):
        response = self.client.get("/another-missing-url/")
        self.assertContains(response, 'href="/app/"', status_code=404)
