import unittest
from src.hello import say_hello


class TestHello(unittest.TestCase):
    def setUp(self):
        self.name = "Ashoka"

    def tearDown(self):
        pass

    def test_say_hello(self):
        assert say_hello(self.name) == f"Hello, {self.name}!"
